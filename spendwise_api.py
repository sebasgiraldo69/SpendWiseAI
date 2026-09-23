"""Async REST API. Local persistence never waits for an AI request."""
import asyncio
from contextlib import asynccontextmanager
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import urlsplit
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from starlette.concurrency import run_in_threadpool
from spendwise_jobs import JobManager
from spendwise_provider import GeminiClient, ProviderError
import spendwise_storage as storage
import spendwise_service as service
from spendwise_core import CATEGORIES, money, calculate_financials, calculate_goal_scenario, calculate_event_scenario
from spendwise_compare import compare_budgets

ROOT=Path(__file__).resolve().parent
TTL=1800

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Extract(Input):
    input: str = Field(min_length=1,max_length=12000)
    consent: StrictBool

class ProfileSelect(Input):
    profile_id: str = Field(min_length=1,max_length=80)

class ProfileCreate(Input):
    display_name: str = Field(min_length=1,max_length=80)

class Compare(Input):
    budget_a_id: str
    budget_b_id: str
    consent: StrictBool = False

class Scenario(Input):
    text: str = Field(min_length=1,max_length=4000)
    type: str
    budget_id: str
    consent: StrictBool

class Database:
    def __init__(self,path=None):self.path=path
    def run(self,operation,*args,**kwargs):
        conn=storage.get_connection(self.path)
        try:return operation(conn,*args,**kwargs)
        finally:conn.close()
    async def call(self,operation,*args,**kwargs):
        return await run_in_threadpool(self.run,operation,*args,**kwargs)

def normalize_movements(movements):
    if not isinstance(movements,list) or not 1<=len(movements)<=100:
        raise ValueError('Incluye entre 1 y 100 movimientos.')
    normalized=[]
    for m in movements:
        if not isinstance(m,dict):raise ValueError('Movimiento inválido.')
        desc=m.get('description',m.get('descripcion'))
        if not isinstance(desc,str) or not 1<=len(desc.strip())<=200:raise ValueError('Descripción inválida.')
        amount=m.get('amount',m.get('valor'))
        category=m.get('category',m.get('categoria'))
        if money(amount)<0 or category not in CATEGORIES:raise ValueError('Monto o categoría inválidos.')
        origin=m.get('origin','manual')
        if origin not in ('manual','interpreted','scenario'):raise ValueError('Origen inválido.')
        normalized.append({'description':desc.strip(),'amount':amount,'category':category,
                           'source_quote':m.get('source_quote',m.get('fuente')),'origin':origin})
    return normalized

def summary(budget):
    return calculate_financials(float(budget['income']) if budget['income'] is not None else None,
        [{'valor':float(m['amount']),'categoria':m['category']} for m in budget['movements']])

def create_app(db_path=None,provider=None,job_deadline=40):
    db=Database(db_path)
    sessions={}

    @asynccontextmanager
    async def lifespan(api):
        await db.call(storage.initialize_database)
        api.state.provider=provider or GeminiClient(service.MODEL)
        api.state.jobs=JobManager(deadline=job_deadline)
        async def cleanup():
            while True:
                await asyncio.sleep(30)
                api.state.jobs.prune()
                for sid in list(sessions):
                    if time.monotonic()-sessions[sid]['touched']>TTL:
                        api.state.jobs.clear_owner(sid)
                        del sessions[sid]
        cleaner=asyncio.create_task(cleanup())
        try:yield
        finally:
            cleaner.cancel()
            await asyncio.gather(cleaner,return_exceptions=True)
            await api.state.jobs.close()
            await api.state.provider.close()
            sessions.clear()

    api=FastAPI(title='SpendWise API',version='2.0.0',lifespan=lifespan,docs_url=None,redoc_url=None)

    @api.middleware('http')
    async def boundary(request,call_next):
        start=time.perf_counter()
        host=request.headers.get('host','')
        if urlsplit('http://'+host).hostname not in ('127.0.0.1','localhost','testserver'):
            return JSONResponse({'error':'Host no permitido.'},status_code=403)
        if request.method in ('POST','PUT','DELETE','PATCH'):
            origin=request.headers.get('origin')
            if origin and origin!=str(request.base_url).rstrip('/'):
                return JSONResponse({'error':'Origen no permitido.'},status_code=403)
            if request.method!='DELETE' and request.headers.get('content-type','').split(';')[0]!='application/json':
                return JSONResponse({'error':'Se requiere application/json.'},status_code=415)
            try:
                if int(request.headers.get('content-length','0'))>100000:
                    return JSONResponse({'error':'Solicitud demasiado grande.'},status_code=413)
            except ValueError:return JSONResponse({'error':'Longitud inválida.'},status_code=400)
        response=await call_next(request)
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'Referrer-Policy':'no-referrer','Server-Timing':f'app;dur={(time.perf_counter()-start)*1000:.1f}',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"})
        return response

    @api.exception_handler(ValueError)
    async def value_error(request,exc):return JSONResponse({'error':str(exc),'code':'invalid_input'},status_code=400)
    @api.exception_handler(RequestValidationError)
    async def schema_error(request,exc):return JSONResponse({'error':'Revisa los campos requeridos y sus tipos.','code':'invalid_input'},status_code=422)
    @api.exception_handler(HTTPException)
    async def http_error(request,exc):return JSONResponse({'error':exc.detail},status_code=exc.status_code)
    @api.exception_handler(ProviderError)
    async def provider_error(request,exc):return JSONResponse({'error':str(exc),'code':exc.code,'retryable':exc.retryable},status_code=503)
    @api.exception_handler(sqlite3.Error)
    async def db_error(request,exc):return JSONResponse({'error':'No se pudo guardar o leer el presupuesto. Vuelve a intentar.','code':'storage_error'},status_code=409)
    @api.exception_handler(TypeError)
    async def type_error(request,exc):return JSONResponse({'error':'Revisa los tipos de los datos enviados.','code':'invalid_input'},status_code=400)

    def session(request,required=True):
        sid=request.cookies.get('spendwise_session')
        state=sessions.get(sid)
        if state and time.monotonic()-state['touched']>TTL:
            api.state.jobs.clear_owner(sid)
            sessions.pop(sid,None);state=None
        if not state:
            if required:raise HTTPException(401,'La sesión expiró. Recarga la página.')
            return None,None
        state['touched']=time.monotonic()
        return sid,state

    def active(request):
        sid,state=session(request)
        if not state['profile']:raise HTTPException(401,'Selecciona un perfil primero.')
        return sid,{**state}

    def check_generation(sid,state):
        if sid not in sessions or sessions[sid]['generation']!=state['generation']:
            raise HTTPException(409,'El perfil cambió. Repite la operación en el perfil actual.')

    async def get_budget(identifier,profile):
        budget=await db.call(storage.get_budget,identifier,profile)
        if not budget:raise HTTPException(404,'Presupuesto no encontrado para este perfil.')
        return budget

    @api.get('/api/health')
    async def health():return {'status':'ok','version':'2.0.0'}

    @api.get('/api/config')
    async def config(request:Request,response:Response):
        sid,state=session(request,False)
        if not state:
            if len(sessions)>=200:raise HTTPException(503,'Demasiadas sesiones abiertas.')
            sid=secrets.token_urlsafe(32)
            state={'profile':None,'reviews':{},'touched':time.monotonic(),'generation':0}
            sessions[sid]=state
            response.set_cookie('spendwise_session',sid,httponly=True,samesite='strict',max_age=TTL)
        return {'live_available':bool(os.getenv('GEMINI_API_KEY')),'model':service.MODEL,
                'active_profile':state['profile'],'job_timeout_seconds':job_deadline}

    @api.get('/api/profiles')
    async def profiles():return {'profiles':await db.call(storage.list_profiles)}

    @api.post('/api/profiles',status_code=201)
    async def add_profile(payload:ProfileCreate,request:Request):
        session(request)
        name=payload.display_name.strip()
        if not name:raise ValueError('Indica el nombre del perfil.')
        def create(conn):
            from datetime import datetime,timezone
            identifier=secrets.token_hex(16)
            with conn:conn.execute('INSERT INTO profiles VALUES (?,?,?,?)',(identifier,name,'demo',datetime.now(timezone.utc).isoformat()))
            return storage.get_profile(conn,identifier)
        return {'profile':await db.call(create)}

    @api.post('/api/profile/select')
    async def select_profile(payload:ProfileSelect,request:Request):
        sid,state=session(request)
        profile=await db.call(storage.get_profile,payload.profile_id)
        if not profile:raise HTTPException(404,'Perfil no encontrado.')
        api.state.jobs.clear_owner(sid)
        state.update(profile=payload.profile_id,reviews={},generation=state['generation']+1)
        return {'profile':profile}

    @api.post('/api/extract',status_code=202)
    async def extract(payload:Extract,request:Request):
        sid,state=active(request)
        if not payload.consent:raise ValueError('Autoriza el envío del texto a Gemini.')
        if not payload.input.strip():raise ValueError('Escribe tus ingresos y gastos.')
        if not os.getenv('GEMINI_API_KEY') and provider is None:raise ProviderError('Configura Gemini con python app.py --ask-key.','missing_key')
        generation=state['generation']
        async def operation():
            raw,meta=await api.state.provider.generate(service.EXTRACTION_PROMPT,service.EXTRACTION_SCHEMA,
                        {'texto_no_confiable':payload.input},service.PROMPT_VERSION)
            review=service.prepare_review(raw,payload.input,meta)
            if sessions.get(sid,{}).get('generation')!=generation:raise ValueError('Cambió el perfil.')
            token=secrets.token_urlsafe(24)
            if len(state['reviews'])>=30:state['reviews'].pop(next(iter(state['reviews'])))
            state['reviews'][token]=review
            return {'token':token,**review}
        return api.state.jobs.submit(sid,'extract',payload.model_dump(),operation)

    @api.get('/api/jobs/{identifier}')
    async def job(identifier:str,request:Request):
        sid,_=session(request)
        result=api.state.jobs.get(identifier,sid)
        if not result:raise HTTPException(404,'Análisis no encontrado o expirado.')
        return result

    @api.delete('/api/jobs/{identifier}')
    async def cancel_job(identifier:str,request:Request):
        sid,_=session(request)
        if not api.state.jobs.cancel(identifier,sid):raise HTTPException(404,'Análisis no encontrado.')
        return {'cancelled':True}

    @api.post('/api/confirm')
    async def confirm(payload:dict,request:Request):
        _,state=active(request)
        review=state['reviews'].get(payload.get('token',''))
        if not review:raise HTTPException(410,'La revisión expiró o pertenece a otro perfil.')
        return service.confirm_review(review,payload)

    @api.post('/api/forget')
    async def forget(payload:dict,request:Request):
        sid,state=session(request)
        token=payload.get('token','')
        state['reviews'].pop(token,None)
        for identifier,job in list(api.state.jobs.jobs.items()):
            if job['owner']==sid and job.get('result') and job['result'].get('token')==token:
                api.state.jobs.cancel(identifier,sid)
                del api.state.jobs.jobs[identifier]
        return {'forgotten':True}

    @api.get('/api/budgets')
    async def budgets(request:Request):
        _,state=active(request)
        return {'budgets':await db.call(storage.list_budgets,state['profile'])}

    @api.get('/api/budgets/{identifier}')
    async def budget_detail(identifier:str,request:Request):
        _,state=active(request)
        budget=await get_budget(identifier,state['profile'])
        return {'budget':budget,'summary':summary(budget)}

    @api.post('/api/budgets',status_code=201)
    async def save_budget(payload:dict,request:Request):
        _,state=active(request)
        year,month=payload.get('year'),payload.get('month')
        if type(year) is not int or type(month) is not int or not 2000<=year<=2200 or not 1<=month<=12:raise ValueError('Periodo inválido.')
        moves=normalize_movements(payload.get('movements'))
        calculate_financials(payload.get('income'),[{'valor':m['amount'],'categoria':m['category']} for m in moves])
        mode=payload.get('source_mode','live')
        if mode not in ('live','manual'):raise ValueError('Solo se guardan presupuestos reales o manuales.')
        if type(payload.get('replace',False)) is not bool:raise ValueError('Confirma el reemplazo.')
        try:
            budget=await db.call(storage.save_budget,state['profile'],year,month,payload.get('income'),moves,mode,payload.get('replace',False))
        except FileExistsError as exc:raise HTTPException(409,str(exc)) from None
        return {'saved':True,'budget':budget}

    @api.put('/api/budgets/{identifier}')
    async def update_budget(identifier:str,payload:dict,request:Request):
        _,state=active(request)
        await get_budget(identifier,state['profile'])
        moves=normalize_movements(payload.get('movements'))
        calculate_financials(payload.get('income'),[{'valor':m['amount'],'categoria':m['category']} for m in moves])
        return {'updated':True,'budget':await db.call(storage.update_budget,identifier,state['profile'],payload.get('income'),moves)}

    @api.delete('/api/budgets/{identifier}')
    async def delete_budget(identifier:str,request:Request):
        _,state=active(request)
        if not await db.call(storage.delete_budget,identifier,state['profile']):raise HTTPException(404,'Presupuesto no encontrado.')
        return {'deleted':True}

    async def comparison_data(payload,state):
        a=await get_budget(payload.budget_a_id,state['profile'])
        b=await get_budget(payload.budget_b_id,state['profile'])
        return a,b,compare_budgets(a,b)

    @api.post('/api/compare')
    async def compare(payload:Compare,request:Request):
        _,state=active(request)
        a,b,result=await comparison_data(payload,state)
        return {'comparison':result}

    @api.post('/api/compare/explanation',status_code=202)
    async def explanation(payload:Compare,request:Request):
        sid,state=active(request)
        if not payload.consent:raise ValueError('Autoriza el envío a Gemini.')
        a,b,result=await comparison_data(payload,state)
        context=service.comparison_context(result,a['movements'],b['movements'])
        check_generation(sid,state)
        async def operation():
            raw,meta=await api.state.provider.generate(service.EXPLANATION_PROMPT,service.EXPLANATION_SCHEMA,context,service.EXPLANATION_PROMPT_VERSION)
            service._validate_explanation(raw,{m['id'] for m in a['movements']+b['movements']})
            return {'explanation':raw,'metadata':meta}
        return api.state.jobs.submit(sid,'explanation',context,operation)

    @api.post('/api/scenarios/interpret',status_code=202)
    async def interpret(payload:Scenario,request:Request):
        sid,state=active(request)
        if not payload.consent:raise ValueError('Autoriza el envío a Gemini.')
        if payload.type not in ('goal','event'):raise ValueError('Tipo inválido.')
        budget=await get_budget(payload.budget_id,state['profile'])
        check_generation(sid,state)
        totals=summary(budget)
        context={'texto_no_confiable':payload.text,'presupuesto_actual':totals}
        prefix='GOAL' if payload.type=='goal' else 'EVENT'
        async def operation():
            raw,meta=await api.state.provider.generate(getattr(service,prefix+'_PROMPT'),getattr(service,prefix+'_SCHEMA'),context,getattr(service,prefix+'_PROMPT_VERSION'))
            validate_scenario(raw,payload.type)
            return {'scenario':raw,'metadata':meta}
        return api.state.jobs.submit(sid,'scenario',{'type':payload.type,**context},operation)

    @api.post('/api/scenarios/calculate')
    async def calculate(payload:dict,request:Request):
        _,state=active(request)
        if payload.get('confirmed') is not True:raise ValueError('Confirma los supuestos del escenario.')
        budget=await get_budget(payload.get('budget_id'),state['profile'])
        totals=summary(budget)
        if payload.get('type')=='goal':
            reductions=payload.get('reductions',[])
            if not isinstance(reductions,list):raise ValueError('Reducciones inválidas.')
            indexed={m['id']:m for m in budget['movements']}
            seen=set();normalized=[]
            for r in reductions:
                identifier=r.get('movement_id')
                if identifier not in indexed or identifier in seen:raise ValueError('Movimiento desconocido o repetido.')
                seen.add(identifier);m=indexed[identifier]
                normalized.append({'description':m['description'],'category':m['category'],'current_amount':float(m['amount']),'reduce_by':r.get('reduce_by')})
            result=calculate_goal_scenario(totals['gasto_total'],totals['ingreso_total'],payload.get('target_amount'),normalized)
        elif payload.get('type')=='event':
            result=calculate_event_scenario(totals['ingreso_total'],totals['gasto_total'],payload.get('items'))
        else:raise ValueError('Tipo inválido.')
        return {'type':payload['type'],'result':result}

    def static(filename):
        async def serve():return FileResponse(ROOT/'web'/filename)
        return serve
    for path,name in {'/':'index.html','/app.js':'app.js','/api.js':'api.js','/styles.css':'styles.css','/pitch':'pitch.html','/pitch.js':'pitch.js','/pitch.css':'pitch.css'}.items():
        api.add_api_route(path,static(name),methods=['GET'],include_in_schema=False)
    return api

def validate_scenario(raw,kind):
    schema=service.GOAL_SCHEMA if kind=='goal' else service.EVENT_SCHEMA
    if not isinstance(raw,dict) or set(raw)!=set(schema['required']):raise ValueError('Escenario inválido.')
    if not isinstance(raw['questions'],list) or not all(isinstance(q,str) for q in raw['questions']):raise ValueError('Preguntas inválidas.')
    if kind=='goal':
        if raw['target_amount'] is not None and money(raw['target_amount'])<0:raise ValueError('Meta inválida.')
        if not isinstance(raw['protected_categories'],list) or any(c not in CATEGORIES for c in raw['protected_categories']):raise ValueError('Categorías inválidas.')
    else:
        if not isinstance(raw['name'],str) or not isinstance(raw['items'],list) or len(raw['items'])>50:raise ValueError('Evento inválido.')
        if raw['max_budget'] is not None and money(raw['max_budget'])<0:raise ValueError('Presupuesto inválido.')
        for item in raw['items']:
            if not isinstance(item,dict):raise ValueError('Rubro inválido.')
            if not isinstance(item.get('description'),str):raise ValueError('Rubro inválido.')
            if item.get('estimated_amount') is not None and money(item['estimated_amount'])<0:raise ValueError('Monto inválido.')
            item['confirmed']=False

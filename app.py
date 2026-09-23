"""Local SpendWise web app. Run: python app.py [--ask-key] [--port 8000]."""
import argparse
from getpass import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit
from evals.run_evals import load_cases, load_fixtures
from spendwise_service import (MODEL, ProviderError, call_gemini, prepare_review,
                               confirm_review, explain_comparison, interpret_goal,
                               interpret_event)
from spendwise_core import (money, CATEGORIES, calculate_financials,
                            calculate_goal_scenario, calculate_event_scenario)
import spendwise_storage as storage

ROOT=Path(__file__).resolve().parent
SESSIONS={}
PROFILE_SESSIONS={}  # token -> (monotonic_time, profile_id)
LOCK=threading.Lock()
TTL=1800
CASES={c['id']:c for c in load_cases()}
FIXTURES=load_fixtures()
DB_CONN=None  # Initialized in main()

def prune():
    now=time.monotonic()
    for token in list(SESSIONS):
        if now-SESSIONS[token][0]>TTL: del SESSIONS[token]
    for token in list(PROFILE_SESSIONS):
        if now-PROFILE_SESSIONS[token][0]>TTL: del PROFILE_SESSIONS[token]

def get_db():
    """Return the shared DB connection. Initialized at startup."""
    global DB_CONN
    if DB_CONN is None:
        DB_CONN = storage.get_connection()
        storage.initialize_database(DB_CONN)
    return DB_CONN

def _get_active_profile(handler):
    """Read profile session token from cookie and return profile_id or None."""
    cookie_header = handler.headers.get('Cookie', '')
    for part in cookie_header.split(';'):
        part = part.strip()
        if part.startswith('spendwise_profile='):
            token = part[len('spendwise_profile='):]
            with LOCK:
                entry = PROFILE_SESSIONS.get(token)
            if entry and (time.monotonic() - entry[0]) < TTL:
                return entry[1]
    return None

def _set_profile_cookie(handler, token):
    """Set HttpOnly, SameSite=Strict cookie for profile session."""
    handler.send_header('Set-Cookie',
        f'spendwise_profile={token}; HttpOnly; SameSite=Strict; Path=/')

def _parse_budget_id(path):
    """Extract budget ID from paths like /api/budgets/{id}. Returns id or None."""
    match = re.match(r'^/api/budgets/([a-f0-9-]{36})$', path)
    return match.group(1) if match else None


class Handler(BaseHTTPRequestHandler):
    server_version='SpendWiseLocal/1'
    def setup(self):
        super().setup()
        self.connection.settimeout(50)
    def log_message(self,*args):
        pass  # Never log financial inputs, session tokens or API keys.
    def respond(self,status,body,content_type='application/json; charset=utf-8',extra_headers=None):
        data=json.dumps(body,ensure_ascii=False,allow_nan=False).encode('utf-8') if content_type.startswith('application/json') else body
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if extra_headers:
            for key, value in extra_headers:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)
    def valid_host(self):
        port=self.server.server_port
        return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')

    def do_GET(self):
        if not self.valid_host(): return self.respond(403,{'error':'Host no permitido.'})
        path=urlsplit(self.path).path
        if path=='/api/config':
            profile_id = _get_active_profile(self)
            return self.respond(200,{'live_available':bool(os.getenv('GEMINI_API_KEY')),'model':MODEL,
                'active_profile': profile_id,
                'examples':[{'id':c['id'],'input':c['input']} for c in CASES.values()]})
        if path=='/api/profiles':
            profiles = storage.list_profiles(get_db())
            return self.respond(200, {'profiles': profiles})
        if path=='/api/budgets':
            profile_id = _get_active_profile(self)
            if not profile_id:
                return self.respond(401, {'error': 'Selecciona un perfil primero.'})
            budgets = storage.list_budgets(get_db(), profile_id)
            return self.respond(200, {'budgets': budgets})
        # GET /api/budgets/{id}
        budget_id = _parse_budget_id(path)
        if budget_id:
            profile_id = _get_active_profile(self)
            if not profile_id:
                return self.respond(401, {'error': 'Selecciona un perfil primero.'})
            budget = storage.get_budget(get_db(), budget_id, profile_id)
            if not budget:
                return self.respond(404, {'error': 'Presupuesto no encontrado.'})
            return self.respond(200, {'budget': budget})
        # Static files
        allowed={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css',
                 '/pitch':'pitch.html','/pitch.js':'pitch.js','/pitch.css':'pitch.css'}
        if path not in allowed: return self.respond(404,{'error':'No encontrado.'})
        file=ROOT/'web'/allowed[path]
        if not file.exists(): return self.respond(404,{'error':'No encontrado.'})
        mime={'.html':'text/html','.css':'text/css','.js':'text/javascript'}[file.suffix]
        self.respond(200,file.read_bytes(),mime+'; charset=utf-8')

    def do_DELETE(self):
        if not self.valid_host(): return self.respond(403,{'error':'Host no permitido.'})
        path=urlsplit(self.path).path
        budget_id = _parse_budget_id(path)
        if not budget_id:
            return self.respond(404, {'error': 'No encontrado.'})
        profile_id = _get_active_profile(self)
        if not profile_id:
            return self.respond(401, {'error': 'Selecciona un perfil primero.'})
        deleted = storage.delete_budget(get_db(), budget_id, profile_id)
        if not deleted:
            return self.respond(404, {'error': 'Presupuesto no encontrado.'})
        return self.respond(200, {'deleted': True})

    def do_POST(self):
        if not self.valid_host(): return self.respond(403,{'error':'Host no permitido.'})
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
            return self.respond(403,{'error':'Origen no permitido.'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.respond(415,{'error':'Se requiere application/json.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=100000: return self.respond(413,{'error':'Solicitud demasiado grande o vacia.'})
            payload=json.loads(self.rfile.read(length),parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Numero no finito.')))
            if not isinstance(payload,dict): raise ValueError('Se requiere un objeto JSON.')
            path=urlsplit(self.path).path

            # --- Profile selection ---
            if path=='/api/profile/select':
                profile_id = payload.get('profile_id')
                if not isinstance(profile_id, str):
                    raise ValueError('Selecciona un perfil válido.')
                profile = storage.get_profile(get_db(), profile_id)
                if not profile:
                    raise ValueError('Perfil no encontrado.')
                token = secrets.token_urlsafe(32)
                with LOCK:
                    # Clear old profile sessions and review sessions
                    old_profile = _get_active_profile(self)
                    if old_profile:
                        for t in list(SESSIONS):
                            pass  # Reviews persist across profile changes for simplicity
                    PROFILE_SESSIONS[token] = (time.monotonic(), profile_id)
                extra = [('Set-Cookie',
                    f'spendwise_profile={token}; HttpOnly; SameSite=Strict; Path=/')]
                return self.respond(200, {'profile': profile}, extra_headers=extra)

            # --- Original extraction flow ---
            if path=='/api/extract':
                text=payload.get('input')
                if not isinstance(text,str) or not text.strip() or len(text)>12000: raise ValueError('Ingresa entre 1 y 12000 caracteres.')
                mode=payload.get('mode')
                if mode=='fixture':
                    case=CASES.get(payload.get('case_id'))
                    if not case or text!=case['input']: raise ValueError('El ensayo solo admite los ejemplos predefinidos. Para texto propio usa Gemini.')
                    raw=FIXTURES[case['id']]
                    meta={'mode':'fixture','model':None,'label':'SIMULADO: extraccion preparada manualmente'}
                elif mode=='live':
                    if payload.get('consent') is not True: raise ValueError('Autoriza el envio del texto a Gemini.')
                    raw,meta=call_gemini(text)
                else: raise ValueError('Selecciona un modo valido.')
                review=prepare_review(raw,text,meta)
                token=secrets.token_urlsafe(32)
                with LOCK:
                    prune()
                    if len(SESSIONS)>=100: return self.respond(503,{'error':'Demasiadas revisiones abiertas. Reinicia o espera.'})
                    SESSIONS[token]=(time.monotonic(),review)
                return self.respond(200,{'token':token,**review})
            if path in ('/api/confirm','/api/forget'):
                token=payload.get('token')
                if not isinstance(token,str): raise ValueError('Sesion invalida.')
                with LOCK:
                    prune()
                    entry=SESSIONS.get(token)
                    if path=='/api/forget':
                        SESSIONS.pop(token,None)
                        return self.respond(200,{'forgotten':True})
                if entry is None: return self.respond(410,{'error':'La revision expiro. Vuelve a interpretar la entrada.'})
                result=confirm_review(entry[1],payload)
                return self.respond(200,result)

            # --- Budget persistence ---
            if path=='/api/budgets':
                profile_id = _get_active_profile(self)
                if not profile_id:
                    return self.respond(401, {'error': 'Selecciona un perfil primero.'})
                year = payload.get('year')
                month = payload.get('month')
                if not isinstance(year, int) or not isinstance(month, int):
                    raise ValueError('Año y mes son obligatorios.')
                if not (2000 <= year <= 2200) or not (1 <= month <= 12):
                    raise ValueError('Periodo inválido.')
                income = payload.get('income')
                movements = payload.get('movements')
                source_mode = payload.get('source_mode', 'manual')
                if source_mode not in ('live', 'fixture', 'manual'):
                    raise ValueError('Modo de origen inválido.')
                if not isinstance(movements, list) or not movements:
                    raise ValueError('Incluye al menos un movimiento.')
                # Validate movements
                for m in movements:
                    if not isinstance(m, dict):
                        raise ValueError('Movimiento inválido.')
                    if not isinstance(m.get('description', m.get('descripcion', '')), str):
                        raise ValueError('Descripción inválida.')
                # Normalize movement keys from frontend
                normalized_movements = []
                for m in movements:
                    desc = m.get('description', m.get('descripcion', ''))
                    amt = m.get('amount', m.get('valor'))
                    cat = m.get('category', m.get('categoria'))
                    if cat not in CATEGORIES:
                        raise ValueError(f'Categoría inválida: {cat}')
                    money(amt)  # Validate
                    normalized_movements.append({
                        'description': desc,
                        'amount': amt,
                        'category': cat,
                        'source_quote': m.get('source_quote', m.get('fuente')),
                        'origin': m.get('origin', 'interpreted'),
                    })
                # Check for existing budget
                replace = payload.get('replace', False)
                existing_id = storage.budget_exists(get_db(), profile_id, year, month)
                if existing_id and not replace:
                    return self.respond(409, {
                        'error': f'Ya existe un presupuesto para {year}-{month:02d}.',
                        'existing_id': existing_id,
                        'action_required': 'replace'
                    })
                if existing_id and replace:
                    storage.delete_budget(get_db(), existing_id, profile_id)
                try:
                    result = storage.create_budget(
                        get_db(), profile_id, year, month, income,
                        normalized_movements, source_mode
                    )
                except sqlite3.IntegrityError:
                    raise ValueError('No se pudo guardar: conflicto de datos.')
                return self.respond(201, {'budget': result, 'saved': True})

            # PUT /api/budgets/{id}
            budget_id = _parse_budget_id(path)
            if budget_id and self.command == 'POST':
                # We use POST with _method=PUT pattern since BaseHTTPRequestHandler
                # doesn't have do_PUT by default
                pass  # Handled below in the PUT section

            if path.startswith('/api/budgets/') and path.endswith('/update'):
                budget_id = path[len('/api/budgets/'):-len('/update')]
                if not re.match(r'^[a-f0-9-]{36}$', budget_id):
                    return self.respond(404, {'error': 'No encontrado.'})
                profile_id = _get_active_profile(self)
                if not profile_id:
                    return self.respond(401, {'error': 'Selecciona un perfil primero.'})
                income = payload.get('income')
                movements = payload.get('movements')
                if not isinstance(movements, list) or not movements:
                    raise ValueError('Incluye al menos un movimiento.')
                normalized_movements = []
                for m in movements:
                    desc = m.get('description', m.get('descripcion', ''))
                    amt = m.get('amount', m.get('valor'))
                    cat = m.get('category', m.get('categoria'))
                    if cat not in CATEGORIES:
                        raise ValueError(f'Categoría inválida: {cat}')
                    money(amt)
                    normalized_movements.append({
                        'description': desc,
                        'amount': amt,
                        'category': cat,
                        'source_quote': m.get('source_quote'),
                        'origin': m.get('origin', 'manual'),
                    })
                updated = storage.update_budget(get_db(), budget_id, profile_id,
                                                income, normalized_movements)
                if not updated:
                    return self.respond(404, {'error': 'Presupuesto no encontrado.'})
                return self.respond(200, {'budget': updated, 'updated': True})

            # --- Comparison ---
            if path=='/api/compare':
                profile_id = _get_active_profile(self)
                if not profile_id:
                    return self.respond(401, {'error': 'Selecciona un perfil primero.'})
                budget_a_id = payload.get('budget_a_id')
                budget_b_id = payload.get('budget_b_id')
                if not isinstance(budget_a_id, str) or not isinstance(budget_b_id, str):
                    raise ValueError('Selecciona dos presupuestos para comparar.')
                budget_a = storage.get_budget(get_db(), budget_a_id, profile_id)
                budget_b = storage.get_budget(get_db(), budget_b_id, profile_id)
                if not budget_a or not budget_b:
                    return self.respond(404, {'error': 'Uno o ambos presupuestos no existen.'})
                from spendwise_compare import compare_budgets
                comparison = compare_budgets(budget_a, budget_b)
                return self.respond(200, {'comparison': comparison})

            if path=='/api/compare/explanation':
                profile_id = _get_active_profile(self)
                if not profile_id:
                    return self.respond(401, {'error': 'Selecciona un perfil primero.'})
                if payload.get('consent') is not True:
                    raise ValueError('Autoriza el envío de datos a Gemini para la explicación.')
                comparison = payload.get('comparison')
                budget_a_id = payload.get('budget_a_id')
                budget_b_id = payload.get('budget_b_id')
                if not comparison or not budget_a_id or not budget_b_id:
                    raise ValueError('Faltan datos de comparación.')
                budget_a = storage.get_budget(get_db(), budget_a_id, profile_id)
                budget_b = storage.get_budget(get_db(), budget_b_id, profile_id)
                if not budget_a or not budget_b:
                    return self.respond(404, {'error': 'Presupuestos no encontrados.'})
                explanation, meta = explain_comparison(
                    comparison, budget_a['movements'], budget_b['movements'])
                return self.respond(200, {'explanation': explanation, 'metadata': meta})

            # --- Scenarios ---
            if path=='/api/scenarios/interpret':
                profile_id = _get_active_profile(self)
                if not profile_id:
                    return self.respond(401, {'error': 'Selecciona un perfil primero.'})
                if payload.get('consent') is not True:
                    raise ValueError('Autoriza el envío de datos a Gemini.')
                text = payload.get('text', '')
                if not isinstance(text, str) or not text.strip():
                    raise ValueError('Describe tu meta o evento.')
                scenario_type = payload.get('type', 'goal')
                budget_id = payload.get('budget_id')
                budget_summary = {}
                if budget_id:
                    budget = storage.get_budget(get_db(), budget_id, profile_id)
                    if budget:
                        movs = budget.get('movements', [])
                        expense = sum(float(m['amount']) for m in movs)
                        cats = {}
                        for m in movs:
                            cats[m['category']] = cats.get(m['category'], 0) + float(m['amount'])
                        inc = float(budget['income']) if budget.get('income') else None
                        budget_summary = {
                            'income': inc,
                            'expense': expense,
                            'balance': (inc - expense) if inc is not None else None,
                            'categories': cats,
                        }
                if scenario_type == 'goal':
                    result, meta = interpret_goal(text, budget_summary)
                elif scenario_type == 'event':
                    result, meta = interpret_event(text, budget_summary)
                else:
                    raise ValueError('Tipo de escenario inválido: usa "goal" o "event".')
                return self.respond(200, {'scenario': result, 'metadata': meta})

            if path=='/api/scenarios/calculate':
                scenario_type = payload.get('type')
                if scenario_type == 'goal':
                    budget_expense = payload.get('budget_expense', 0)
                    budget_income = payload.get('budget_income')
                    target_amount = payload.get('target_amount')
                    reductions = payload.get('reductions', [])
                    if target_amount is None:
                        raise ValueError('Indica el monto objetivo.')
                    result = calculate_goal_scenario(
                        budget_expense, budget_income, target_amount, reductions)
                    return self.respond(200, {'result': result, 'type': 'goal'})
                elif scenario_type == 'event':
                    budget_income = payload.get('budget_income')
                    budget_expense = payload.get('budget_expense', 0)
                    event_items = payload.get('items', [])
                    result = calculate_event_scenario(
                        budget_income, budget_expense, event_items)
                    return self.respond(200, {'result': result, 'type': 'event'})
                else:
                    raise ValueError('Tipo de escenario inválido.')

            return self.respond(404,{'error':'No encontrado.'})
        except ProviderError as exc:
            return self.respond(502,{'error':str(exc)})
        except (ValueError,TypeError,KeyError,UnicodeError) as exc:
            return self.respond(400,{'error':str(exc)})
        except Exception:
            return self.respond(500,{'error':'No fue posible procesar la solicitud. No se genero un presupuesto.'})

    def do_PUT(self):
        """Handle PUT /api/budgets/{id} for updates."""
        if not self.valid_host(): return self.respond(403,{'error':'Host no permitido.'})
        path=urlsplit(self.path).path
        budget_id = _parse_budget_id(path)
        if not budget_id:
            return self.respond(404, {'error': 'No encontrado.'})
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':
            return self.respond(415,{'error':'Se requiere application/json.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=100000: return self.respond(413,{'error':'Solicitud demasiado grande.'})
            payload=json.loads(self.rfile.read(length))
            if not isinstance(payload,dict): raise ValueError('Se requiere un objeto JSON.')
            profile_id = _get_active_profile(self)
            if not profile_id:
                return self.respond(401, {'error': 'Selecciona un perfil primero.'})
            income = payload.get('income')
            movements = payload.get('movements')
            if not isinstance(movements, list) or not movements:
                raise ValueError('Incluye al menos un movimiento.')
            normalized = []
            for m in movements:
                desc = m.get('description', m.get('descripcion', ''))
                amt = m.get('amount', m.get('valor'))
                cat = m.get('category', m.get('categoria'))
                if cat not in CATEGORIES:
                    raise ValueError(f'Categoría inválida: {cat}')
                money(amt)
                normalized.append({
                    'description': desc, 'amount': amt, 'category': cat,
                    'source_quote': m.get('source_quote'),
                    'origin': m.get('origin', 'manual'),
                })
            updated = storage.update_budget(get_db(), budget_id, profile_id, income, normalized)
            if not updated:
                return self.respond(404, {'error': 'Presupuesto no encontrado.'})
            return self.respond(200, {'budget': updated, 'updated': True})
        except (ValueError,TypeError,KeyError) as exc:
            return self.respond(400,{'error':str(exc)})
        except Exception:
            return self.respond(500,{'error':'No fue posible procesar la solicitud.'})


class LocalServer(ThreadingHTTPServer):
    daemon_threads=True
    def service_actions(self):
        with LOCK: prune()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--ask-key',action='store_true')
    args=parser.parse_args()
    if args.ask_key: os.environ['GEMINI_API_KEY']=getpass('Gemini API key (oculta): ').strip()
    # Initialize database
    global DB_CONN
    DB_CONN = storage.get_connection()
    storage.initialize_database(DB_CONN)
    server=LocalServer(('127.0.0.1',args.port),Handler)
    print(f'SpendWise AI: http://127.0.0.1:{server.server_port} | Pitch: /pitch',flush=True)
    print(f'DB: {storage._db_path()}',flush=True)
    print('Gemini listo.' if os.getenv('GEMINI_API_KEY') else 'Modo ensayo disponible. Gemini requiere GEMINI_API_KEY.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        server.server_close()
        if DB_CONN:
            DB_CONN.close()

if __name__=='__main__': main()

import asyncio
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from spendwise_api import create_app
from spendwise_jobs import JobManager
from spendwise_provider import GeminiClient, ProviderError
from evals.run_evals import load_cases, load_fixtures

CASE=load_cases()[0]
RAW=load_fixtures()[CASE['id']]

class FakeProvider:
    def __init__(self,delay=0):self.delay=delay;self.calls=0;self.cancelled=0
    async def close(self):pass
    async def generate(self,prompt,schema,context,version):
        self.calls+=1
        try:await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled+=1;raise
        if 'goal' in version:result={'target_amount':100,'period':'mensual','protected_categories':[],'preferences':[],'questions':[]}
        elif 'event' in version:result={'name':'Viaje','date':None,'max_budget':300,'items':[{'description':'Bus','estimated_amount':100,'source':'Usuario','confirmed':False}],'questions':[]}
        elif 'explanation' in version:result={'observaciones':[],'limitaciones':['Prueba con proveedor simulado.']}
        else:result=copy.deepcopy(RAW)
        return result,{'mode':'live','model':'TEST DOUBLE','prompt_version':version}

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.provider=FakeProvider()
        self.application=create_app(str(Path(self.temp.name)/'test.db'),self.provider)
        self.client=TestClient(self.application).__enter__()
        self.client.get('/api/config')
        self.select('demo-ana-001')
    def tearDown(self):
        self.client.__exit__(None,None,None);self.temp.cleanup()
    def select(self,identifier):
        response=self.client.post('/api/profile/select',json={'profile_id':identifier})
        self.assertEqual(response.status_code,200,response.text)
    def extract(self):
        r=self.client.post('/api/extract',json={'input':CASE['input'],'consent':True})
        self.assertEqual(r.status_code,202,r.text)
        return r.json()['id']
    def wait(self,identifier):
        for _ in range(200):
            job=self.client.get('/api/jobs/'+identifier).json()
            if job.get('status') in ('done','error','cancelled'):return job
            time.sleep(.01)
        self.fail('Job did not finish')
    def budget(self,month=1):
        payload={'year':2026,'month':month,'income':1000,'source_mode':'live',
                 'movements':[{'description':'Mercado','amount':200,'category':'alimentacion','origin':'interpreted'}]}
        result=self.client.post('/api/budgets',json=payload)
        self.assertEqual(result.status_code,201,result.text)
        return result.json()['budget']['id']
    def test_repeat_profile_switch_never_deadlocks(self):
        timings=[]
        for _ in range(10):
            for identifier in ('demo-carlos-002','demo-ana-001'):
                start=time.perf_counter();self.select(identifier);timings.append(time.perf_counter()-start)
                self.assertEqual(self.client.get('/api/health').status_code,200)
        self.assertLess(max(timings),.5)
    def test_slow_ai_does_not_block_profiles_history_or_health(self):
        self.provider.delay=2
        start=time.perf_counter();identifier=self.extract()
        self.assertLess(time.perf_counter()-start,.5)
        for url in ('/api/profiles','/api/budgets','/api/health'):
            start=time.perf_counter();self.assertEqual(self.client.get(url).status_code,200)
            self.assertLess(time.perf_counter()-start,.5)
        self.select('demo-carlos-002')
        self.assertEqual(self.client.get('/api/jobs/'+identifier).status_code,404)
    def test_extraction_review_confirmation(self):
        job=self.wait(self.extract());self.assertEqual(job['status'],'done',job)
        review=job['result']
        payload={'token':review['token'],'confirmed':True,'ingreso_total':review['ingreso_total'],
                 'movimientos':review['movimientos'],'selected_ids':['m3']}
        r=self.client.post('/api/confirm',json=payload)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['output']['ahorro_potencial'],30000)
        payload['confirmed']=False
        self.assertEqual(self.client.post('/api/confirm',json=payload).status_code,400)
        self.select('demo-carlos-002')
        self.assertEqual(self.client.post('/api/confirm',json=payload).status_code,410)
    def test_identical_requests_deduplicate(self):
        one=self.extract();self.wait(one);two=self.extract()
        self.assertEqual(one,two);self.assertEqual(self.provider.calls,1)
    def test_forgetting_review_invalidates_cached_job(self):
        first=self.extract();review=self.wait(first)['result']
        self.assertEqual(self.client.post('/api/forget',json={'token':review['token']}).status_code,200)
        second=self.extract()
        self.assertNotEqual(first,second)
        self.assertEqual(self.wait(second)['status'],'done')
    def test_create_profile_and_update_stored_budget(self):
        response=self.client.post('/api/profiles',json={'display_name':'Mi perfil'})
        self.assertEqual(response.status_code,201,response.text)
        self.select(response.json()['profile']['id'])
        identifier=self.budget()
        response=self.client.put('/api/budgets/'+identifier,json={'income':1200,'movements':[{'description':'Bus','amount':50,'category':'transporte'}]})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/budgets/'+identifier).json()['summary']['saldo_disponible'],1150)
    def test_cancel(self):
        self.provider.delay=2;identifier=self.extract()
        self.assertEqual(self.client.delete('/api/jobs/'+identifier).status_code,200)
        self.assertEqual(self.wait(identifier)['status'],'cancelled')
    def test_job_access_other_session(self):
        identifier=self.extract();self.client.cookies.clear();self.client.get('/api/config')
        self.assertEqual(self.client.get('/api/jobs/'+identifier).status_code,404)
    def test_persistence_and_atomic_replacement(self):
        identifier=self.budget()
        bad={'year':2026,'month':1,'income':1000,'source_mode':'live','replace':True,
             'movements':[{'description':'bad','amount':-20,'category':'otros'}]}
        self.assertEqual(self.client.post('/api/budgets',json=bad).status_code,400)
        detail=self.client.get('/api/budgets/'+identifier).json()
        self.assertEqual(detail['summary']['gasto_total'],200)
        bad['movements'][0]['amount']=300
        self.assertEqual(self.client.post('/api/budgets',json=bad).json()['budget']['id'],identifier)
        self.assertEqual(self.client.get('/api/budgets/'+identifier).json()['summary']['gasto_total'],300)
    def test_cross_profile_budget_access(self):
        identifier=self.budget();self.select('demo-carlos-002')
        self.assertEqual(self.client.get('/api/budgets/'+identifier).status_code,404)
        self.assertEqual(self.client.delete('/api/budgets/'+identifier).status_code,404)
        self.assertEqual(self.client.get('/api/budgets').json()['budgets'],[])
    def test_comparison_and_explanation(self):
        a,b=self.budget(1),self.budget(2)
        payload={'budget_a_id':a,'budget_b_id':b,'consent':True}
        self.assertEqual(self.client.post('/api/compare',json=payload).json()['comparison']['expense_diff'],0)
        response=self.client.post('/api/compare/explanation',json=payload)
        self.assertEqual(response.status_code,202,response.text)
        self.assertEqual(self.wait(response.json()['id'])['status'],'done')
    def test_goal_uses_stored_values_and_user_reductions(self):
        identifier=self.budget()
        mov=self.client.get('/api/budgets/'+identifier).json()['budget']['movements'][0]
        payload={'type':'goal','budget_id':identifier,'target_amount':100,'confirmed':True,
                 'reductions':[{'movement_id':mov['id'],'reduce_by':100}]}
        r=self.client.post('/api/scenarios/calculate',json=payload)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()['result']['new_balance'],900)
        self.assertTrue(r.json()['result']['reached_target'])
        payload['reductions'][0]['reduce_by']=300
        self.assertEqual(self.client.post('/api/scenarios/calculate',json=payload).status_code,400)
    def test_event_missing_amount_is_not_zero(self):
        identifier=self.budget()
        payload={'type':'event','budget_id':identifier,'confirmed':True,
                 'items':[{'description':'Bus','estimated_amount':None}]}
        self.assertEqual(self.client.post('/api/scenarios/calculate',json=payload).status_code,400)
        payload['items'][0]['estimated_amount']=100
        self.assertEqual(self.client.post('/api/scenarios/calculate',json=payload).json()['result']['remaining_after_event'],700)
    def test_scenario_interpretations(self):
        identifier=self.budget()
        for kind in ('goal','event'):
            r=self.client.post('/api/scenarios/interpret',json={'type':kind,'budget_id':identifier,'text':'Mi plan','consent':True})
            self.assertEqual(r.status_code,202,r.text)
            self.assertEqual(self.wait(r.json()['id'])['status'],'done')
    def test_no_fixtures_in_production(self):
        self.assertNotIn('examples',self.client.get('/api/config').json())
        response=self.client.post('/api/extract',json={'input':'text','consent':True,'mode':'fixture'})
        self.assertEqual(response.status_code,422)
        self.assertNotIn('id="example"',self.client.get('/').text)
    def test_static_and_origin_checks(self):
        for path in ('/','/api.js','/app.js','/styles.css','/pitch','/openapi.json'):
            self.assertEqual(self.client.get(path).status_code,200)
        for method,path in [('post','/api/profile/select'),('put','/api/budgets/fake'),('delete','/api/budgets/fake')]:
            kwargs={'headers':{'Origin':'https://example.com'}}
            if method!='delete':kwargs['json']={}
            self.assertEqual(getattr(self.client,method)(path,**kwargs).status_code,403)
        for path in ('/.env','/app.py','/../README.md'):
            self.assertEqual(self.client.get(path).status_code,404)

class JobTests(unittest.IsolatedAsyncioTestCase):
    async def test_deadline_and_recovery(self):
        manager=JobManager(deadline=.02)
        async def slow():await asyncio.sleep(1)
        job=manager.submit('owner','slow',{},slow)
        await asyncio.sleep(.05)
        self.assertEqual(manager.get(job['id'],'owner')['error']['code'],'job_timeout')
        async def fast():return {'ok':True}
        next_job=manager.submit('owner','fast',{},fast)
        await asyncio.sleep(.01)
        self.assertEqual(manager.get(next_job['id'],'owner')['status'],'done')
        await manager.close()
    async def test_queue_bounded(self):
        manager=JobManager(capacity=1)
        async def slow():await asyncio.sleep(1)
        manager.submit('one','x',{},slow)
        with self.assertRaises(ProviderError):manager.submit('two','x',{},slow)
        await manager.close()

class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_internal_error_retried_once_in_both_clients(self):
        from spendwise_provider import generate_sync
        for status in (500, 503):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status)
            client = GeminiClient('test', httpx.MockTransport(handler))
            try:
                with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-only'}), patch('spendwise_provider.asyncio.sleep'), self.assertRaises(ProviderError) as caught:
                    await client.generate('p', {}, 'x', 'v')
                self.assertEqual(len(calls), 2)
                self.assertEqual(caught.exception.code, f'gemini_{status}')
                self.assertTrue(caught.exception.retryable)
            finally:
                await client.close()
            calls.clear()
            with httpx.Client(transport=httpx.MockTransport(handler)) as sync_client:
                with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-only'}), patch('spendwise_provider.httpx.Client', return_value=sync_client), patch('spendwise_provider.time.sleep'), self.assertRaises(ProviderError) as caught:
                    generate_sync('p', {}, 'x', 'v', 'test')
                self.assertEqual(len(calls), 2)
                self.assertEqual(caught.exception.code, f'gemini_{status}')

    async def test_structured_success_and_single_retry(self):
        calls=[]
        def handler(request):
            calls.append(request)
            if len(calls)==1:return httpx.Response(503)
            return httpx.Response(200,json={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"ok":true}'}]}}]})
        client=GeminiClient('test',httpx.MockTransport(handler))
        try:
            with patch.dict('os.environ',{'GEMINI_API_KEY':'test-only'}):
                result,meta=await client.generate('prompt',{},'input','v1')
            self.assertTrue(result['ok']);self.assertEqual(meta['attempts'],2)
        finally:await client.close()
    async def test_quota_not_retried_and_timeout_is_specific(self):
        for status,code in [(429,'gemini_429'),(401,'gemini_401')]:
            client=GeminiClient('test',httpx.MockTransport(lambda r:httpx.Response(status)))
            try:
                with patch.dict('os.environ',{'GEMINI_API_KEY':'test-only'}),self.assertRaises(ProviderError) as exc:
                    await client.generate('p',{},'x','v')
                self.assertEqual(exc.exception.code,code)
            finally:await client.close()
        def timeout(r):raise httpx.ReadTimeout('private details')
        client=GeminiClient('test',httpx.MockTransport(timeout))
        try:
            with patch.dict('os.environ',{'GEMINI_API_KEY':'test-only'}),self.assertRaises(ProviderError) as exc:
                await client.generate('p',{},'x','v')
            self.assertEqual(exc.exception.code,'read_timeout')
        finally:await client.close()

    async def test_transport_diagnostics_do_not_expose_private_details(self):
        cases = [(httpx.ConnectTimeout, 'connect_timeout'),
                 (httpx.ReadTimeout, 'read_timeout'),
                 (httpx.WriteTimeout, 'write_timeout'),
                 (httpx.PoolTimeout, 'pool_timeout'),
                 (httpx.ConnectError, 'connection_error')]
        for error_type, code in cases:
            with self.subTest(code=code):
                def fail(request):
                    raise error_type('SECRET_KEY PRIVATE_EXPENSE')
                client = GeminiClient('test', httpx.MockTransport(fail))
                try:
                    with patch.dict('os.environ', {'GEMINI_API_KEY': 'SECRET_KEY'}), self.assertLogs('spendwise_provider', level='WARNING') as logs:
                        with self.assertRaises(ProviderError) as caught:
                            await client.generate('prompt', {}, 'PRIVATE_EXPENSE', 'v1')
                    self.assertEqual(caught.exception.code, code)
                    diagnostic = str(caught.exception) + ' '.join(logs.output)
                    self.assertIn('code=' + code, diagnostic)
                    self.assertNotIn('SECRET_KEY', diagnostic)
                    self.assertNotIn('PRIVATE_EXPENSE', diagnostic)
                finally:
                    await client.close()

if __name__=='__main__':unittest.main()

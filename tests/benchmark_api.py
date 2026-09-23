"""Local latency evidence with a delayed test provider, never a Gemini speed claim."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import threading
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from spendwise_api import create_app
from test_api import FakeProvider,CASE

def baseline_deadlock():
    source=subprocess.check_output(['git','show','HEAD:app.py'],cwd=ROOT,text=True,encoding='utf-8')
    tree=ast.parse(source)
    function=next((node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='_get_active_profile'),None)
    if function is None:return {'reproduced':None,'reason':'HEAD no longer contains the old implementation'}
    namespace={'LOCK':threading.Lock(),'PROFILE_SESSIONS':{'token':(time.monotonic(),'profile')},'TTL':1800,'time':time}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'baseline','exec'),namespace)
    class Handler:headers={'Cookie':'spendwise_profile=token'}
    def select():
        # Exact nested lock pattern found in the former profile/select route.
        with namespace['LOCK']:namespace['_get_active_profile'](Handler())
    worker=threading.Thread(target=select,daemon=True);worker.start();worker.join(.25)
    return {'reproduced':worker.is_alive(),'observation_window_ms':250,'pattern':'LOCK held by select -> _get_active_profile acquires the same non-reentrant LOCK'}

def main():
    timings={'profile_select_ms':[],'history_during_ai_ms':[],'health_during_ai_ms':[]}
    provider=FakeProvider(2)
    with tempfile.TemporaryDirectory() as folder:
        with TestClient(create_app(str(Path(folder)/'test.db'),provider)) as client:
            client.get('/api/config')
            for _ in range(15):
                for profile in ('demo-ana-001','demo-carlos-002'):
                    start=time.perf_counter()
                    response=client.post('/api/profile/select',json={'profile_id':profile})
                    assert response.status_code==200
                    timings['profile_select_ms'].append((time.perf_counter()-start)*1000)
            start=time.perf_counter()
            response=client.post('/api/extract',json={'input':CASE['input'],'consent':True})
            accepted_ms=(time.perf_counter()-start)*1000
            assert response.status_code==202
            job=response.json()['id']
            for _ in range(15):
                for key,path in [('history_during_ai_ms','/api/budgets'),('health_during_ai_ms','/api/health')]:
                    start=time.perf_counter();r=client.get(path);assert r.status_code==200
                    timings[key].append((time.perf_counter()-start)*1000)
            client.delete('/api/jobs/'+job)
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'mode':'in-process HTTP test client, temporary SQLite, provider delayed 2 seconds; NOT real Gemini latency',
            'baseline':baseline_deadlock(),'job_accepted_ms':round(accepted_ms,2),
            'measurements':{key:{'samples':len(v),'median_ms':round(statistics.median(v),2),'p95_ms':round(sorted(v)[int((len(v)-1)*.95)],2),'max_ms':round(max(v),2)} for key,v in timings.items()},
            'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('spendwise_*.py')}}
    (ROOT/'evals/performance_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))

if __name__=='__main__':main()

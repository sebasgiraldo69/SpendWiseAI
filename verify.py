"""Reproduce local technical gates; external gates remain explicitly pending."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from evals.run_evals import run_suite

ROOT=Path(__file__).resolve().parent

def main():
    tests=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd=ROOT,capture_output=True,text=True)
    suite=run_suite()
    (ROOT/'evals/offline_report.json').write_text(json.dumps(suite,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    test_pass=tests.returncode==0
    offline_pass=suite['passed']==suite['total']
    gates=[{'id':'T1','name':'Contrato y calculos','status':'PASS' if test_pass else 'FAIL'},
           {'id':'T2','name':'Incertidumbre y revision humana','status':'PASS' if test_pass and offline_pass else 'FAIL'},
           {'id':'T3','name':'Errores de proveedor y controles HTTP','status':'PASS' if test_pass else 'FAIL'},
           {'id':'T4','name':'Regresion con fixtures','status':'PASS' if offline_pass else 'FAIL'},
           {'id':'E1','name':'Calidad actual de Gemini: 33/33 y cero fallos criticos','status':'PENDING'},
           {'id':'E2','name':'Validacion con usuarios reales','status':'PENDING'},
           {'id':'E3','name':'Correspondencia con rubrica oficial','status':'PENDING'}]
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'Gates propuestos por el equipo. No equivalen a aprobacion oficial.',
            'technical_pass':test_pass and offline_pass,'all_gates_pass':False,
            'unit_test_output':tests.stdout+tests.stderr,'offline_score':f"{suite['passed']}/{suite['total']}",
            'gates':gates,'source_sha256':{**suite['source_sha256'],
                **{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in [ROOT/'app.py',ROOT/'verify.py',*sorted(ROOT.glob('spendwise_*.py')),*sorted((ROOT/'tests').glob('test_*.py')),*sorted((ROOT/'web').glob('*'))]}}}
    (ROOT/'evals/gates_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(tests.stdout+tests.stderr)
    print('Offline:',report['offline_score'])
    print('Gates tecnicos:', 'PASS' if report['technical_pass'] else 'FAIL')
    print('Gates externos: PENDING. Ver evals/gates_report.json')
    return 0 if report['technical_pass'] else 1

if __name__=='__main__':raise SystemExit(main())

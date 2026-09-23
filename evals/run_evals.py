"""python -m evals.run_evals [--live --repeat 3] [--output path.json]"""
import argparse
from getpass import getpass
import os
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from spendwise_core import evaluate_expected
from spendwise_service import prepare_review, call_gemini, MODEL, PROMPT_VERSION

ROOT = Path(__file__).resolve().parents[1]

def load_cases():
    return json.loads((ROOT/'evals/eval_cases.json').read_text(encoding='utf-8'))

def load_fixtures():
    return json.loads((ROOT/'evals/extraction_fixtures.json').read_text(encoding='utf-8'))['cases']

def signatures(review):
    # Full inventory, including excluded movements. A coincident total cannot hide omissions.
    return Counter((m['valor'], m['categoria'], m['moneda'], m['tipo']) for m in review['movimientos'])

def run_suite(live=False, repeat=1):
    cases, fixtures = load_cases(), load_fixtures()
    results=[]
    for iteration in range(repeat):
        for case in cases:
            start=time.perf_counter()
            try:
                if live:
                    raw,metadata=call_gemini(case['input'])
                else:
                    raw,metadata=fixtures[case['id']],{'mode':'fixture','model':None,'prompt_version':PROMPT_VERSION}
                review=prepare_review(raw,case['input'],metadata)
                reference=prepare_review(fixtures[case['id']],case['input'])
                inventory_ok=signatures(review)==signatures(reference)
                issues=[i['codigo'] for i in review['incidencias']]
                trace={'movements_match_reference':inventory_ok, 'issues':issues,
                       'requires_confirmation':review['requires_confirmation'],
                       'recommendation_policy':'user_scenario_only'}
                errors=evaluate_expected(review['preview'],case['expected'],trace)
                if not inventory_ok: errors.append('Inventario de movimientos distinto de la referencia manual.')
                if review['ingreso_total'] != reference['ingreso_total']: errors.append('Ingreso distinto de la referencia.')
                if review['preview']['gasto_total'] != reference['preview']['gasto_total']: errors.append('Gasto distinto de la referencia.')
                results.append({'case':case['id'],'iteration':iteration+1,'status':'FAIL' if errors else 'PASS',
                                'errors':errors,'trace':trace,'raw_extraction':raw,'output':review['preview'],
                                'metadata':metadata,'latency_ms':round((time.perf_counter()-start)*1000)})
            except Exception as exc:
                results.append({'case':case['id'],'iteration':iteration+1,'status':'ERROR','errors':[str(exc)]})
            if live: time.sleep(1)
    paths=['spendwise_core.py','spendwise_service.py','spendwise_provider.py','evals/run_evals.py','evals/eval_cases.json','evals/extraction_fixtures.json']
    return {'timestamp_utc':datetime.now(timezone.utc).isoformat(),'mode':'live' if live else 'fixture',
            'meaning':'Real Gemini extraction + deterministic checks' if live else 'Software checks with hand-annotated extraction; does NOT measure Gemini quality',
            'model':MODEL if live else None,'prompt_version':PROMPT_VERSION,'repeat':repeat,
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
            'passed':sum(r['status']=='PASS' for r in results),'total':len(results),'results':results}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--ask-key',action='store_true',help='Solicitar clave oculta, sin guardarla')
    parser.add_argument('--repeat',type=int,default=1)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not 1<=args.repeat<=10: parser.error('--repeat debe estar entre 1 y 10')
    if args.ask_key: os.environ['GEMINI_API_KEY']=getpass('Gemini API key (oculta): ').strip()
    if args.live and not os.getenv('GEMINI_API_KEY'): parser.error('Configura GEMINI_API_KEY o usa --ask-key para evals reales.')
    report=run_suite(args.live,args.repeat)
    target=args.output or ROOT/'evals/runs'/('live.json' if args.live else 'offline.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(f"{report['mode']}: {report['passed']}/{report['total']} | {target}")
    for result in report['results']:
        if result['status']!='PASS': print(result['case'],result['errors'])
    return 0 if report['passed']==report['total'] else 1

if __name__=='__main__':
    raise SystemExit(main())

"""Local SpendWise web app. Run: python app.py [--ask-key] [--port 8000]."""
import argparse
from getpass import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from urllib.parse import urlsplit
from evals.run_evals import load_cases, load_fixtures
from spendwise_service import MODEL, ProviderError, call_gemini, prepare_review, confirm_review

ROOT=Path(__file__).resolve().parent
SESSIONS={}
LOCK=threading.Lock()
TTL=1800
CASES={c['id']:c for c in load_cases()}
FIXTURES=load_fixtures()

def prune():
    now=time.monotonic()
    for token in list(SESSIONS):
        if now-SESSIONS[token][0]>TTL: del SESSIONS[token]

class Handler(BaseHTTPRequestHandler):
    server_version='SpendWiseLocal/1'
    def setup(self):
        super().setup()
        self.connection.settimeout(50)
    def log_message(self,*args):
        pass  # Never log financial inputs, session tokens or API keys.
    def respond(self,status,body,content_type='application/json; charset=utf-8'):
        data=json.dumps(body,ensure_ascii=False,allow_nan=False).encode('utf-8') if content_type.startswith('application/json') else body
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)
    def valid_host(self):
        port=self.server.server_port
        return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')
    def do_GET(self):
        if not self.valid_host(): return self.respond(403,{'error':'Host no permitido.'})
        path=urlsplit(self.path).path
        if path=='/api/config':
            return self.respond(200,{'live_available':bool(os.getenv('GEMINI_API_KEY')),'model':MODEL,
                'examples':[{'id':c['id'],'input':c['input']} for c in CASES.values()]})
        allowed={'/':'index.html','/app.js':'app.js','/styles.css':'styles.css',
                 '/pitch':'pitch.html','/pitch.js':'pitch.js','/pitch.css':'pitch.css'}
        if path not in allowed: return self.respond(404,{'error':'No encontrado.'})
        file=ROOT/'web'/allowed[path]
        if not file.exists(): return self.respond(404,{'error':'No encontrado.'})
        mime={'.html':'text/html','.css':'text/css','.js':'text/javascript'}[file.suffix]
        self.respond(200,file.read_bytes(),mime+'; charset=utf-8')
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
            return self.respond(404,{'error':'No encontrado.'})
        except ProviderError as exc:
            return self.respond(502,{'error':str(exc)})
        except (ValueError,TypeError,KeyError,UnicodeError) as exc:
            return self.respond(400,{'error':str(exc)})
        except Exception:
            return self.respond(500,{'error':'No fue posible procesar la solicitud. No se genero un presupuesto.'})

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
    server=LocalServer(('127.0.0.1',args.port),Handler)
    print(f'SpendWise AI: http://127.0.0.1:{server.server_port} | Pitch: /pitch',flush=True)
    print('Gemini listo.' if os.getenv('GEMINI_API_KEY') else 'Modo ensayo disponible. Gemini requiere GEMINI_API_KEY.',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()

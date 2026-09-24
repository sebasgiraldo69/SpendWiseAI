"""Browser check with mocked API responses; does not call Gemini or use saved data."""
from pathlib import Path
import json
import socket
import sys
import threading
import time
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.append(str(ROOT/'.tmp-tools'))
import uvicorn
from main import app
from playwright.sync_api import sync_playwright, expect


def run():
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error'))
    with patch('main.initialize_database'):
        thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
        try:
            for _ in range(100):
                if server.started:break
                time.sleep(.05)
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='msedge',headless=True)
                page=browser.new_page();errors=[];calls=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                def api(route):
                    path=route.request.url.split('/api/')[1]
                    if path=='config': data={'live_available':True,'examples':[{'id':'test','input':'Caso ficticio'}]}
                    elif path=='budgets': data={'budgets':[{'id':'b1','month':9,'year':2026}]}
                    elif path=='plan/chat':
                        calls.append(route.request.post_data_json)
                        data={'reply':'Podemos ajustar cine. ¿Quieres empezar con algo pequeño?', 'proposal':{'reductions':[{'description':'Cine','current_amount':100,'reduce_by':10}],'event_items':[],'saving':10,'event_total':0,'remaining':910,'estimated':False}}
                    else:data={}
                    route.fulfill(status=200,content_type='application/json',body=json.dumps(data))
                page.route('**/api/**',api)
                page.goto(f'http://127.0.0.1:{port}')
                page.locator('[data-section="plan"]').click()
                page.locator('#plan-budget').select_option('b1')
                page.locator('#chat-text').fill('Quiero ahorrar más')
                page.locator('#chat-send').click()
                expect(page.locator('#chat-status')).to_contain_text('Autoriza')
                assert not calls
                page.locator('#chat-consent').check();page.locator('#chat-send').click()
                expect(page.locator('.chat-proposal')).to_be_visible()
                page.get_by_role('button',name='Revisar simulación').click()
                expect(page.locator('.chat-proposal')).to_contain_text('910')
                page.locator('#chat-text').fill('No puedo reducir transporte');page.locator('#chat-send').click()
                expect(page.locator('.chat-user')).to_have_count(2)
                expect(page.locator('#chat-send')).to_be_enabled()
                assert calls[1]['history'][0]['content']=='Quiero ahorrar más'
                page.locator('#plan-budget').select_option('')
                expect(page.locator('.chat-user')).to_have_count(0)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not errors,errors
                browser.close()
                print('PASS: consentimiento, conversación, seguimiento, simulación, cambio de presupuesto, móvil, sin errores JS.')
        finally:
            server.should_exit=True;thread.join(5);sock.close()

if __name__=='__main__':run()

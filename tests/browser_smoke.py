"""Browser regression with a test-only provider; no real Gemini quality claim."""
import json
from datetime import datetime, timezone
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'.tmp-tools'))
from playwright.sync_api import sync_playwright, expect
import uvicorn
from spendwise_api import create_app
from test_api import FakeProvider, CASE


def main():
    errors=[];checks=[]
    folder=ROOT/'artifacts/browser';folder.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        provider=FakeProvider(.3)
        application=create_app(str(Path(temp)/'browser.db'),provider)
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(application,host='127.0.0.1',port=port,log_level='error',access_log=False))
        thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
        try:
            for _ in range(100):
                if server.started:break
                time.sleep(.05)
            assert server.started
            with sync_playwright() as p:
                browser=p.chromium.launch(channel='msedge',headless=True)
                page=browser.new_page(viewport={'width':1440,'height':1000})
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{port}')
                expect(page.locator('#profile-select option')).to_have_count(3)
                assert page.locator('#mode').count()==0 and page.locator('#example').count()==0
                for pid,name in [('demo-ana-001','ANA'),('demo-carlos-002','CARLOS'),('demo-ana-001','ANA')]:
                    page.select_option('#profile-select',pid);expect(page.locator('#profile-label')).to_contain_text(name)
                checks.append('Repeated profile changes, no timeout; no sample selector')
                page.fill('#input',CASE['input']);page.check('#consent')
                page.select_option('#period-month','1')
                page.click('#extract');page.wait_for_selector('#review:visible')
                assert page.locator('#rows tr').count()==8
                page.locator('#rows tr').nth(2).locator('.simulate').check()
                page.check('#confirmed');page.click('#confirm');page.wait_for_selector('#result:visible')
                expect(page.locator('#total-balance')).to_contain_text('173.200')
                expect(page.locator('#saving')).to_contain_text('30.000')
                page.click('#save-budget');expect(page.locator('#notice')).to_contain_text('guardado')
                checks.append('Job polling, extraction, human confirmation, savings and persistence')
                page.click('[data-section="history"]');expect(page.locator('#history-rows tr')).to_have_count(1)
                page.locator('#history-rows button').first.click();page.wait_for_selector('#budget-detail:visible')
                expect(page.locator('#detail-balance')).to_contain_text('173.200')
                page.click('#detail-edit');page.locator('.saved-amount').first.fill('850000')
                page.click('#detail-save');expect(page.locator('#detail-balance')).to_contain_text('223.200')
                checks.append('Stored budget editing recalculates and persists')
                page.click('[data-section="register"]');page.click('#restart')
                page.select_option('#period-month','2');page.fill('#input',CASE['input']);page.click('#extract')
                page.wait_for_selector('#review:visible');page.check('#confirmed');page.click('#confirm')
                page.wait_for_selector('#result:visible');page.click('#save-budget');expect(page.locator('#notice')).to_contain_text('guardado')
                page.click('[data-section="compare"]');expect(page.locator('#compare-a option')).to_have_count(3)
                options=page.locator('#compare-a option').all()
                page.select_option('#compare-a',options[2].get_attribute('value'))
                page.select_option('#compare-b',options[1].get_attribute('value'))
                page.click('#run-compare');page.wait_for_selector('#compare-result:visible')
                expect(page.locator('#compare-expense-diff')).to_contain_text('50.000')
                page.check('#compare-consent');page.click('#explain-changes');page.wait_for_selector('#explanation-result:visible')
                checks.append('Two-period comparison and async explanation')
                page.click('[data-section="plan"]');expect(page.locator('#plan-budget option')).to_have_count(3)
                bid=page.locator('#plan-budget option').nth(1).get_attribute('value')
                page.select_option('#plan-budget',bid);page.fill('#plan-text','Liberar 100 pesos');page.check('#plan-consent')
                page.click('#plan-interpret');page.wait_for_selector('#plan-assumptions:visible')
                page.locator('.goal-reduction').first.fill('100');page.check('#plan-confirmed');page.click('#plan-calculate');page.wait_for_selector('#plan-result:visible')
                expect(page.locator('#plan-result-content')).to_contain_text('Meta alcanzable')
                checks.append('History detail and goal reductions are functional')
                page.click('#plan-new');page.check('input[name="plan-type"][value="event"]')
                page.fill('#plan-text','Viaje en bus');page.click('#plan-interpret');page.wait_for_selector('#plan-assumptions:visible')
                page.locator('.plan-item-amt').first.fill('')
                page.check('#plan-confirmed');page.click('#plan-calculate')
                expect(page.locator('#notice')).to_contain_text('Completa todos los montos')
                page.locator('.plan-item-amt').first.fill('100');page.check('#plan-confirmed');page.click('#plan-calculate');page.wait_for_selector('#plan-result:visible')
                checks.append('Event estimation requires amounts and confirmation')
                page.click('[data-section="register"]');page.click('#restart')
                provider.delay=2
                page.fill('#input',CASE['input']);page.click('#extract');page.wait_for_selector('#analysis-progress:visible')
                page.click('[data-section="history"]');expect(page.locator('#history-rows tr')).to_have_count(2)
                page.click('#cancel-analysis');expect(page.locator('#analysis-progress')).to_be_hidden()
                checks.append('History remains responsive during AI; cancellation works')
                page.click('[data-section="register"]');page.click('#extract');page.wait_for_selector('#analysis-progress:visible')
                page.select_option('#profile-select','demo-carlos-002');expect(page.locator('#profile-label')).to_contain_text('CARLOS')
                expect(page.locator('#input')).to_have_value('');expect(page.locator('#review')).to_be_hidden()
                page.click('[data-section="history"]');expect(page.locator('#history-list')).to_be_hidden()
                checks.append('Switching profile cancels old AI and clears private views')
                page.click('[data-section="register"]')
                page.screenshot(path=str(folder/'refactor-desktop.png'),full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('() => document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(folder/'refactor-mobile.png'),full_page=True)
                checks.append('Desktop and mobile rendered')
                assert not errors,errors
                browser.close()
        finally:
            server.should_exit=True;thread.join(5);sock.close()
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'mode':'test_provider_not_real_gemini','checks':checks,'console_errors':errors,'status':'PASS'}
    (ROOT/'evals/browser_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Browser PASS:',len(checks))

if __name__=='__main__':main()

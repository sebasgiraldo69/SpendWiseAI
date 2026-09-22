"""Optional real-browser check. Install Playwright; uses installed Chrome/Edge."""
import json
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'.tmp-tools'))
from playwright.sync_api import sync_playwright, expect
import app

def main():
    output=ROOT/'artifacts/browser'
    output.mkdir(parents=True,exist_ok=True)
    server=app.LocalServer(('127.0.0.1',0),app.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    errors=[]
    checks=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='msedge',headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(base)
            expect(page.locator('#input')).not_to_have_value('')
            page.screenshot(path=str(output/'01-entrada-simulada.png'),full_page=True)
            page.click('#extract');page.wait_for_selector('#review:visible')
            assert page.locator('#rows tr').count()==8
            page.locator('#rows tr').nth(2).locator('.simulate').check()
            page.check('#confirmed');page.click('#confirm');page.wait_for_selector('#result:visible')
            assert '173.200' in page.locator('#total-balance').inner_text()
            assert '30.000' in page.locator('#saving').inner_text()
            assert 'SIMULADO' in page.locator('#result-mode').inner_text()
            page.screenshot(path=str(output/'02-presupuesto-simulado.png'),full_page=True)
            with page.expect_download() as info:page.click('#download')
            download=info.value
            report=json.loads(Path(download.path()).read_text(encoding='utf-8'))
            assert report['output']['ahorro_potencial']==30000
            checks.append('Normal flow, user-selected savings, simulated label, JSON export')
            page.click('#restart');page.select_option('#example','8');page.click('#extract');page.wait_for_selector('#review:visible')
            assert 'Falta el monto' in page.locator('#issues').inner_text()
            row=page.locator('#rows tr').first
            row.locator('.amount').fill('100000');row.locator('.include').check()
            page.screenshot(path=str(output/'03-correccion-simulada.png'),full_page=True)
            page.check('#confirmed');page.click('#confirm');page.wait_for_selector('#result:visible')
            assert '180.000' in page.locator('#total-expense').inner_text()
            assert '1.320.000' in page.locator('#total-balance').inner_text()
            checks.append('Missing amount visible, corrected, included, recalculated')
            page.click('#edit-review');page.wait_for_selector('#review:visible')
            assert not page.locator('#confirmed').is_checked()
            page.click('#back');page.wait_for_selector('#entry:visible')
            for index in range(11):
                page.select_option('#example',str(index));page.click('#extract');page.wait_for_selector('#review:visible')
                page.check('#confirmed');page.click('#confirm');page.wait_for_selector('#result:visible')
                assert page.locator('#total-expense').inner_text()
                page.click('#restart');page.wait_for_selector('#entry:visible')
            checks.append('All 11 examples traverse review and result')
            page.select_option('#mode','live');assert not page.locator('#input').get_attribute('readonly')
            page.click('#extract');expect(page.locator('#notice')).to_contain_text('Autoriza')
            checks.append('Real provider requires explicit consent')
            mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
            mobile.goto(base);expect(mobile.locator('#input')).not_to_have_value('')
            assert mobile.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth')
            mobile.screenshot(path=str(output/'04-movil.png'),full_page=True)
            mobile.click('#extract');mobile.wait_for_selector('#review:visible')
            assert mobile.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth')
            mobile.check('#confirmed');mobile.click('#confirm');mobile.wait_for_selector('#result:visible')
            assert mobile.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth')
            checks.append('Mobile 390px entry, table scrolling, result without page overflow')
            page.goto(base+'/pitch')
            assert page.locator('.slide:visible').count()==1
            page.keyboard.press('ArrowRight');assert page.locator('#page').inner_text()=='2 / 7'
            page.click('#timer-toggle');page.wait_for_timeout(1200);assert page.locator('#timer').inner_text()!='06:00'
            page.click('#timer-reset');assert page.locator('#timer').inner_text()=='06:00'
            page.keyboard.press('ArrowLeft')
            page.screenshot(path=str(output/'05-pitch.png'),full_page=True)
            page.pdf(path=str(ROOT/'docs/SpendWiseAI_pitch.pdf'),landscape=True,print_background=True,prefer_css_page_size=True)
            checks.append('Pitch navigation, timer and PDF export')
            assert not errors, errors
            browser.close()
        hashes={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [ROOT/'app.py',ROOT/'spendwise_service.py',ROOT/'tests/browser_smoke.py',*sorted((ROOT/'web').glob('*'))]}
        (ROOT/'evals/browser_report.json').write_text(json.dumps({'timestamp_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':hashes,'mode':'fixture','browser':'Microsoft Edge / Playwright','checks':checks,'console_errors':errors,'status':'PASS'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Browser checks PASS:',len(checks))
    finally:
        server.shutdown();server.server_close();thread.join()

if __name__=='__main__':main()

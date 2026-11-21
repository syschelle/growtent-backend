"""Local/CI Chromium smoke for production ZIP export dialog with synthetic responses."""
import base64
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from render_analysis_export import fixture


def run(browser):
    f=fixture()
    image_bytes=base64.b64decode(f['zip_b64'])
    context=browser.new_context(accept_downloads=True)
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda err:errors.append(str(err)))
    page.set_content(f['html'])
    page.add_script_tag(content=f['js'])
    page.evaluate("""(base64Zip)=>{
      const bytes=Uint8Array.from(atob(base64Zip), c=>c.charCodeAt(0));
      window.testExportUrls=[];window.testExportFail=false;
      window.fetch=async(url)=>{
        window.testExportUrls.push(url);
        return new Response(window.testExportFail ? new Blob(['failure']) : new Blob([bytes],{type:'application/zip'}),{
          status: window.testExportFail ? 500 : 200,
          headers: {'Content-Disposition':'attachment; filename="growtent-2_2026-11-15_1200Z_24h.zip"'}
        });
      };
    }""", f['zip_b64'])
    page.evaluate("""() => {document.body.classList.remove('role-pending','role-guest');document.body.classList.add('role-admin');document.getElementById('exportCsvBtn').style.display='inline-block';}""")
    page.locator('#exportCsvBtn').click()
    assert page.locator('#analysisExportDialog').evaluate('(e)=>e.open')
    with page.expect_download() as info:
        page.locator('#analysisExportDownload').click()
    assert info.value.suggested_filename.endswith('_24h.zip')
    assert not page.locator('#analysisExportDialog').evaluate('(e)=>e.open')
    assert '/api/export/analysis.zip?tent_id=2&range=24h' in page.evaluate('window.testExportUrls[0]')
    page.evaluate('window.testExportFail=true')
    page.locator('#exportCsvBtn').click()
    page.locator('#analysisExportDownload').click()
    page.wait_for_function('document.getElementById("analysisExportStatus").textContent.includes("fehlgeschlagen")')
    assert page.locator('#analysisExportDialog').evaluate('(e)=>e.open')
    page.locator('#analysisExportCancel').click()
    for language in ('de','en'):
        for w in (1200,390,320):
            page.set_viewport_size({'width':w,'height':700})
            page.evaluate('(lang)=>{currentLang=lang;openAnalysisExport();}',language)
            assert page.locator('#analysisExportDialog').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
            assert 'ZIP' in page.locator('#analysisExportTitle').text_content()
            if language=='de': assert 'Kamerabild' in page.locator('#analysisExportHint').text_content()
            else: assert 'camera image' in page.locator('#analysisExportHint').text_content()
            page.keyboard.press('Escape')
    assert not errors,errors
    context.close()


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--browser', default='/usr/bin/chromium')
    args=parser.parse_args()
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=args.browser,args=['--no-sandbox'])
        try:run(browser)
        finally:browser.close()
    print('Analysis ZIP browser: DE/EN, desktop/mobile, download, failure recovery and cancel passed.')

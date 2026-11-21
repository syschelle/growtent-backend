"""Chromium smoke of original/HDR switch in *actual* fullscreen camera UI."""
from io import BytesIO
from base64 import b64encode
from playwright.sync_api import sync_playwright
from PIL import Image
from test_irrigation_ui_runtime import render, extract_scripts

with BytesIO() as stream:
    Image.new('RGB',(640,360),(60,100,150)).save(stream,'JPEG',quality=90)
    JPG=stream.getvalue()


def run(browser):
    script='\n'.join(extract_scripts(render('dashboard_page')))
    start=script.index('          function renderStream(')
    end=script.index('          function renderShellyDevices(',start)
    runtime=script[start:end]
    for lang in ('de','en'):
        context=browser.new_context(accept_downloads=True)
        seen=[];errors=[]
        page=context.new_page();page.on('pageerror',lambda err:errors.append(str(err)))
        page.set_content('<a id="streamOpenBtn">Fullscreen</a><div id="streamInfo"></div><iframe id="streamFrame"></iframe><img id="streamPreview">')
        page.evaluate("Object.defineProperty(window,'localStorage',{value:{getItem:()=> 'dark'}, configurable:true})")
        page.add_script_tag(content=f'''
            let currentLang='{lang}', currentTentId=2, currentPreviewBase='',previewTimer=null;
            let currentTempUnit='C';
            const tr=k=>k;
            const firstNum=()=>null,espControlVpd=()=>null,convertTempFromC=x=>x,fmtNum=()=>'-';
        ''' + runtime)
        page.evaluate("""(imageData) => {
          window.testRequestUrls=[];
          const originalOpen=window.open.bind(window);
          window.open=(...args)=>{
            const popup=originalOpen(...args);
            const RealImage=popup.Image;
            popup.Image=function(){
              const pre=new RealImage();
              Object.defineProperty(pre,'src',{set(url){
                window.testRequestUrls.push(url);
                pre.setAttribute('src', 'data:image/jpeg;base64,' + imageData);
              }});
              return pre;
            };
            return popup;
          };
          renderStream('', '', '', '/tents/2/preview');
        }""", b64encode(JPG).decode('ascii'))
        with page.expect_popup() as new_window:
            page.locator('#streamOpenBtn').click()
        popup=new_window.value
        popup.on('pageerror',lambda err:errors.append(str(err)))
        popup.wait_for_selector('#previewModeHDR',timeout=5000)
        assert popup.locator('#previewModeOriginal').get_attribute('aria-pressed')=='true'
        assert popup.locator('#previewModeHDR').get_attribute('aria-pressed')=='false'
        assert popup.locator('#previewImageModes').get_attribute('aria-label')==('Bildmodus' if lang=='de' else 'Image mode')
        popup.locator('#previewModeHDR').click()
        popup.wait_for_function("document.getElementById('previewModeHDR').getAttribute('aria-pressed')==='true'")
        popup.wait_for_timeout(300)
        seen=page.evaluate('window.testRequestUrls');assert any('hdr=1' in u and 'w=1920' in u for u in seen), seen[-12:]
        popup.locator('#previewModeOriginal').click()
        popup.wait_for_function("document.getElementById('previewModeOriginal').getAttribute('aria-pressed')==='true'")
        popup.wait_for_timeout(300)
        seen=page.evaluate('window.testRequestUrls');assert any('hdr=1' not in u and 'w=1920' in u for u in seen)
        # 320px viewport must not crop controls. Switching must stay usable.
        popup.set_viewport_size({'width':320,'height':568})
        geometry=popup.locator('#previewImageModes').evaluate('el=>{const b=el.getBoundingClientRect();return {x:b.x,y:b.y,right:b.right,bottom:b.bottom,width:innerWidth,height:innerHeight}}')
        assert geometry['x']>=0 and geometry['right']<=geometry['width'] and geometry['y']>=0 and geometry['bottom']<=geometry['height']
        popup.locator('#previewModeHDR').click()
        popup.wait_for_timeout(250)
        assert popup.locator('#previewModeHDR').get_attribute('aria-pressed')=='true'
        # At 200% the existing smart zoom requests the correct 2K frame
        # for the currently selected mode and still supports switching back.
        popup.locator('img[alt="Preview"]').dblclick(position={'x':100,'y':100},force=True)
        popup.wait_for_timeout(350)
        seen=page.evaluate('window.testRequestUrls')
        assert any('hdr=1' in u and 'w=2560' in u for u in seen),seen[-12:]
        popup.locator('#previewModeOriginal').click()
        popup.wait_for_timeout(350)
        seen=page.evaluate('window.testRequestUrls')
        assert any('hdr=1' not in u and 'w=2560' in u for u in seen),seen[-12:]
        popup.close();page.close();context.close()
        assert not errors,(lang,errors)


if __name__=='__main__':
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        try:run(browser)
        finally:browser.close()
    print('Fullscreen HDR switch: DE/EN, source URLs, responsive controls and no JS errors passed')

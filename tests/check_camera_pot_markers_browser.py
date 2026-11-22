"""Real Chromium exercise: stored markers, drag/save/cancel, HDR, roles, mobile."""
from base64 import b64encode
from io import BytesIO
import json
from PIL import Image
from playwright.sync_api import sync_playwright
from test_irrigation_ui_runtime import render, extract_scripts

with BytesIO() as memory:
    Image.new('RGB',(960,540),(60,95,105)).save(memory,'JPEG',quality=90)
    JPG=b64encode(memory.getvalue()).decode('ascii')

script='\n'.join(extract_scripts(render('dashboard_page')))
start=script.index('          function renderStream(')
end=script.index('          function renderShellyDevices(',start)
runtime=script[start:end]


def run(browser, role='admin', mobile=False, lang='de'):
    context=browser.new_context(viewport={'width':390 if mobile else 1440,'height':800})
    errors=[]
    page=context.new_page();page.on('pageerror',lambda err:errors.append(str(err)))
    page.set_content('<a id="streamOpenBtn">Fullscreen</a><div id="streamInfo"></div><iframe id="streamFrame"></iframe><img id="streamPreview">')
    page.evaluate("Object.defineProperty(window,'localStorage',{value:{getItem:()=> 'dark'},configurable:true})")
    page.evaluate("""() => {
        window.testCameraPositions={pot1:{x:.25,y:.6},pot2:null,pot3:null};
        window.testPotWrites=[];
        window.fetch=async (url,opts={})=>{
          if (String(url).includes('camera-positions')) {
            if (opts.method==='PUT') {
              const data=JSON.parse(opts.body);
              window.testPotWrites.push(data);
              window.testCameraPositions=data;
              return new Response(JSON.stringify({ok:true,positions:data}),{status:200,headers:{'content-type':'application/json'}});
            }
            return new Response(JSON.stringify({positions:window.testCameraPositions,
              pot_strains:{pot1:'Oreoz',pot2:'White Widow',pot3:''}}),
              {status:200,headers:{'content-type':'application/json'}});
          }
          return new Response(JSON.stringify({latest:{}}),{status:200,headers:{'content-type':'application/json'}});
        };
    }""")
    page.add_script_tag(content=f'''
        let currentLang='{lang}', currentTentId=2, currentUserRole='{role}';
        let currentPreviewBase='',previewTimer=null,currentTempUnit='C';
        const tr=k=>k;
        const firstNum=()=>null,espControlVpd=()=>null,convertTempFromC=x=>x,fmtNum=()=>'-';
    ''' + runtime)
    page.evaluate("""(imageData) => {
        const orig=window.open.bind(window);
        window.open=(...args)=>{
          const popup=orig(...args);
          const RealImage=popup.Image;
          popup.Image=function(){
            const pre=new RealImage();
            Object.defineProperty(pre,'src',{set(url){pre.setAttribute('src','data:image/jpeg;base64,'+imageData);}});
            return pre;
          };
          return popup;
        };
        renderStream('', '', '', '/tents/2/preview');
    }""",JPG)
    with page.expect_popup() as popup_ev:page.locator('#streamOpenBtn').click()
    popup=popup_ev.value;popup.on('pageerror',lambda err:errors.append(str(err)))
    popup.wait_for_selector('#cameraPotToolbar')
    popup.wait_for_selector('[data-pot=pot1]')
    popup.locator('img[alt=Preview]').evaluate('(el,src)=>{el.src=src}', 'data:image/jpeg;base64,'+JPG)
    popup.wait_for_function("document.querySelector('img[alt=Preview]').naturalWidth > 0")
    assert popup.locator('[data-pot=pot1]').get_attribute('aria-label') == ('Topf 1' if lang=='de' else 'Pot 1')
    assert popup.locator('#cameraShowPotNames').count() == 0
    assert popup.locator('#cameraPotToolbar button').count() == 4
    assert popup.locator('#cameraShowPots').inner_text() == ('Töpfe' if lang=='de' else 'Pots')
    if role == 'admin':
        assert popup.locator('#cameraEditPots').inner_text() == ('Positionen bearbeiten' if lang=='de' else 'Edit positions')
        assert popup.locator('#cameraPotToolbar').evaluate('el=>el.parentElement === document.body')
    assert popup.locator('#cameraPotToolbar').evaluate('el=>el.parentElement === document.body')
    assert popup.locator('.camera-pot-marker').first.locator('div').count() == 2
    assert popup.locator('[data-pot=pot1]').get_attribute('title') == 'Oreoz'
    popup.locator('[data-pot=pot1]').hover()
    assert popup.locator('[data-pot=pot1] .camera-pot-tooltip').is_visible()
    popup.mouse.move(1,1)
    assert 'Oreoz' not in popup.locator('#cameraPotMarkers').inner_text()
    assert popup.locator('[data-pot=pot2]').count()==0
    assert popup.locator('#cameraEditPots').is_visible() == (role == 'admin')
    if role == 'admin':
        assert popup.locator('#cameraPotToolbar').is_visible()
        assert popup.locator('#cameraPotToolbar').bounding_box()['y'] < popup.locator('img[alt=Preview]').bounding_box()['y']
        popup.locator('#cameraEditPots').click()
        popup.wait_for_selector('[data-pot=pot3]')
        assert popup.locator('#cameraSavePots').is_visible()
        assert popup.locator('#cameraCancelPots').is_visible()
        pos=popup.locator('[data-pot=pot1]').bounding_box()
        popup.mouse.move(pos['x']+pos['width']/2,pos['y']+10)
        popup.mouse.down()
        popup.mouse.move(pos['x']+pos['width']/2+75,pos['y']+10+35,steps=6)
        popup.mouse.up()
        draft=popup.locator('[data-pot=pot1]').evaluate("el=>({left:el.style.left,top:el.style.top})")
        assert draft['left'] != '25%', draft
        popup.locator('#cameraCancelPots').click()
        assert page.evaluate('window.testPotWrites.length')==0
        assert popup.locator('[data-pot=pot1]').evaluate('el=>el.style.left')=='25%'
        popup.locator('#cameraEditPots').click()
        popup.locator('[data-pot=pot2]').focus()
        popup.keyboard.press('ArrowRight')
        popup.locator('#cameraSavePots').click()
        popup.wait_for_function("document.getElementById('cameraPotFeedback').textContent.includes('gespeichert') || document.getElementById('cameraPotFeedback').textContent.includes('saved')")
        writes=page.evaluate('window.testPotWrites'); assert len(writes)==1 and writes[0]['pot2']['x']==.51, writes
        assert len([p for p in writes[0].values() if p])==3
    else:
        assert not popup.locator('#cameraEditPots').is_visible()
        assert popup.locator('#cameraPotToolbar').is_visible()
    popup.locator('#previewModeHDR').click()
    assert popup.locator('#previewModeHDR').get_attribute('aria-pressed')=='true'
    assert popup.locator('[data-pot=pot1]').count()==1
    popup.locator('#cameraShowPots').click()
    assert popup.locator('[data-pot=pot1]').count()==0
    popup.locator('#cameraShowPots').click()
    assert popup.locator('[data-pot=pot1]').count()==1
    popup.set_viewport_size({'width':320,'height':568})
    toolbar=popup.locator('#cameraPotToolbar').bounding_box()
    assert toolbar['x']>=0 and toolbar['x']+toolbar['width']<=322, toolbar
    if role == 'admin':
        edit_bar=popup.locator('#cameraPotToolbar').bounding_box()
        assert edit_bar['x']>=0 and edit_bar['x']+edit_bar['width']<=322, edit_bar
    assert popup.evaluate('document.documentElement.scrollWidth <= innerWidth+2')
    assert not errors,errors
    popup.close();page.close();context.close()


if __name__=='__main__':
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        try:
            run(browser,'admin',False,'de')
            run(browser,'admin',True,'en')
            run(browser,'guest',True,'de')
        finally:browser.close()
    print('Camera pot markers: DE/EN, edit-save-cancel, guest, HDR and 320 px verified')

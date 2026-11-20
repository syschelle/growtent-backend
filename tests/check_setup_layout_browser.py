"""Browser smoke checks for the compact setup page with mock API responses."""
import argparse
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from test_irrigation_ui_runtime import render

TENTS=[
    {"id":1,"name":"GrowTent","source_url":"http://192.168.1.58:8080/api/state","rtsp_url":"rtsp://cam.local/live","pot_strains":{"pot1":"Oreoz"},"soil_sensors":["192.168.1.81","",""],"irrigation_plan":{"enabled":True,"every_n_days":3,"offset_after_light_on_min":60},"growlight_power_alert_enabled":True,"growlight_power_drop_w":20,"backend_write_enabled":True,"backend_controller_url":"http://192.168.1.58:8080","has_backend_hmac_secret":True},
    {"id":2,"name":"Stecklingsbox","source_url":"http://192.168.1.62:8080/api/state","rtsp_url":"","pot_strains":{},"soil_sensors":[],"irrigation_plan":{},"backend_write_enabled":False},
    {"id":3,"name":"Zelt Drei","source_url":"http://192.168.1.63:8080/api/state","rtsp_url":"","pot_strains":{},"soil_sensors":[],"irrigation_plan":{},"backend_write_enabled":False},
]

def check(browser, screenshot_dir=None):
    page=browser.new_page(viewport={'width':1440,'height':900})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    import json
    fixtures=json.dumps(TENTS)
    # Browser navigation is unavailable in sandbox; run the real rendered page
    # on about:blank with *only* localStorage and HTTP fetch replaced by mocks.
    prelude = """<script>
      Object.defineProperty(window,'localStorage',{configurable:true,value:{
        __data:{gt_lang:'de',gt_theme:'dark'},getItem(k){return this.__data[k] ?? null;},
        setItem(k,v){this.__data[k]=String(v);},removeItem(k){delete this.__data[k];}
      }});
      window.__writes=[];
      window.__tents=__TENTS__;
      window.fetch=async (resource,options={})=>{
        const url=String(resource), method=options.method || 'GET';
        if(method!=='GET')window.__writes.push({method,path:url,body:options.body});
        let value=[];
        if(url==='/auth/whoami') value={role:'admin'};
        else if(url==='/tents') value=window.__tents;
        else if(url.endsWith('/latest')) value={latest:{}};
        else if(url.endsWith('/irrigation-plan')) value={enabled:false,revision:1,every_n_days:2,offset_after_light_on_min:30};
        else if(method!=='GET') value={};
        return {ok:true,status:200,json:async()=>value,text:async()=>JSON.stringify(value),headers:{get:()=>null}};
      };
    </script>""".replace('__TENTS__',fixtures)
    page.set_content(render('setup_page').replace('<script>',prelude+'\n<script>',1),wait_until='domcontentloaded')
    page.locator('.setup-tent-item').first.wait_for(state='visible')
    assert page.locator('.setup-tent-item').count() == 3
    assert page.locator('section.setup-group').count()==5
    for lang in ('de','en'):
        page.locator('#langSelect').select_option(lang)
        for theme in ('dark','light'):
            page.locator('#themeSelect').select_option(theme)
            for width,height in [(1920,950),(1440,900),(1024,768),(768,800),(390,844),(320,700)]:
                page.set_viewport_size({'width':width,'height':height})
                page.wait_for_timeout(40)
                geom=page.evaluate('''() => ({w:innerWidth, documentWidth:document.documentElement.scrollWidth,
                    groupWidths:[...document.querySelectorAll('section.setup-group')].map(el=>el.getBoundingClientRect().width),
                    editorOpen:document.getElementById('tentEditor').open,
                    cards:[...document.querySelectorAll('.setup-tent-item')].map(el=>{const r=el.getBoundingClientRect();return [r.left,r.right]})})''')
                assert geom['documentWidth']<=width+2,(lang,theme,width,geom)
                assert not geom['editorOpen']
                assert all(l>=-2 and r<=width+2 for l,r in geom['cards']),(lang,theme,width,geom)
                if width in (1440,1024,768,390,320):
                    layout=page.evaluate('''() => {
                      const groups = ['setupGroupDisplay','setupGroupBackup','setupGroupAccess','setupGroupStatus','setupGroupDevices'];
                      return Object.fromEntries(groups.map(id=>{
                        const r=document.getElementById(id).getBoundingClientRect();
                        return [id,{x:r.x,y:r.y,bottom:r.bottom,width:r.width}];
                      }));
                    }''')
                    display, backup, access, status, tents = (layout[x] for x in ['setupGroupDisplay','setupGroupBackup','setupGroupAccess','setupGroupStatus','setupGroupDevices'])
                    # Desktop sections form compact independent columns, not five long rows.
                    if width>=1000:
                        assert display['x']+15<access['x']<status['x']-15,(width,layout)
                        assert abs(display['y']-access['y'])<6 and abs(access['y']-status['y'])<6,(width,layout)
                        assert backup['y']>=display['bottom'],(width,layout)
                    # Tablet folds to two columns, small phones fold to one column.
                    elif width==768:
                        assert display['x']+15<access['x'],(width,layout)
                        assert status['y']>=access['bottom']-4,(width,layout)
                    else:
                        assert abs(display['x']-access['x'])<3 and abs(access['x']-status['x'])<3,(width,layout)
                        assert display['bottom']<=backup['y']<=access['y']<=status['y'],(width,layout)
                    assert tents['y']>=max(display['bottom'],backup['bottom'],access['bottom'],status['bottom'])-4,(width,layout)
                if screenshot_dir and lang=='de' and theme=='dark' and width in (1440,390):
                    Path(screenshot_dir).mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(Path(screenshot_dir)/f'setup-{width}.png'),full_page=True)
    # Check the expanded editor too, including long credential fields, at 320 px.
    page.set_viewport_size({'width':320,'height':700})
    page.locator('#tentEditor').evaluate('(el)=>el.open=true')
    expanded=page.evaluate("() => ({width:document.documentElement.scrollWidth, inputs:[...document.querySelectorAll('#tentEditor input, #tentEditor select')].map(el=>el.getBoundingClientRect().right)})")
    assert expanded['width']<=322, expanded
    assert all(r<=322 for r in expanded['inputs']), expanded
    actions=page.locator('.tent-editor-actions').evaluate('el=>[...el.querySelectorAll("button")].map(btn=>{const r=btn.getBoundingClientRect();return [r.left,r.right]})')
    assert all(left>=0 and right<=322 for left,right in actions), actions
    page.locator('#tentEditor').evaluate('(el)=>el.open=false')
    # Verify editing selects the right tent and reveals the pre-existing fields.
    page.set_viewport_size({'width':1440,'height':900})
    page.locator('#langSelect').select_option('de')
    page.locator('[data-edit-tent="1"]').click()
    assert page.locator('#tentEditor').evaluate('(el)=>el.open')
    assert page.locator('#tentName').input_value() == 'GrowTent'
    assert page.locator('#tentBackendControllerUrl').input_value() == 'http://192.168.1.58:8080'
    assert page.locator('#addTentBtn').get_attribute('data-edit-id') == '1'
    # Cancel edited tent: reset all unsaved fields, including credentials and the
    # HMAC clear flag, without sending any write request or altering the tent list.
    page.locator('#tentName').fill('UNSAVED')
    page.locator('#tentMainPass').fill('new-password')
    page.locator('#tentBackendHmacSecret').fill('a'*64)
    page.locator('#tentBackendHmacSecretClear').check()
    page.locator('#tentGrowlightPowerAlertEnabled').uncheck()
    page.locator('#tentGrowlightPowerDropW').fill('55')
    page.locator('#tentSoilSensor1').fill('10.0.0.99')
    writes_before=page.evaluate('window.__writes.length')
    assert page.locator('#cancelTentBtn').inner_text()=='Abbrechen'
    page.locator('#cancelTentBtn').click()
    assert not page.locator('#tentEditor').evaluate('(el)=>el.open')
    assert page.evaluate('window.__writes.length')==writes_before
    assert page.locator('#addTentBtn').get_attribute('data-edit-id') is None
    assert page.locator('#addTentBtn').text_content()=='Zelt hinzufügen'
    assert page.locator('#tentName').input_value()==''
    assert page.locator('#tentUrl').input_value()==''
    assert page.locator('#tentMainPass').input_value()==''
    assert page.locator('#tentBackendHmacSecret').input_value()==''
    assert not page.locator('#tentBackendHmacSecretClear').is_checked()
    assert page.locator('#tentGrowlightPowerDropW').input_value()=='20'
    assert page.locator('#tentSoilSensor1').input_value()==''
    assert page.locator('.setup-tent-item').count()==3
    assert 'GrowTent' in page.locator('.setup-tent-item').first.inner_text()
    # Reopening editing must load the persisted values, not the cancelled draft.
    page.locator('[data-edit-tent="1"]').click()
    assert page.locator('#tentName').input_value()=='GrowTent'
    assert page.locator('#tentGrowlightPowerAlertEnabled').is_checked()
    assert page.locator('#tentGrowlightPowerDropW').input_value()=='20'
    assert page.locator('#tentSoilSensor1').input_value()=='192.168.1.81'
    # Cancel is also translated on a language change during editing.
    page.locator('#langSelect').select_option('en')
    assert page.locator('#cancelTentBtn').inner_text()=='Cancel'
    assert page.locator('#addTentBtn').inner_text()=='Save tent'
    page.locator('#langSelect').select_option('de')
    assert page.locator('#cancelTentBtn').inner_text()=='Abbrechen'
    assert page.locator('#addTentBtn').inner_text()=='Zelt speichern'
    # Save flow still uses PUT with expected field names; calls are mocked and never leave browser.
    page.locator('#tentName').fill('GrowTent test')
    page.locator('#addTentBtn').click()
    page.wait_for_timeout(100)
    found=page.evaluate('window.__writes.filter(p=>p.method==="PUT" && p.path==="/tents/1")')
    assert found, page.evaluate('window.__writes')
    import json
    body=json.loads(found[-1]['body']); assert body['name']=='GrowTent test' and 'backend_write_enabled' in body and 'soil_sensors' in body
    assert page.locator('#addTentBtn').get_attribute('data-edit-id') is None
    # Cancel an unsaved new tent too, without accidental POST/PUT.
    page.locator('#tentName').fill('Draft tent')
    page.locator('#tentUrl').fill('http://draft/api/state')
    writes_before=page.evaluate('window.__writes.length')
    page.locator('#cancelTentBtn').click()
    assert page.evaluate('window.__writes.length')==writes_before
    assert page.locator('#tentName').input_value()==''
    assert not page.locator('#tentEditor').evaluate('(el)=>el.open')
    # Plan modal must be reachable from same compact card.
    page.locator('[data-plan-tent="1"]').click()
    assert page.locator('#irPlanModal').is_visible()
    page.locator('#irPlanCloseBtn').click()
    assert not page.locator('#irPlanModal').is_visible()
    assert not errors,errors
    page.close()
    return True

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser',default='/usr/bin/chromium');parser.add_argument('--screenshot-dir');args=parser.parse_args()
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=args.browser,args=['--no-sandbox'])
        try: check(b,args.screenshot_dir)
        finally: b.close()
    print('Setup layout browser checks passed: DE/EN, light/dark, desktop/mobile, editing, cancel without writes, watering modal, save mock.')

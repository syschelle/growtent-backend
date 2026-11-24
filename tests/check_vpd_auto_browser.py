"""Browser smoke: editable optional VPD plans per tent, DE/EN and mobile layout."""
import json
import argparse
from playwright.sync_api import sync_playwright
from test_irrigation_ui_runtime import render


def check(browser):
    page = browser.new_page(viewport={'width': 1100, 'height': 800})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    tents = [
        {'id':1,'name':'Zelt Eins','source_url':'http://192.0.2.1:8080/api/state','backend_write_enabled':True,'has_backend_hmac_secret':True},
        {'id':2,'name':'Zelt Zwei','source_url':'http://192.0.2.2:8080/api/state','backend_write_enabled':False},
    ]
    plans = {
        '1':{'enabled':False,'vegetative':[0.6,0.8], 'flowering':[1.0,1.3,1.4]},
        '2':{'enabled':False,'vegetative':[0.7], 'flowering':[1.1,1.2]},
    }
    prelude = '''<script>
    Object.defineProperty(window,'localStorage',{configurable:true,value:{
      __data:{gt_lang:'de',gt_theme:'dark'},getItem(k){return this.__data[k]??null;},
      setItem(k,v){this.__data[k]=String(v);},removeItem(k){delete this.__data[k];}
    }});
    window.__writes=[];
    window.__tents=__TENTS__;
    window.__plans=__PLANS__;
    window.fetch=async (resource,options={})=>{
      const url=String(resource),method=options.method||'GET';
      if(method!=='GET')window.__writes.push({path:url,method,body:options.body});
      let value={};let status=200;
      if(url==='/auth/whoami')value={role:'admin'};
      else if(url==='/tents')value=window.__tents;
      else if(/^\\/tents\\/\\d+\\/vpd-auto$/.test(url)){
        const id=url.split('/')[2];
        if(method==='PUT')window.__plans[id]=JSON.parse(options.body);
        value={tentId:Number(id),plan:window.__plans[id],lastApplied:null,lastStatus:null};
      }
      return {ok:status===200,status,json:async()=>value,text:async()=>JSON.stringify(value),headers:{get:()=>null}};
    };
    </script>'''.replace('__TENTS__',json.dumps(tents)).replace('__PLANS__',json.dumps(plans))
    page.set_content(render('setup_page').replace('<script>',prelude+'\n<script>',1),wait_until='domcontentloaded')
    page.locator('[data-vpd-auto="1"]').wait_for(state='visible')
    for lang in ('de','en'):
        page.locator('#langSelect').select_option(lang)
        page.evaluate('window.__plans["1"]={enabled:false,vegetative:[0.6,0.8],flowering:[1.0,1.3,1.4]}')
        page.set_viewport_size({'width':320,'height':700})
        page.locator('[data-vpd-auto="1"]').click()
        page.locator('#vpdAutoVegetative input').first.wait_for()
        assert page.locator('#vpdAutoVegetative input').count()==2
        assert page.locator('#vpdAutoFlowering input').count()==3
        assert not page.locator('#vpdAutoEnabled').is_checked()
        assert page.locator('#vpdAutoDrying').input_value()=='0.90'
        assert (('Trocknung' if lang=='de' else 'Drying') in page.locator('#vpdAutoDryTitle').inner_text())
        hint = page.locator('#vpdAutoHint').inner_text()
        assert ('wechselt niemals die Growphase' if lang=='de' else 'never advances it') in hint
        assert ('letzten konfigurierten Woche' if lang=='de' else 'last target holds') in hint
        page.locator('[data-vpd-add="vegetative"]').click()
        assert page.locator('#vpdAutoVegetative input').count()==3
        page.locator('#vpdAutoVegetative input').nth(1).fill('0.85')
        page.locator('#vpdAutoDrying').fill('0.95')
        page.locator('#vpdAutoEnabled').check()
        page.locator('#vpdAutoSaveBtn').click()
        page.wait_for_function('window.__writes.some(x=>x.path==="/tents/1/vpd-auto")')
        assert page.locator('#vpdAutoMsg').inner_text()
        saved=page.evaluate('window.__plans["1"]')
        assert saved=={'enabled':True,'vegetative':[0.6,.85,.8], 'flowering':[1.0,1.3,1.4], 'drying':0.95}
        assert page.evaluate('window.__plans["2"].enabled') is False
        page.locator('#vpdAutoCancelBtn').click()
        assert not page.locator('#vpdAutoModal').is_visible()
        page.locator('[data-vpd-auto="2"]').click()
        page.locator('#vpdAutoVegetative input').first.wait_for()
        assert page.locator('#vpdAutoVegetative input').count()==1
        assert page.locator('#vpdAutoVegetative input').first.input_value()=='0.70'
        page.locator('#vpdAutoCancelBtn').click()
        page.locator('[data-vpd-auto="1"]').click()
        page.locator('#vpdAutoVegetative input').first.wait_for()
        assert page.locator('#vpdAutoEnabled').is_checked()
        assert page.locator('#vpdAutoDrying').input_value()=='0.95'
        assert page.locator('#vpdAutoVegetative input').nth(1).input_value()=='0.85'
        page.locator('#vpdAutoCancelBtn').click()
    assert not errors, errors
    page.close()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser',default='/usr/bin/chromium');args=parser.parse_args()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=args.browser,args=['--no-sandbox'])
        try:check(browser)
        finally:browser.close()
    print('VPD automation: DE/EN, two tents, 320 px, weekly targets, save and reload verified')

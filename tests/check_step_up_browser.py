"""Chromium UI regression for the five-minute step-up dialog (no real HTTP)."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from test_irrigation_ui_runtime import render


def check(browser, language='de', totp=False, mobile=False):
    page = browser.new_page(viewport={'width':320 if mobile else 1260,'height':700})
    errors=[]
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    prelude='''<script>
      Object.defineProperty(window,'localStorage',{configurable:true,value:{
        getItem:key=>key==='gt_lang'?'__LANG__':key==='gt_theme'?'dark':null,
        setItem:()=>{},removeItem:()=>{}}});
      window.__stepApproved=false;
      window.__stepRequests=[];
      window.__sensitiveWrites=[];
      window.fetch=async (resource, options={})=>{
        const url=String(resource),method=String(options.method||'GET').toUpperCase();
        if(url==='/auth/step-up/status')return new Response(JSON.stringify({requires_totp:__TOTP__}),{
          status:200,headers:{'Content-Type':'application/json'}});
        if(url==='/auth/step-up'){
          const payload=JSON.parse(options.body||'{}');
          window.__stepRequests.push(payload);
          const ok=payload.password==='valid-password' && (!__TOTP__ || payload.code==='123456');
          window.__stepApproved=ok;
          return new Response(JSON.stringify({ok}),{status:ok?200:401,headers:{'Content-Type':'application/json'}});
        }
        if(url==='/config/admins' && method==='POST'){
          window.__sensitiveWrites.push({url,method,body:options.body});
          if(!window.__stepApproved)return new Response(JSON.stringify({detail:'Fresh security confirmation required'}),{
            status:428,headers:{'X-Step-Up-Required':'1','Content-Type':'application/json'}});
          return new Response(JSON.stringify({ok:true}),{status:200,headers:{'Content-Type':'application/json'}});
        }
        if(url==='/auth/whoami')return new Response(JSON.stringify({role:'admin'}),{status:200});
        if(url==='/config/admins')return new Response(JSON.stringify({items:[],current_admin_id:1}),{status:200});
        if(url==='/config/auth')return new Response(JSON.stringify({enabled:true,username:'admin',has_password:true}),{status:200});
        if(url==='/tents')return new Response('[]',{status:200});
        if(url==='/strains')return new Response('[]',{status:200});
        return new Response('{}',{status:200});
      };
    </script>'''.replace('__LANG__',language).replace('__TOTP__','true' if totp else 'false')
    page.set_content(render('setup_page').replace('<script>',prelude+'\n<script>',1),wait_until='domcontentloaded')
    page.evaluate('''() => {
      window.__action = fetch('/config/admins',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({username:'new-admin',password:'test-password'})})
        .then(r=>({ok:r.ok,status:r.status}));
    }''')
    page.locator('#securityStepUpModal').wait_for(timeout=10000)
    assert page.locator('#securityStepUpModal [role=dialog]').is_visible()
    assert page.locator('#securityStepUpModal input').count()==(2 if totp else 1)
    if mobile:
        box=page.locator('#securityStepUpModal [role=dialog]').bounding_box()
        assert box['x']>=0 and box['x']+box['width'] <=322, box
    page.locator('#securityStepUpModal input[type=password]').fill('wrong')
    if totp:page.locator('#securityStepUpModal input[autocomplete="one-time-code"]').fill('123456')
    page.locator('#securityStepUpModal button[type=submit]').click()
    page.wait_for_function('document.querySelector("#securityStepUpModal [role=alert]")?.textContent.length>0')
    assert len(page.evaluate('window.__sensitiveWrites'))==1
    page.locator('#securityStepUpModal input[type=password]').fill('valid-password')
    if totp:page.locator('#securityStepUpModal input[autocomplete="one-time-code"]').fill('123456')
    page.locator('#securityStepUpModal button[type=submit]').click()
    page.wait_for_function('!document.getElementById("securityStepUpModal")')
    result=page.evaluate('''async()=>await window.__action''')
    assert result=={'ok':True,'status':200},result
    assert len(page.evaluate('window.__sensitiveWrites'))==2
    assert len(page.evaluate('window.__stepRequests'))==2
    assert all('password=' not in x['url'] and 'secret=' not in x['url'] for x in page.evaluate('window.__sensitiveWrites'))
    assert not errors,errors
    page.close()


if __name__ == '__main__':
    with sync_playwright() as pw:
        kwargs={'headless':True,'args':['--no-sandbox']}
        if Path('/usr/bin/chromium').is_file():kwargs['executable_path']='/usr/bin/chromium'
        browser=pw.chromium.launch(**kwargs)
        try:
            check(browser,'de',True,False)
            check(browser,'en',False,True)
        finally:browser.close()
    print('Step-up browser checks: DE/EN, TOTP, incorrect/retry, modal 320px passed')

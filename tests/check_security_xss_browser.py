"""XSS regression checks on real rendered setup and Shelly UI (no network/controller)."""
import ast
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from test_irrigation_ui_runtime import render, extract_scripts

PAYLOAD = '<img src=x onerror="window.__xss=1">'
ATTR_PAYLOAD = '192.0.2.8" onmouseover="window.__xss=2'


def check_setup(browser):
    ctx = browser.new_context(viewport={'width': 1280, 'height': 800})
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    tent = {'id': 1, 'name': PAYLOAD, 'source_url': 'http://host/' + PAYLOAD,
            'rtsp_url': 'rtsp://host/' + PAYLOAD,
            'shelly_main_user': PAYLOAD,
            'pot_strains': {'pot1': PAYLOAD, 'pot2': 'Oreoz', 'pot3': ''},
            'soil_sensors': [PAYLOAD],
            'backend_write_enabled': True, 'backend_controller_url': PAYLOAD,
            'irrigation_plan': {'enabled': False}}
    guest = {'id': 9, 'username': PAYLOAD, 'enabled': True,
             'expires_at': '2030-01-01T10:00:00Z'}
    prelude = '''<script>
    window.__xss=0;
    Object.defineProperty(window,'localStorage',{configurable:true,value:{
      getItem:k=>({gt_lang:'de',gt_theme:'dark'}[k] ?? null),
      setItem:()=>{},removeItem:()=>{}}});
    const tent=__TENT__, guest=__GUEST__;
    window.fetch=async (url,opts={})=>{
      let value=[];
      if(url==='/auth/whoami')value={role:'admin'};
      else if(url==='/tents')value=[tent];
      else if(url==='/strains')value=[];
      else if(url==='/config/guests')value={items:[guest]};
      else if(url==='/config/admins')value={items:[],current_admin_id:1};
      else if(url==='/config/auth')value={enabled:true,username:'admin',has_password:true};
      else if(String(url).endsWith('/latest'))value={latest:{'settings.ui.boxName':__PAYLOAD__}};
      else value={};
      return {ok:true,status:200,json:async()=>value,text:async()=>JSON.stringify(value),headers:{get:()=>null}};
    };
    </script>'''.replace('__TENT__',json.dumps(tent)).replace('__GUEST__',json.dumps(guest)).replace('__PAYLOAD__',json.dumps(PAYLOAD))
    html = render('setup_page').replace('<script>', prelude+'\n<script>', 1)
    page.set_content(html, wait_until='domcontentloaded')
    page.locator('.setup-tent-item').first.wait_for(state='visible',timeout=10000)
    page.evaluate('loadGuestUsers()')
    page.wait_for_timeout(300)
    assert page.locator('.setup-tent-item img').count() == 0
    assert PAYLOAD in page.locator('.setup-tent-item').first.inner_text()
    assert page.locator('#guestUsersList img').count() == 0
    assert page.locator('#tentNavSetup img').count() == 0
    assert page.evaluate('window.__xss') == 0, 'Injected name executed JavaScript'
    assert not errors, errors
    ctx.close()


def _top_level_function(src, name):
    # Same extraction used by the project's established Shelley DOM tests.
    match = re.search(r'^          function ' + re.escape(name) + r'\(.*?^          }', src, re.M|re.S)
    assert match, name
    return match.group()


def check_shelly(browser):
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    page.set_content('<div id="shellyDevices"></div>')
    script = '\n'.join(extract_scripts(render('dashboard_page')))
    extracted = '\n'.join(_top_level_function(script,name) for name in
                          ('finiteNumber','normalizeShellyDeviceFromPayload','shellyIcon',
                           'shellyName','escHtml','renderShellyDevices'))
    mocks = '''
    window.__xss=0;
    const tr=k=>({on:'AN',off:'AUS'}[k]||k);
    const formatShellyChangeTime=()=>'-';
    const shellyLastSwitches={},shellyLastActivity={},shellyLastActivityDirect={};
    const shellyMainDirectTs=null;
    '''
    page.add_script_tag(content=mocks+'\n'+extracted)
    page.evaluate('''({payload,attrPayload})=>{
      const data={
        'settings.shelly.main.ip':attrPayload,
        'settings.shelly.main.gen':payload,
        'settings.shelly.main.line':'ON '+payload+'|OFF '+payload,
        'cur.shelly.main.isOn':true,
        'settings.shelly.injected.ip':payload,
        'settings.shelly.injected.line':payload,
        'settings.shelly.injected.gen':payload,
        'cur.shelly.injected.isOn':false
      };
      renderShellyDevices(data);
    }''',{'payload':PAYLOAD,'attrPayload':ATTR_PAYLOAD})
    assert page.locator('#shellyDevices img').count() == 0
    assert page.locator('#shellyDevices [onmouseover]').count() == 0
    assert PAYLOAD in page.locator('#shellyDevices').inner_text()
    assert page.evaluate('window.__xss') == 0
    assert not errors, errors
    page.close()


def check_shell(browser):
    source = (Path(__file__).resolve().parents[1] / 'api/app.py').read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'app_shell_page')
    node.decorator_list = []
    ns = {'APP_VERSION':'v0.408','FAVICON_LINKS':''}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'app.py','exec'),ns)
    html = ns['app_shell_page']()
    prelude = '''<script>
    window.__xss=0;
    Object.defineProperty(window,'localStorage',{configurable:true,value:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}}});
    window.fetch=async url=>{
      const value=String(url)==='/tents'? [{id:7,name:__PAYLOAD__}]:
          String(url).endsWith('/latest') ? {latest:{'settings.ui.boxName':__PAYLOAD__}} :
          String(url)==='/auth/whoami' ? {role:'admin'} : {};
      return {ok:true,status:200,json:async()=>value};
    };
    </script>'''.replace('__PAYLOAD__',json.dumps(PAYLOAD))
    page=browser.new_page()
    errors=[]
    page.on('pageerror',lambda exc: errors.append(str(exc)))
    page.set_content(html.replace('<script>',prelude+'\n<script>',1),wait_until='domcontentloaded')
    page.locator('#tentNav .navlink').first.wait_for(state='attached',timeout=10000)
    assert page.locator('#tentNav img').count() == 0
    assert PAYLOAD in page.locator('#tentNav').inner_text()
    assert page.evaluate('window.__xss') == 0
    assert not errors, errors
    page.close()


if __name__ == '__main__':
    with sync_playwright() as pw:
        launch_args={'headless':True,'args':['--no-sandbox']}
        if Path('/usr/bin/chromium').is_file():
            launch_args['executable_path']='/usr/bin/chromium'
        browser = pw.chromium.launch(**launch_args)
        try:
            check_setup(browser)
            check_shelly(browser)
            check_shell(browser)
        finally:
            browser.close()
    print('XSS browser checks passed: setup/tent/guest labels, shell navigation and Shelly fields')

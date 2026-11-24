"""Chromium regression for the plain-text VPD automation status."""
from __future__ import annotations
from playwright.sync_api import sync_playwright
from test_irrigation_ui_runtime import render


def check(browser):
    page = browser.new_page(viewport={'width': 1100, 'height': 800})
    errors=[]
    page.on('pageerror',lambda e: errors.append(str(e)))
    prelude = '''<script>
      Object.defineProperty(window,'localStorage',{configurable:true,value:{
        __data:{gt_lang:'de',gt_theme:'dark'},getItem(k){return this.__data[k]??null;},
        setItem(k,v){this.__data[k]=String(v)},removeItem(k){delete this.__data[k]}
      }});
      window.__tents = [
        {id:1,name:'Tent One'}, {id:2,name:'Tent Two'}
      ];
      window.__badgeData = {
        1:{tentId:1,enabled:true,lastSyncFailed:false},
        2:{tentId:2,enabled:true,lastSyncFailed:true}
      };
      window.__badgeRequests = [];
      window.__badgeWaiting = null;
      window.fetch = async (input,options={})=>{
        const url=String(input);
        if(url==='/auth/whoami')return reply({role:'admin'});
        if(url==='/tents')return reply(window.__tents);
        const match=url.match(/^\\/tents\\/(\\d+)\\/vpd-auto\\/status$/);
        if(match){
          window.__badgeRequests.push(Number(match[1]));
          if(window.__badgeWaiting?.id===Number(match[1]))return await window.__badgeWaiting.promise;
          if(window.__badgeData[match[1]]===null)return reply({},503);
          return reply(window.__badgeData[match[1]]);
        }
        if(url.includes('/latest'))return reply({latest:{},captured_at:null});
        if(url.includes('/history'))return reply({points:[], rows:[]});
        return reply({});
      };
      function reply(value,status=200){return {ok:status===200,status,json:async()=>value,text:async()=>JSON.stringify(value),headers:{get:()=>null}};}
    </script>'''
    # The actual dashboard script is executed; only backend requests are mocked.
    html=render('dashboard_page')
    html=html.replace('<script>\n          const isEmbed', prelude+'\n<script>\n          const isEmbed',1)
    page.set_content(html,wait_until='domcontentloaded')
    badge=page.locator('#vpdAutoBadge')
    page.wait_for_function("document.querySelector('#vpdAutoBadge')?.dataset.state==='active'",timeout=10000)
    assert badge.inner_text() == 'auto'
    assert badge.get_attribute('title') == 'VPD-Automatik aktiv'
    assert badge.is_visible()
    green = badge.evaluate('e=>getComputedStyle(e).color')
    # The status must be plain colored text: no chip border, padding or background.
    def assert_plain_text():
        style = badge.evaluate('''e => {
          const s = getComputedStyle(e);
          return {border:s.borderTopWidth, background:s.backgroundColor,
                  padding:s.paddingTop, radius:s.borderTopLeftRadius, shadow:s.boxShadow};
        }''')
        assert style == {'border':'0px','background':'rgba(0, 0, 0, 0)',
                         'padding':'0px','radius':'0px','shadow':'none'}, style
    assert_plain_text()
    assert page.locator('#vpdAutoBadge').evaluate('e=>e.closest(".card-head")!==null')

    # Switching tents never retains the previous tent's green state.
    page.evaluate('currentTentId=2')
    page.evaluate('loadVpdAutoBadge()')
    page.wait_for_function("document.querySelector('#vpdAutoBadge')?.dataset.state==='failed'")
    assert badge.get_attribute('title')=='Letzter VPD-Abgleich fehlgeschlagen'
    assert badge.evaluate('e=>getComputedStyle(e).color') != green
    assert_plain_text()
    # A late response from the previous tent must not repaint the current tent.
    page.evaluate("""() => {
      window.__badgeWaiting={id:1,promise:new Promise(resolve=>{window.__resolveOldBadge=resolve})};
      currentTentId=1;
      void loadVpdAutoBadge();
    }""")
    page.wait_for_function("window.__badgeRequests.at(-1)===1")
    page.evaluate('currentTentId=2;void loadVpdAutoBadge()')
    page.wait_for_function("document.querySelector('#vpdAutoBadge')?.dataset.state==='failed'")
    page.evaluate("window.__resolveOldBadge(reply({tentId:1,enabled:true,lastSyncFailed:false}));window.__badgeWaiting=null")
    page.wait_for_timeout(60)
    assert badge.get_attribute('data-state')=='failed'
    page.evaluate("currentLang='en'; loadVpdAutoBadge()")
    page.wait_for_function("document.querySelector('#vpdAutoBadge')?.title==='Last VPD sync failed'")
    page.evaluate('window.__badgeData[2]={tentId:2,enabled:false,lastSyncFailed:true};loadVpdAutoBadge()')
    page.wait_for_function("document.querySelector('#vpdAutoBadge')?.hidden===true")

    # A failed status lookup hides the badge instead of preserving stale state.
    page.evaluate('window.__badgeData[2]=null;loadVpdAutoBadge()')
    page.wait_for_function("window.__badgeRequests.length>=5")
    assert not badge.is_visible()

    # Responsive width, guest mode, and tent switch keep badge usable.
    page.set_viewport_size({'width':320,'height':700})
    page.evaluate('window.__badgeData[2]={tentId:2,enabled:true,lastSyncFailed:false};currentUserRole="guest";loadVpdAutoBadge()')
    page.wait_for_function("document.querySelector('#vpdAutoBadge')?.dataset.state==='active'")
    assert badge.is_visible()
    assert badge.bounding_box()['x'] < 320
    assert badge.inner_text() == 'auto'
    assert_plain_text()
    # No synthetic JS errors from the badge logic.
    assert not any('loadVpdAutoBadge' in e for e in errors), errors
    page.close()


if __name__ == '__main__':
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        check(browser)
        browser.close()
    print('VPD auto badge: green/orange/hidden, DE/EN, guest, mobile checked')

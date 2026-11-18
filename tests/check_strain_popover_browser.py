"""Isolated Chromium check of the production dashboard plant-information popover."""
import argparse
import re

from playwright.sync_api import sync_playwright
from render_target_editors import StaticHTML
from test_irrigation_ui_runtime import render, extract_scripts


def check(browser, screenshot=None):
    html = render('dashboard_page')
    script = '\n'.join(extract_scripts(html))
    i18n = script[script.index('          const I18N = {'):script.index('          let currentLang')]
    popover = script[script.index('          let dashboardStrainMap = null;'):script.index('          function renderStream(')]
    guest = re.search(r'^          function applyGuestModeUi\(\).*?^          }', script, re.M | re.S).group()
    page = browser.new_page(viewport={'width': 390, 'height': 760})
    page.route('**/*', lambda route: route.abort())
    page.set_content(''.join(StaticHTML(html).parts))
    page.add_script_tag(content=i18n + r'''
        let currentLang='de', isGuestMode=true;
        function tr(key){return I18N[currentLang]?.[key]||I18N.en[key]||key;}
        function syncGrowProfileAction(){} function syncHmacBadge(){}
        let sample = {name:'Example',genetics:'Hybrid',thc:'20–25 %',cbd:'< 1%',flowering_weeks:'medium',effects:'- Beispieltext mit mehreren Zeilen\n- Zweite Zeile mit einem „Zitat“ und einem längeren Satz zur Prüfung des Umbruchs\n- Dritte Zeile\n- Vierte Zeile mit weiteren Angaben\n- Fünfte Zeile',aroma:'Beispielbeschreibung mit mehreren Wörtern und einem gut sichtbaren Zeilenumbruch'};
        window.fetch=async()=>({json:async()=>[sample]});
    ''' + popover + guest + '''
        window.setup=(lang,theme)=>{currentLang=lang;document.documentElement.dataset.theme=theme;document.body.classList.add('embed');renderPotStrains({pot3:'Example'});applyGuestModeUi();};
        window.openSample=()=>{showStrainPopover(document.querySelector('.pot-strain-link'),tr('pot3'),'Example',sample);applyGuestModeUi();};
        window.fixedAnchor=()=>{Object.assign(document.getElementById('streamPotStrains').style,{position:'fixed',right:'12px',bottom:'12px',zIndex:'1000'});};
    ''')
    pop = page.locator('#strainPopover')
    anchor = page.locator('.pot-strain-link')
    geometry = '''el=>{const r=el.getBoundingClientRect();return {x:r.left,y:r.top,right:r.right,bottom:r.bottom,w:r.width,h:r.height,scroll:el.scrollHeight-el.clientHeight,overflow:el.scrollWidth-el.clientWidth,font:getComputedStyle(el).fontSize}}'''
    for lang in ['de', 'en']:
        for theme in ['dark','light']:
            for width,height in [(1600,900),(390,760),(320,568),(667,350)]:
                page.set_viewport_size({'width':width,'height':height})
                page.evaluate('([lang,theme])=>{setup(lang,theme);fixedAnchor()}',[lang,theme])
                anchor.click()
                pop.wait_for(state='visible')
                g=pop.evaluate(geometry)
                assert g['x']>=11 and g['y']>=11 and g['right']<=width-11 and g['bottom']<=height-11, (lang,theme,width,g)
                assert g['w']<=350 and g['overflow']<=1 and g['font']=='13px',g
                assert pop.locator('dt').all_text_contents()==(['THC','CBD','Genetik','Blütezeit'] if lang=='de' else ['THC','CBD','Genetics','Flowering time'])
                assert pop.locator('dd').all_text_contents()[-1]==('Mittel – 9–10 Wochen' if lang=='de' else 'Medium – 9–10 weeks')
                assert pop.locator('h3').all_text_contents()==(['Effekte','Aroma'] if lang=='de' else ['Effects','Aroma'])
                assert pop.locator('dd').nth(1).text_content()=='< 1%'
                assert anchor.get_attribute('aria-expanded')=='true'
                assert page.locator('#closeStrainPopover').is_enabled()
                page.evaluate("renderPotStrains({pot3:'Example'})")
                assert pop.is_visible()
                if screenshot and (lang,theme,width)==('de','dark',390):
                    pop.screenshot(path=screenshot)
                page.keyboard.press('Escape')
                assert pop.is_hidden() and anchor.get_attribute('aria-expanded')=='false'
    page.set_viewport_size({'width':320,'height':420})
    page.evaluate('setup("de","dark"); sample.effects=("<img src=x onerror=alert(1)> "+"W".repeat(250)+"\\n").repeat(12);openSample()')
    g=pop.evaluate(geometry)
    assert g['scroll']>0 and g['overflow']<=1 and g['bottom']<=409,g
    assert pop.locator('img').count()==0
    assert '<img src=x' in pop.text_content()
    pop.evaluate('el=>el.scrollTop=el.scrollHeight')
    assert pop.evaluate('el=>el.scrollTop')>0
    page.keyboard.press('Escape')
    page.evaluate('sample.flowering_weeks="";openSample()')
    assert pop.locator('dt').count()==3
    page.evaluate('showStrainPopover(document.querySelector(".pot-strain-link"),"Topf 3","Unknown",null)')
    assert 'Kein Eintrag' in pop.text_content()
    page.locator('#closeStrainPopover').click()
    assert pop.is_hidden()
    page.evaluate('openSample()')
    page.locator('body').click(position={'x':2,'y':2})
    assert pop.is_hidden()
    page.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--browser')
    parser.add_argument('--screenshot')
    args=parser.parse_args()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=args.browser,args=['--no-sandbox'])
        try: check(browser,args.screenshot)
        finally: browser.close()
    print('Plant popover browser checks passed (DE/EN, light/dark, desktop/mobile, long text, escaping, guest access and dismissal).')

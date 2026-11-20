"""Chromium regression for the bundled Grow-Guide, without network or controller calls."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / 'api' / 'static'


def page_html():
    result = (STATIC / 'grow-guide-page.html').read_text(encoding='utf-8')
    result = result.replace('__FAVICON_LINKS__', '')
    for lang in ('de', 'en'):
        result = result.replace(f'__GUIDE_{lang.upper()}__', (STATIC / f'grow-guide-{lang}.html').read_text(encoding='utf-8'))
    return result


def check(browser, screenshot_dir=None):
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_storage = '''<script>
      Object.defineProperty(window,'localStorage',{configurable:true,value:{
        values:{gt_theme:'dark',gt_lang:'de'},
        getItem(k){return this.values[k] ?? null;},setItem(k,v){this.values[k]=v;}
      }});
      window.fetch=()=>{throw Error('Guide must never fetch controller data');};
    </script>'''
    html = page_html().replace('<script>', mock_storage + '<script>', 1)
    page.set_content(html, wait_until='domcontentloaded')
    assert page.locator('#guideNav a').count() == 20
    assert page.locator('#guideDe .guide-section:visible').count() == 20
    assert page.locator('#guideEn .guide-section:visible').count() == 0
    assert page.locator('#guideDe table').count() >= 5
    assert page.locator('#guideDe a[href^="https://"]').count() == 13
    for lang in ('de','en'):
        if (page.locator('html').get_attribute('lang') != lang):
            page.locator('#guideLangToggle').click()
        assert page.locator('html').get_attribute('lang') == lang
        assert page.locator('#guideNav a').count() == 20
        assert page.locator(f'#guide{lang.title()} .guide-section:visible').count() == 20
        assert page.locator('#guideNavTitle').inner_text() == ('Kapitel' if lang == 'de' else 'Chapters')
        for theme in ('dark','light'):
            page.evaluate('(theme)=>document.documentElement.dataset.theme=theme', theme)
            for width,height in ((1440,900),(768,780),(390,844),(320,650)):
                page.set_viewport_size({'width':width,'height':height})
                page.wait_for_timeout(20)
                bounds = page.evaluate('''() => ({viewport:innerWidth, html:document.documentElement.scrollWidth,
                    panel:document.querySelector('.guide-panel').getBoundingClientRect().right,
                    nav:document.querySelector('.guide-navigation').getBoundingClientRect().right})''')
                assert bounds['html'] <= width+2, (lang,theme,width,bounds)
                assert bounds['panel'] <= width+2 and bounds['nav'] <= width+2,(lang,theme,width,bounds)
                if screenshot_dir and lang == 'de' and theme == 'dark' and width in (1440,390):
                    Path(screenshot_dir).mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(Path(screenshot_dir)/f'grow-guide-{width}.png'),full_page=False)
    page.locator('#guideSearch').fill('trichomes')
    n = page.locator('#guideEn .guide-section:visible').count()
    assert 0 < n < 20
    assert page.locator('#guideNav a').count() == n
    page.locator('#guideSearch').fill('not-a-real-phrase-zz')
    assert page.locator('#guideNav a').count() == 0
    assert 'No matching' in page.locator('#guideMatches').inner_text()
    page.locator('#guideSearch').fill('')
    assert page.locator('#guideNav a').count() == 20
    page.set_viewport_size({'width':320,'height':650})
    if not page.locator('#guideNavigation').evaluate('el=>el.open'):
        page.locator('#guideNavigation summary').click()
    page.locator('#guideNav a').first.click()
    assert not page.locator('#guideNavigation').evaluate('el=>el.open')
    assert not errors, errors
    page.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--browser', default='/usr/bin/chromium')
    parser.add_argument('--screenshot-dir')
    args=parser.parse_args()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.browser, headless=True, args=['--no-sandbox'])
        try: check(browser,args.screenshot_dir)
        finally: browser.close()
    print('GrowGuide browser checks passed (DE/EN, 20 chapters, search, light/dark, 320–1440 px, no controller writes).')

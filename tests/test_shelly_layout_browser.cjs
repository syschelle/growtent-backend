// Exercise production dashboard CSS and Shelly rendering without any live devices.
const fs = require('node:fs');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const fixture = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const roles = ['main','light','humidifier','heater','heatmat','fan','exhaust'];
(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.CHROMIUM_EXECUTABLE ? {executablePath:process.env.CHROMIUM_EXECUTABLE} : {})});
  try {
    const page = await browser.newPage({viewport:{width:1730,height:900}});
    await page.route('**/*', route => route.abort());
    await page.setContent(fixture.html);
    await page.addScriptTag({content: `
      let currentLang='de';
      function tr(key){return I18N[currentLang]?.[key]||I18N.en[key]||key;}
      const shellyLastSwitches={},shellyLastActivity={},shellyLastActivityDirect={};
      const shellyMainDirectTs=null;
      ${fixture.js}
      window.renderTestDevices=(roles,lang)=>{
        currentLang=lang;
        const payload={};
        roles.forEach((key,i)=>{
          payload['settings.shelly.'+key+'.ip']='192.0.2.'+(i+1);
          payload['settings.shelly.'+key+'.gen']=key==='heatmat'?3:2;
          payload['settings.shelly.'+key+'.line']='ON 5:00 | OFF 17:00';
          payload['cur.shelly.'+key+'.isOn']=i%3!==2;
          payload['cur.shelly.'+key+'.meteringOnly']=key==='heatmat';
          payload['cur.shelly.'+key+'.Watt']=135.3;
          payload['cur.shelly.'+key+'.Wh']=93587;
          payload['cur.shelly.'+key+'.Cost']=36.54;
          shellyLastActivity[key]=new Date(Date.now()-60000).toISOString();
        });
        renderShellyDevices(payload);
      };
    `});
    const geometry = () => page.locator('#shellyDevices').evaluate(grid=>{
      const cards=[...grid.querySelectorAll(':scope > .card')];
      const rects=cards.map(c=>c.getBoundingClientRect());
      return {rows:new Set(rects.map(r=>Math.round(r.top))).size,
        widthSpread:Math.max(...rects.map(r=>r.width))-Math.min(...rects.map(r=>r.width)),
        heightSpread:Math.max(...rects.map(r=>r.height))-Math.min(...rects.map(r=>r.height)),
        overflow:grid.scrollWidth-grid.clientWidth,
        clipped:cards.some(c=>c.scrollWidth>c.clientWidth+1),
        count:cards.length};
    });
    await page.evaluate(()=>document.body.classList.add('embed'));
    for(const lang of ['de','en']){
      for(const width of [1920,1730,1440,1280,1100]){
        await page.setViewportSize({width,height:900});
        await page.evaluate(({roles,lang})=>renderTestDevices(roles,lang),{roles,lang});
        const g=await geometry();
        assert.equal(g.count,7);assert.equal(g.rows,1,`${lang} ${width}`);
        assert.ok(g.widthSpread<=1);assert.ok(g.heightSpread<=1);assert.equal(g.clipped,false);
        if(width>=1280)assert.ok(g.overflow<=1,JSON.stringify(g));
        else assert.ok(g.overflow>0,'Narrow desktop scrolls inside the Shelly grid');
        assert.equal(await page.locator('#shellyDevices [data-shelly-toggle]').count(),6);
        assert.equal(await page.locator('#shellyDevices [data-open-shelly]').count(),7);
      }
    }
    for(const width of [900,390]){
      await page.setViewportSize({width,height:900});
      assert.equal((await geometry()).rows,width===900?4:7);
    }
    await page.setViewportSize({width:1730,height:900});
    await page.evaluate(()=>document.body.classList.add('force-mobile'));
    assert.equal((await geometry()).rows,7);
    await page.evaluate(()=>document.body.classList.remove('force-mobile'));
    for(const count of [1,3,7,8]){
      const configured=[...roles,'extra'].slice(0,count);
      await page.evaluate(roles=>renderTestDevices(roles,'de'),configured);
      const g=await geometry();assert.equal(g.count,count);assert.equal(g.rows,1);assert.ok(g.widthSpread<=1);
    }
    await page.evaluate(()=>renderTestDevices([],'de'));
    assert.equal(await page.locator('#shellyDevices > .card').count(),0);
    assert.ok((await page.locator('#shellyDevices').textContent()).trim());
    console.log('Desktop single row, equal widths, narrow scrolling, mobile/tablet/forced mobile, dynamic devices and actions passed');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});

const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const f=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const browser=await chromium.launch();const page=await browser.newPage();let requests=0;
 await page.route('**/*',route=>{requests++;return route.fulfill({contentType:'text/html; charset=utf-8',body:f.html});});await page.goto('http://vpd-table.test/dashboard');await page.addScriptTag({content:f.js});
 await page.evaluate(()=>{document.body.classList.remove('role-pending','role-guest');document.body.classList.add('role-admin');window.ctx={tent:2,language:'de',unit:'C'};window.clock=Date.now();window.timer=null;
  GrowTentVpdTable.mount({getContext:()=>ctx,clock:()=>clock,setTimer:fn=>timer=fn});
  window.sample={'sensors.cur.temperatureC':23.8,'sensors.cur.humidityPct':52.6,'sensors.cur.vpdKpa':1.16,'settings.grow.targetVPD':1.17,'settings.grow.offsetLeafTemperature':-1.5};
  GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());});
 const before=requests;await page.locator('#openVpdTableBtn').click();assert.equal(await page.locator('#vpdReferenceTable tbody tr').count(),21);assert.equal(await page.locator('#vpdReferenceTable tbody td').count(),525);assert.equal(await page.locator('#vpdReferenceTable td[data-current]').count(),1);assert.match(await page.locator('#vpdTableReadings').textContent(),/ESP-Regel-VPD1,16 kPa/);
 const initial=await page.locator('#vpdReferenceTable td[data-current]').textContent();
 await page.evaluate(()=>{sample['settings.grow.offsetLeafTemperature']=0;GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());});assert.notEqual(await page.locator('#vpdReferenceTable td[data-current]').textContent(),initial);assert.match(await page.locator('#vpdTableReadings').textContent(),/ESP-Regel-VPD1,16 kPa/);
 await page.evaluate(()=>{sample['settings.grow.offsetLeafTemperature']=null;GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());});assert.equal(await page.locator('#vpdReferenceTable td[data-current]').count(),0);assert.match(await page.locator('#vpdTableState').textContent(),/Blatt-Offset fehlt/);assert.equal(await page.locator('#vpdReferenceTable td.vpd-band-unknown').count(),525);
 await page.evaluate(()=>{sample['settings.grow.offsetLeafTemperature']=-1.5;GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());clock+=120001;timer();});assert.equal(await page.locator('#vpdReferenceTable td[data-current]').count(),0);assert.match(await page.locator('#vpdTableState').textContent(),/Keine aktuellen/);
 await page.evaluate(()=>{ctx.tent=3;GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());timer();});assert.equal(await page.locator('#vpdReferenceTable td[data-current]').count(),0);
 await page.evaluate(()=>{GrowTentVpdTable.update(3,{...sample,'sensors.cur.temperatureC':18},new Date(clock).toISOString());});assert.match(await page.locator('#vpdTableState').textContent(),/außerhalb/);assert.equal(await page.locator('#vpdReferenceTable td[data-current]').count(),0);
 fs.mkdirSync('layout-previews',{recursive:true});
 for(const language of ['de','en'])for(const width of [1640,390]){
  await page.keyboard.press('Escape');await page.setViewportSize({width,height:1000});await page.evaluate(({language,width})=>{ctx.language=language;ctx.unit=language==='en'?'F':'C';document.documentElement.dataset.theme=language==='en'?'light':'dark';GrowTentVpdTable.update(3,sample,new Date(clock).toISOString());}, {language,width});await page.locator('#openVpdTableBtn').click();
  assert.equal(await page.locator('#vpdTableDialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);
  assert.equal(await page.locator('#vpdReferenceTable td[data-current]').count(),1);
  const visible=await page.locator('#vpdReferenceTable td[data-current]').evaluate(el=>{const a=el.getBoundingClientRect(),b=el.closest('.vpd-table-scroll').getBoundingClientRect();return a.left>=b.left&&a.right<=b.right;});assert.ok(visible,'Current marker centered on open');
  await page.screenshot({path:`layout-previews/vpd-table-${language}-${width}.png`});
 }
 await page.locator('#closeVpdTableBtn').click();assert.equal(await page.locator('#vpdTableDialog').evaluate(el=>el.open),false);assert.equal(requests,before,'No polling or control calls from table');
 console.log('Live VPD table: central value/offset/reference, markers, stale/missing data, tent races, outside range, auto-scroll, DE/EN C/F and responsive light/dark passed');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

const fs=require('fs'),assert=require('node:assert/strict');const{chromium}=require('playwright');
(async()=>{
 const f=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const browser=await chromium.launch();const context=await browser.newContext();
 await context.route('http://chart-settings.test/**',route=>route.fulfill({contentType:'text/html',body:f.html}));
 const page=await context.newPage();await page.goto('http://chart-settings.test/setup');await page.addScriptTag({content:f.js});
 assert.equal(await page.locator('#chartTemperatureRange').inputValue(),'5');assert.equal(await page.locator('#chartHumidityRange').inputValue(),'10');assert.equal(await page.locator('#chartVpdRange').inputValue(),'0');
 await page.locator('#chartTemperatureRange').fill('2.5');await page.locator('#chartHumidityRange').fill('12');await page.locator('#chartVpdRange').fill('0.30');await page.locator('#saveChartRangesBtn').click();
 assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('gt_chart_ranges'))),{temperature:2.5,humidity:12,vpd:0.3});
 await page.reload();await page.addScriptTag({content:f.js});assert.equal(await page.locator('#chartTemperatureRange').inputValue(),'2.5');assert.equal(await page.locator('#chartHumidityRange').inputValue(),'12');assert.equal(await page.locator('#chartVpdRange').inputValue(),'0.3');
 for(const[id,value]of[['chartTemperatureRange',''],['chartTemperatureRange','-1'],['chartTemperatureRange','51'],['chartHumidityRange','101'],['chartVpdRange','11']]){
   const before=await page.evaluate(()=>localStorage.getItem('gt_chart_ranges'));await page.locator('#'+id).fill(value);await page.locator('#saveChartRangesBtn').click();assert.equal(await page.evaluate(()=>localStorage.getItem('gt_chart_ranges')),before);
   await page.reload();await page.addScriptTag({content:f.js});
 }
 for(const id of ['chartTemperatureRange','chartHumidityRange','chartVpdRange'])await page.locator('#'+id).fill('0');await page.locator('#saveChartRangesBtn').click();assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('gt_chart_ranges'))),{temperature:0,humidity:0,vpd:0});
 await page.evaluate(()=>localStorage.setItem('gt_chart_ranges','invalid json'));await page.reload();await page.addScriptTag({content:f.js});assert.equal(await page.locator('#chartTemperatureRange').inputValue(),'5');
 fs.mkdirSync('layout-previews',{recursive:true});
 for(const lang of ['de','en'])for(const width of [1500,1000,390]){
  await page.setViewportSize({width,height:1000});await page.evaluate(lang=>{document.getElementById('langSelect').value=lang;applyChartRangesI18n();},lang);
  assert.ok(await page.locator('#chartRangesTitle').isVisible());assert.equal(await page.locator('#chartRangesTitle').textContent(),lang==='de'?'Diagramme':'Charts');
  assert.ok(await page.locator('#chartRangesCard').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Card overflow');
  const overflow=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth,elements:[...document.querySelectorAll('body *')].filter(el=>el.getBoundingClientRect().right>innerWidth+1).map(el=>({tag:el.tagName,id:el.id,width:el.getBoundingClientRect().width})).slice(0,15)}));
  assert.ok(overflow.width<=width+1,'Page overflow '+JSON.stringify(overflow));
  await page.screenshot({path:`layout-previews/chart-settings-${lang}-${width}.png`,fullPage:true});
 }
 // A quota/storage failure must not report successful persistence.
 await page.evaluate(()=>{Storage.prototype.setItem=function(){throw new Error('synthetic quota failure')};});await page.locator('#saveChartRangesBtn').click();assert.equal(await page.locator('#chartRangesMsg').textContent(),'Save failed.');
 console.log('Chart settings browser: defaults, save/reload, zero/automatic, invalid bounds, corrupt storage, DE/EN responsive layout and storage failure passed');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});

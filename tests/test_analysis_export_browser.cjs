const fs=require('fs'),assert=require('node:assert/strict');const{chromium}=require('playwright');
(async()=>{
 const f=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const browser=await chromium.launch();const page=await browser.newPage({acceptDownloads:true});let fail=false,urls=[];
 await page.route('http://analysis-export.test/**',route=>{
  if(route.request().url().includes('/api/export/analysis.zip')){
   urls.push(route.request().url());return route.fulfill({status:fail?500:200,contentType:'application/zip',headers:{'Content-Disposition':'attachment; filename="growtent-2_2026-11-15_1200Z_24h.zip"'},body:fail?'{}':Buffer.from(f.zip_b64,'base64')});
  }
  return route.fulfill({contentType:'text/html; charset=utf-8',body:f.html});
 });
 await page.goto('http://analysis-export.test/dashboard');await page.addScriptTag({content:f.js});
 await page.evaluate(()=>{document.body.classList.remove('role-pending','role-guest');document.body.classList.add('role-admin');document.getElementById('exportCsvBtn').style.display='inline-block';});
 await page.locator('#exportCsvBtn').click();assert.equal(await page.locator('#analysisExportRange').inputValue(),'24h');assert.ok(await page.locator('#analysisExportDialog').evaluate(el=>el.open));
 const download=page.waitForEvent('download');await page.locator('#analysisExportDownload').click();const d=await download;assert.equal(d.suggestedFilename(),'growtent-2_2026-11-15_1200Z_24h.zip');const raw=fs.readFileSync(await d.path());assert.equal(raw.subarray(0,2).toString(),'PK');assert.ok(raw.includes(Buffer.from('camera.jpg')));assert.ok(raw.includes(Buffer.from('growtent.analysis.v1')));
 assert.match(urls[0],/tent_id=2&range=24h/);assert.equal(await page.locator('#analysisExportDialog').evaluate(el=>el.open),false);
 fail=true;await page.locator('#exportCsvBtn').click();await page.locator('#analysisExportRange').selectOption('48h');assert.match(await page.locator('#analysisExportHint').textContent(),/Kamerabild/);await page.locator('#analysisExportDownload').click();await page.waitForFunction(()=>document.getElementById('analysisExportStatus').textContent.includes('fehlgeschlagen'));
 assert.equal(await page.locator('#analysisExportDownload').isDisabled(),false);assert.equal(await page.locator('#analysisExportDialog').evaluate(el=>el.open),true);assert.match(urls.at(-1),/range=48h/);
 await page.locator('#analysisExportCancel').click();assert.equal(await page.locator('#analysisExportDialog').evaluate(el=>el.open),false);
 fs.mkdirSync('layout-previews',{recursive:true});
 for(const lang of ['de','en'])for(const width of [1200,390]){
  await page.setViewportSize({width,height:800});await page.evaluate(lang=>{currentLang=lang;openAnalysisExport();},lang);
  assert.equal(await page.locator('#analysisExportRange').inputValue(),'24h');assert.match(await page.locator('#analysisExportTitle').textContent(),/ZIP/);assert.equal(await page.locator('#analysisExportDialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1),true);
  await page.screenshot({path:`layout-previews/analysis-export-${lang}-${width}.png`});await page.keyboard.press('Escape');
 }
 console.log('Analysis export: real button/dialog, default/48h selection, ZIP attachment with JSON and JPEG, failure recovery, cancel/Escape and DE/EN desktop/mobile passed');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

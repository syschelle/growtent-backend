const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
(async()=>{
 const f=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));const browser=await chromium.launch();const page=await browser.newPage();let requests=0;
 await page.route('**/*',route=>{requests++;return route.fulfill({contentType:'text/html; charset=utf-8',body:f.html});});await page.goto('http://vpd-table.test/dashboard');await page.addScriptTag({content:f.js});
 await page.evaluate(()=>{document.body.classList.remove('role-pending','role-guest');document.body.classList.add('role-admin');window.ctx={tent:2,language:'de',unit:'C'};window.clock=Date.now();window.timer=null;
  GrowTentVpdTable.mount({getContext:()=>ctx,clock:()=>clock,setTimer:fn=>timer=fn});
  window.sample={'sensors.cur.temperatureC':23.8,'sensors.cur.humidityPct':52.6,'sensors.cur.vpdKpa':1.16,'settings.grow.targetVPD':1.17,'settings.grow.offsetLeafTemperature':-1.5,'settings.grow.currentPhase':1,'settings.grow.currentPhaseWeek':1};
  GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());});
 assert.equal(await page.locator('#vpdRangeAssessment').textContent(),'Außerhalb des Referenzbereichs');
 await page.evaluate(()=>GrowTentVpdTable.update(2,{...sample,'settings.grow.currentPhaseWeek':3},new Date(clock).toISOString()));
 assert.equal(await page.locator('#vpdRangeAssessment').textContent(),'Im Referenzbereich');
 await page.evaluate(()=>{clock+=120001;timer();});
 assert.equal(await page.locator('#vpdRangeAssessment').textContent(),'Referenzbereich offen');
 await page.evaluate(()=>{clock-=120001;GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());});
 // Guest read-only table controls must be clickable, while write controls stay blocked.
 await page.evaluate(()=>{document.body.classList.remove('role-admin');document.body.classList.add('role-guest');});
 for(const id of ['openVpdTableBtn','closeVpdTableBtn'])assert.notEqual(await page.locator('#'+id).evaluate(el=>getComputedStyle(el).pointerEvents),'none');
 assert.equal(await page.locator('#editVpdTargetBtn').evaluate(el=>getComputedStyle(el).pointerEvents),'none');
 await page.locator('#openVpdTableBtn').click();assert.equal(await page.locator('#vpdTableDialog').evaluate(el=>el.open),true);
 await page.locator('#closeVpdTableBtn').click();assert.equal(await page.locator('#vpdTableDialog').evaluate(el=>el.open),false);
 await page.evaluate(()=>{document.body.classList.remove('role-guest');document.body.classList.add('role-admin');});
 // Both VPD actions share one compact footer row instead of two stacked rows.
 await page.locator('#editVpdTargetBtn').evaluate(el=>el.style.display='inline-block');
 for(const width of [1640,800,390]){
  await page.setViewportSize({width,height:1000});
  const geometry=await page.locator('.vpd-card-actions').evaluate(row=>{const a=row.querySelector('#openVpdTableBtn').getBoundingClientRect(),b=row.querySelector('#editVpdTargetBtn').getBoundingClientRect(),c=row.closest('.card').getBoundingClientRect();return{ay:a.y,by:b.y,aw:a.width,cw:c.width,right:a.right,next:b.left,height:row.getBoundingClientRect().height};});
  assert.ok(Math.abs(geometry.ay-geometry.by)<2,'VPD actions share a row');assert.ok(geometry.aw<geometry.cw/2,'Table action stays compact');assert.ok(geometry.right<=geometry.next,'Actions do not overlap');assert.ok(geometry.height<=34,'One compact footer row');
 }
 const before=requests;await page.locator('#openVpdTableBtn').click();assert.equal(await page.locator('#vpdReferenceTable tbody tr').count(),16);assert.equal(await page.locator('#vpdReferenceTable tbody td').count(),400);assert.equal(await page.locator('#vpdReferenceTable td[data-current]').count(),1);assert.match(await page.locator('#vpdTableReadings').textContent(),/IST-VPD1,16 kPa/);
 assert.match(await page.locator('#vpdTablePhase').textContent(),/Woche 1.*0,40–0,80/);
 assert.ok(await page.locator('#vpdReferenceTable td[data-phase-range]').count()>0);
 for(const [phase,week,pattern]of [[1,3,/0,80–1,20/],[1,7,/Woche 7.*0,80–1,20/],[2,1,/0,80–1,20/],[2,3,/1,20–1,60/]]){
  await page.evaluate(({phase,week})=>GrowTentVpdTable.update(2,{...sample,'settings.grow.currentPhase':phase,'settings.grow.currentPhaseWeek':week},new Date(clock).toISOString()),{phase,week});
  assert.match(await page.locator('#vpdTablePhase').textContent(),pattern);
 }
 await page.evaluate(()=>GrowTentVpdTable.update(2,{...sample,'settings.grow.currentPhase':3},new Date(clock).toISOString()));assert.match(await page.locator('#vpdTablePhase').textContent(),/Trocknung/);assert.equal(await page.locator('#vpdReferenceTable td[data-phase-range]').count(),0);
 await page.evaluate(()=>GrowTentVpdTable.update(2,{...sample,'settings.grow.currentPhaseWeek':null,'settings.grow.currentGrowWeek':4},new Date(clock).toISOString()));assert.match(await page.locator('#vpdTablePhase').textContent(),/offen/);assert.equal(await page.locator('#vpdReferenceTable td[data-phase-range]').count(),0);
 await page.evaluate(()=>GrowTentVpdTable.update(2,{...sample,'settings.grow.currentPhaseWeek':3},new Date(clock).toISOString()));
 assert.equal(await page.locator('#vpdTableDialog input,#vpdTableDialog select,#vpdTableDialog form').count(),0);
 assert.doesNotMatch(await page.locator('#vpdTablePhase').textContent(),/verlängert|gleicher Phasenbereich/);
 await page.evaluate(()=>{localStorage.setItem('gt_vpd_phase_split_2','{"vegetative":5}');GrowTentVpdTable.update(2,{...sample,'settings.grow.currentPhaseWeek':3},new Date(clock).toISOString());});
 assert.match(await page.locator('#vpdTablePhase').textContent(),/0,80–1,20/);
 await page.evaluate(()=>{ctx.unit='F';GrowTentVpdTable.refresh();});
 assert.equal(await page.locator('#vpdReferenceTable tbody th').first().textContent(),'68,0');
 assert.equal(await page.locator('#vpdReferenceTable tbody th').last().textContent(),'95,0');
 assert.match(await page.locator('#vpdTableReadings').textContent(),/Blatt-Offset-2,70 °F/);
 await page.evaluate(()=>{ctx.unit='C';GrowTentVpdTable.refresh();});
 // Night retains phase/week reference metadata, with exactly one night label.
 for(const language of ['de','en']){
  await page.evaluate(language=>{ctx.language=language;GrowTentVpdTable.update(2,{...sample,'settings.grow.currentPhase':2,'settings.grow.currentPhaseWeek':6,'cur.shelly.light.isOn':false},new Date(clock).toISOString());},language);
  assert.equal(await page.locator('#vpdTablePhase').textContent(),language==='de'?'Blüte · Woche 6 · spät · 1,20–1,60 kPa':'Flowering · Week 6 · late · 1.20–1.60 kPa');
  assert.equal(await page.locator('#vpdTablePhaseAssessment').textContent(),language==='de'?'Nachtphase':'Night phase');
  assert.equal((await page.locator('#vpdTableDialog').textContent()).match(language==='de'?/Nachtphase/g:/Night phase/g)?.length,1);
  assert.equal(await page.locator('#vpdReferenceTable td[data-phase-range]').count(),0);
 }
 await page.evaluate(()=>{ctx.language='de';GrowTentVpdTable.update(2,{...sample,'settings.grow.currentPhaseWeek':3},new Date(clock).toISOString());});
 const initial=await page.locator('#vpdReferenceTable td[data-current]').textContent();
 await page.evaluate(()=>{sample['settings.grow.offsetLeafTemperature']=0;GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());});assert.notEqual(await page.locator('#vpdReferenceTable td[data-current]').textContent(),initial);assert.match(await page.locator('#vpdTableReadings').textContent(),/IST-VPD1,16 kPa/);
 await page.evaluate(()=>{sample['settings.grow.offsetLeafTemperature']=null;GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());});assert.equal(await page.locator('#vpdReferenceTable td[data-current]').count(),0);assert.match(await page.locator('#vpdTableState').textContent(),/Blatt-Offset fehlt/);assert.equal(await page.locator('#vpdReferenceTable td.vpd-band-unknown').count(),400);
 await page.evaluate(()=>{sample['settings.grow.offsetLeafTemperature']=-1.5;GrowTentVpdTable.update(2,sample,new Date(clock).toISOString());clock+=120001;timer();});assert.equal(await page.locator('#vpdReferenceTable td[data-current]').count(),0);assert.match(await page.locator('#vpdTableState').textContent(),/Keine aktuellen/);assert.equal(await page.locator('#vpdReferenceTable td[data-phase-range]').count(),0);
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
 console.log('Phase/week highlights, extended phases, configurable browser-only splits, unknown/drying states; live VPD table: central value/offset/reference, markers, stale/missing data, tent races, outside range, auto-scroll, DE/EN C/F and responsive light/dark passed');await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

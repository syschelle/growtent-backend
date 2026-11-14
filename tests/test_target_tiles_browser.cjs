// Native dashboard dialogs tested with synthetic network responses only.
const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true}),context=await browser.newContext();
 let patches=[],profileReads=0,reject=false,unverified=false,readFail=false;
 let state={targetTemperature:22,targetVPD:1.17,currentPhase:1,floweringStart:'',dryingStart:''};
 const tent={id:3,name:'Test tent',backend_write_enabled:true,backend_controller_url:'http://controller.invalid:8080',has_backend_hmac_secret:true};
 await context.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname;
  if(path==='/dashboard')return route.fulfill({contentType:'text/html; charset=utf-8',body:url.searchParams.get('guest')==='1'?fixture.guest_static:fixture.dashboard_static});
  if(path==='/grow-profile')return route.fulfill({contentType:'text/html; charset=utf-8',body:fixture.editor});
  if(path==='/auth/whoami')return route.fulfill({json:{role:'admin'}});
  if(path==='/tents')return route.fulfill({json:[tent]});
  if(path==='/tents/3/grow-profile'){
   if(route.request().method()==='PATCH'){
    const patch=route.request().postDataJSON();patches.push(patch);
    if(reject)return route.fulfill({status:409,json:{detail:'Synthetic controller rejection'}});
    if(unverified)return route.fulfill({json:{verified:false,state:{runtime:state}}});
    state={...state,...patch};return route.fulfill({json:{verified:true,state:{runtime:state}}});
   }
   profileReads++;await new Promise(resolve=>setTimeout(resolve,180));
   if(readFail)return route.fulfill({status:503,json:{detail:'Synthetic read failure'}});
   return route.fulfill({json:{state:{runtime:state}}});
  }
  return route.abort();
 });
 const page=await context.newPage();await page.goto('http://backend.test/dashboard?embed=1');
 await page.addScriptTag({content:`
 let currentUserRole='admin',currentTentId=3,currentEspOnline=true,currentStatusOk=true,currentLang='de';
 let currentTentMeta=${JSON.stringify(tent)};
 window.refreshCalls=0;
 ${fixture.i18n_js}
 function tr(key){return I18N[currentLang]?.[key]||I18N.en[key]||key;}
 function txt(id,value){const el=document.getElementById(id);if(el)el.textContent=value;}
 async function loadLatest(){window.refreshCalls++;}
 ${fixture.modal_js}
 ${fixture.bindings_js}
 window.setTargetEditState=(patch)=>{if('role'in patch)currentUserRole=patch.role;if('online'in patch)currentEspOnline=patch.online;if('ok'in patch)currentStatusOk=patch.ok;if('ready'in patch)currentTentMeta.backend_write_enabled=patch.ready;if('tent'in patch)currentTentId=patch.tent;syncGrowProfileAction();};
 window.openScopedEditor=openGrowProfileEditor;
 window.setTargetSnapshot=(temperature,vpd)=>cacheTargetValuesFromPayload(currentTentId,{'settings.grow.targetTemperature':temperature,'settings.grow.targetVPD':vpd});
 window.applyTargetLabels=()=>{${fixture.labels_js}};
 syncGrowProfileAction();applyTargetLabels();setTargetSnapshot(22,1.17);
 `});
 const ids=['editTemperatureTargetBtn','editVpdTargetBtn','openGrowProfileBtn'];
 for(const gate of [{role:'guest'},{online:false},{ok:false},{ready:false}]){
  await page.evaluate(gate=>{setTargetEditState({role:'admin',online:true,ok:true,ready:true});setTargetEditState(gate);openScopedEditor('temperature');},gate);
  for(const id of ids)assert.equal(await page.locator('#'+id).isVisible(),false);
  assert.equal(await page.locator('#dbTargetDialog').evaluate(el=>el.open),false,'Native dialog respects readiness');
 }
 await page.evaluate(()=>setTargetEditState({role:'admin',online:true,ok:true,ready:true}));
 fs.mkdirSync('layout-previews',{recursive:true});
 for(const width of [1640,1000,390]){
  await page.setViewportSize({width,height:1000});
  for(const id of ids.slice(0,2)){
   const b=await page.locator('#'+id).evaluate(el=>{const b=el.getBoundingClientRect(),c=el.closest('.card').getBoundingClientRect();return {inside:b.left>=c.left&&b.right<=c.right+1&&b.bottom<=c.bottom+1};});assert.ok(b.inside);
  }
  await page.locator('#currentValuesGrid').screenshot({path:`layout-previews/target-tiles-${width}.png`});
 }
 for(const lang of ['de','en']){
  await page.setViewportSize({width:lang==='de'?1640:390,height:1000});
  await page.evaluate(lang=>{currentLang=lang;localStorage.setItem('gt_lang',lang);applyTargetLabels();},lang);
  for(const id of ids.slice(0,2))assert.equal(await page.locator('#'+id).innerText(),lang==='de'?'ändern':'change');
  const readsBefore=profileReads;
  await page.locator('#editTemperatureTargetBtn').click();
  assert.equal(await page.locator('#dbTargetDialog').evaluate(el=>el.matches(':modal')),true,'Uses native dialog');
  assert.equal(await page.locator('#dbGrowProfileFrame').getAttribute('src'),'about:blank','No target iframe navigation');
  assert.equal(await page.locator('#dbGrowProfileModal').isVisible(),false,'No target iframe loader');
  assert.equal(profileReads,readsBefore,'Existing dashboard value avoids an extra read');
  assert.equal(await page.locator('#dbTargetTitle').innerText(),lang==='de'?'Solltemperatur':'Target temperature');
  assert.equal(await page.locator('#dbTargetInput').inputValue(),String(state.targetTemperature));
  assert.ok((await page.locator('#dbTargetDialog').boundingBox()).width<=281);
  assert.ok(await page.locator('#dbTargetDialog').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'Native dialog fits');
  await page.locator('#dbTargetInput').fill('23.2');assert.equal(await page.locator('#dbTargetSave').isDisabled(),true);
  const desired=lang==='de'?23.5:24;
  await page.locator('#dbTargetInput').fill(String(desired));await page.locator('#dbTargetSave').click();await page.locator('#dbTargetStatus.success').waitFor();
  assert.deepEqual(patches.at(-1),{targetTemperature:desired});assert.equal(await page.locator('#dbTargetSave').isDisabled(),true);
  await page.locator('#dbTargetDialog').screenshot({path:`layout-previews/temperature-editor-${lang}.png`});
  await page.locator('#dbTargetCancel').click();assert.equal(await page.evaluate(()=>document.activeElement.id),'editTemperatureTargetBtn');
  await page.locator('#editVpdTargetBtn').click();
  assert.equal(await page.locator('#dbTargetTitle').innerText(),lang==='de'?'Soll-VPD':'Target VPD');assert.equal(await page.locator('#dbTargetCurrent').innerText(),'1.17');
  assert.equal(await page.locator('#dbTargetDialog iframe').count(),0);assert.equal(profileReads,readsBefore);
  await page.locator('#dbTargetInput').fill('1.25');assert.equal(await page.locator('#dbTargetSave').isDisabled(),true);
  reject=true;await page.locator('#dbTargetInput').fill('1.2');await page.locator('#dbTargetSave').click();await page.locator('#dbTargetStatus.error').waitFor();
  assert.deepEqual(patches.at(-1),{targetVPD:1.2});assert.equal(await page.locator('#dbTargetInput').inputValue(),'1.2');assert.equal(await page.locator('#dbTargetSave').isEnabled(),true);reject=false;
  await page.locator('#dbTargetDialog').screenshot({path:`layout-previews/vpd-editor-${lang}.png`});
  await page.keyboard.press('Escape');assert.equal(await page.locator('#dbTargetDialog').evaluate(el=>el.open),false);
 }
 // HTTP 200 without controller verification must not be displayed as success.
 await page.locator('#editTemperatureTargetBtn').click();unverified=true;await page.locator('#dbTargetInput').fill('24.5');await page.locator('#dbTargetSave').click();await page.locator('#dbTargetStatus.error').waitFor();
 assert.equal(await page.locator('#dbTargetCurrent').innerText(),'24.0');unverified=false;await page.locator('#dbTargetCancel').click();
 // Cold-cache fallback is a single read inside the already-open native dialog.
 await page.evaluate(()=>setTargetSnapshot(null,null));const beforeCold=profileReads;
 await page.locator('#editVpdTargetBtn').click();const initial=await page.locator('#dbTargetDialog').boundingBox();
 assert.equal(await page.locator('#dbTargetSave').isDisabled(),true);await page.waitForFunction(()=>document.getElementById('dbTargetInput').value==='1.17');
 assert.equal(profileReads,beforeCold+1);const ready=await page.locator('#dbTargetDialog').boundingBox();assert.ok(Math.abs(initial.width-ready.width)<1&&Math.abs(initial.height-ready.height)<2,'No opening resize');
 await page.locator('#dbTargetCancel').click();
 // A delayed read from a cancelled dialog cannot overwrite the next dialog.
 await page.evaluate(()=>setTargetSnapshot(null,null));await page.locator('#editTemperatureTargetBtn').click();await page.locator('#dbTargetCancel').click();
 await page.evaluate(()=>setTargetSnapshot(24,1.17));await page.locator('#editVpdTargetBtn').click();await page.waitForTimeout(220);
 assert.equal(await page.locator('#dbTargetInput').inputValue(),'1.17');assert.match(await page.locator('#dbTargetTitle').innerText(),/VPD/);await page.locator('#dbTargetCancel').click();
 // Reads that fail are explicit errors, never guessed values or enabled writes.
 readFail=true;await page.evaluate(()=>setTargetSnapshot(null,null));await page.locator('#editVpdTargetBtn').click();await page.locator('#dbTargetStatus.error').waitFor();
 assert.equal(await page.locator('#dbTargetSave').isDisabled(),true);await page.locator('#dbTargetCancel').click();readFail=false;
 // A tent change while editing cannot redirect this submission to another tent.
 await page.evaluate(()=>setTargetSnapshot(24,1.17));await page.locator('#editTemperatureTargetBtn').click();await page.locator('#dbTargetInput').fill('25');const beforeStale=patches.length;
 await page.evaluate(()=>{setTargetEditState({tent:4});document.getElementById('dbTargetForm').requestSubmit();});assert.equal(patches.length,beforeStale);assert.equal(await page.locator('#dbTargetSave').isDisabled(),true);await page.locator('#dbTargetCancel').click();await page.evaluate(()=>setTargetEditState({tent:3}));
 // The existing phase/date editor stays on its separate legacy path.
 await page.setViewportSize({width:1640,height:1000});await page.locator('#openGrowProfileBtn').click();const frame=page.frameLocator('#dbGrowProfileFrame');
 await frame.locator('#pageStatus.ok').waitFor({state:'attached'});await page.waitForFunction(()=>!document.getElementById('dbGrowProfileModal').classList.contains('is-loading'));
 assert.equal(await frame.locator('[data-profile-field]:visible').count(),3);assert.equal(await frame.locator('#tempInput').isVisible(),false);
 await frame.locator('#phaseInput').selectOption('2');await frame.locator('#flowerInput').fill('2026-11-01');await frame.locator('#saveProfileBtn').click();await frame.locator('#pageStatus.ok').waitFor();
 assert.deepEqual(patches.at(-1),{currentPhase:2,floweringStart:'2026-11-01'});await page.locator('#dbGrowProfileCloseBtn').click();
 assert.ok(await page.evaluate(()=>window.refreshCalls>0));
 await page.goto('http://backend.test/dashboard?embed=1&guest=1');for(const id of [...ids,'dbTargetDialog'])assert.equal(await page.locator('#'+id).count(),0,'Guest HTML excludes editing');
 console.log('Native target dialogs: instant sizing/cache, guarded read fallback, exact verified PATCH, limits, errors, cancellation, permissions and phase/date compatibility passed');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});

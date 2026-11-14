// Browser-only fixtures: all network requests are intercepted; no ESP or push access.
const fs=require('fs'),assert=require('node:assert/strict'),{chromium}=require('playwright');
const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
(async()=>{
 const browser=await chromium.launch({headless:true}),context=await browser.newContext();
 let patches=[],reject=false;
 let state={targetTemperature:22,targetVPD:1.17,currentPhase:1,floweringStart:'',dryingStart:''};
 const tent={id:3,name:'Test tent',backend_write_enabled:true,backend_controller_url:'http://controller.invalid:8080',has_backend_hmac_secret:true};
 // Fixture HTML is trusted repository output. DOMParser removes scripts without HTML regex filtering.
 await context.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname;
  if(path==='/dashboard')return route.fulfill({contentType:'text/html',body:url.searchParams.get('guest')==='1'?fixture.guest_static:fixture.dashboard_static});
  if(path==='/grow-profile')return route.fulfill({contentType:'text/html',body:fixture.editor});
  if(path==='/auth/whoami')return route.fulfill({json:{role:'admin'}});
  if(path==='/tents')return route.fulfill({json:[tent]});
  if(path==='/tents/3/grow-profile'){
   if(route.request().method()==='PATCH'){
    const patch=route.request().postDataJSON();patches.push(patch);
    if(reject)return route.fulfill({status:409,json:{detail:'Synthetic controller rejection'}});
    state={...state,...patch};
   }
   return route.fulfill({json:{state:{runtime:state}}});
  }
  return route.abort();
 });
 const page=await context.newPage();
 // Load dashboard without its polling/chart boot code; execute production modal code below.
 await page.goto('http://backend.test/dashboard?embed=1');
 await page.addScriptTag({content:`
 let currentUserRole='admin',currentTentId=3,currentEspOnline=true,currentStatusOk=true;
 let currentTentMeta=${JSON.stringify(tent)};
 window.testLang='de';window.refreshCalls=0;
 function tr(key){return ({editTemperatureTarget:{de:'Solltemperatur',en:'Target temperature'},editVpdTarget:{de:'Soll-VPD',en:'Target VPD'},growProfileTitle:{de:'Grow-Profil',en:'Grow profile'},editGrowProfile:{de:'Anpassen',en:'Adjust'}})[key]?.[window.testLang]||key;}
 function txt(id,value){const el=document.getElementById(id);if(el)el.textContent=value;}
 async function loadLatest(){window.refreshCalls++;}
 ${fixture.modal_js}
 ${fixture.bindings_js}
 window.setTargetEditState=(patch)=>{if('role'in patch)currentUserRole=patch.role;if('online'in patch)currentEspOnline=patch.online;if('ok'in patch)currentStatusOk=patch.ok;if('ready'in patch)currentTentMeta.backend_write_enabled=patch.ready;syncGrowProfileAction();};
 window.openScopedEditor=openGrowProfileEditor;
 syncGrowProfileAction();
 ['editTemperatureTargetBtn','editVpdTargetBtn','openGrowProfileBtn'].forEach(id=>txt(id,tr(id==='editTemperatureTargetBtn'?'editTemperatureTarget':id==='editVpdTargetBtn'?'editVpdTarget':'editGrowProfile')));
 `});
 const ids=['editTemperatureTargetBtn','editVpdTargetBtn','openGrowProfileBtn'];
 for(const gate of [{role:'guest'},{online:false},{ok:false},{ready:false}]){
  await page.evaluate(gate=>{setTargetEditState({role:'admin',online:true,ok:true,ready:true});setTargetEditState(gate);openScopedEditor('temperature');},gate);
  for(const id of ids)assert.equal(await page.locator('#'+id).isVisible(),false,'Unavailable edit control');
  assert.equal(await page.locator('#dbGrowProfileFrame').getAttribute('src'),'about:blank');
 }
 await page.evaluate(()=>setTargetEditState({role:'admin',online:true,ok:true,ready:true}));
 // Bottom-right position remains inside each measurement tile, including narrow layouts.
 fs.mkdirSync('layout-previews',{recursive:true});
 for(const width of [1640,1000,390]){
  await page.setViewportSize({width,height:1000});
  for(const id of ids.slice(0,2)){
   const geometry=await page.locator('#'+id).evaluate(el=>{const b=el.getBoundingClientRect(),c=el.closest('.card').getBoundingClientRect();return {left:b.left,right:b.right,bottom:b.bottom,cardLeft:c.left,cardRight:c.right,cardBottom:c.bottom};});
   assert.ok(geometry.left>=geometry.cardLeft&&geometry.right<=geometry.cardRight+1&&geometry.bottom<=geometry.cardBottom+1,'Button stays inside tile');
  }
  await page.locator('#currentValuesGrid').screenshot({path:`layout-previews/target-tiles-${width}.png`});
 }
 for(const lang of ['de','en']){
  await page.evaluate(lang=>{window.testLang=lang;localStorage.setItem('gt_lang',lang);},lang);
  const beforeTemp=String(state.targetTemperature);
  await page.locator('#editTemperatureTargetBtn').click();
  let frame=page.frameLocator('#dbGrowProfileFrame');await frame.locator('#tempInput').waitFor();
  await page.waitForFunction(expected=>document.querySelector('#dbGrowProfileFrame').contentDocument?.getElementById('tempInput')?.value===expected,beforeTemp);
  assert.equal(await frame.locator('[data-profile-field]:visible').count(),1);assert.equal(await frame.locator('#vpdInput').isVisible(),false);
  await frame.locator('#tempInput').fill('23.2');assert.equal(await frame.locator('#saveProfileBtn').isDisabled(),true);
  // Even a programmatically changed hidden field must not be included in this scope.
  await frame.locator('#vpdInput').evaluate(el=>{el.value='3.5';});await frame.locator('#phaseInput').evaluate(el=>{el.value='3';});
  await frame.locator('#tempInput').fill(lang==='de'?'23.5':'24');await frame.locator('#saveProfileBtn').click();
  await frame.locator('#pageStatus.ok').waitFor();assert.deepEqual(patches.at(-1),{targetTemperature:lang==='de'?23.5:24});
  await page.locator('.grow-profile-modal-card').screenshot({path:`layout-previews/temperature-editor-${lang}.png`});
  await page.locator('#dbGrowProfileCloseBtn').click();assert.equal(await page.locator('#dbGrowProfileFrame').getAttribute('src'),'about:blank');
  assert.equal(await page.evaluate(()=>document.activeElement.id),'editTemperatureTargetBtn');
  await page.locator('#editVpdTargetBtn').click();frame=page.frameLocator('#dbGrowProfileFrame');await frame.locator('#vpdInput').waitFor();
  await page.waitForFunction(()=>document.querySelector('#dbGrowProfileFrame').contentDocument?.getElementById('vpdInput')?.value==='1.17');
  assert.equal(await frame.locator('[data-profile-field]:visible').count(),1);assert.equal(await frame.locator('#tempInput').isVisible(),false);
  await frame.locator('#vpdInput').fill('1.25');assert.equal(await frame.locator('#saveProfileBtn').isDisabled(),true);
  reject=true;await frame.locator('#vpdInput').fill('1.2');await frame.locator('#saveProfileBtn').click();await frame.locator('#pageStatus.err').waitFor();
  assert.equal(await frame.locator('#vpdInput').inputValue(),'1.2');assert.equal(await frame.locator('#saveProfileBtn').isEnabled(),true);assert.deepEqual(patches.at(-1),{targetVPD:1.2});
  await page.locator('.grow-profile-modal-card').screenshot({path:`layout-previews/vpd-editor-${lang}.png`});reject=false;
  await page.locator('#dbGrowProfileCloseBtn').click();
 }
 await page.locator('#openGrowProfileBtn').click();const frame=page.frameLocator('#dbGrowProfileFrame');await frame.locator('#phaseInput').waitFor();
 await page.waitForFunction(()=>document.querySelector('#dbGrowProfileFrame').contentDocument?.getElementById('phaseInput')?.value==='1');
 assert.equal(await frame.locator('[data-profile-field]:visible').count(),3);assert.equal(await frame.locator('#tempInput').isVisible(),false);assert.equal(await frame.locator('#vpdInput').isVisible(),false);
 await frame.locator('#phaseInput').selectOption('2');await frame.locator('#flowerInput').fill('2026-11-01');await frame.locator('#saveProfileBtn').click();await frame.locator('#pageStatus.ok').waitFor();
 assert.deepEqual(patches.at(-1),{currentPhase:2,floweringStart:'2026-11-01'});await page.locator('#dbGrowProfileCloseBtn').click();
 assert.ok(await page.evaluate(()=>window.refreshCalls>0),'Dashboard refreshes after closing');
 await page.goto('http://backend.test/dashboard?embed=1&guest=1');for(const id of ids)assert.equal(await page.locator('#'+id).count(),0,'Guest HTML excludes controls');
 console.log('Target tiles: permissions/readiness, scoped partial PATCH, limits, failed saves, focus and responsive placement passed');
 await browser.close();
})().catch(error=>{console.error(error);process.exit(1)});

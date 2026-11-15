import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../api/app.py',import.meta.url),'utf8');
function extract(name){const a=source.indexOf('function '+name+'(');assert.ok(a>=0);let i=source.indexOf('{',a)+1,d=1;while(d){d+=(source[i]==='{')-(source[i]==='}');i++;}return source.slice(name==='saveTargetDialog'?a-6:a,i);}
let input={value:'74.3'},sent,status,confirmed=23.5,verified=true;
const ctx=vm.createContext({document:{getElementById:()=>input},tr:k=>k,canEditTarget:()=>true,targetDialogActive:()=>true,targetStatus:(message)=>status=message,syncTargetDialogActions(){},renderTargetDialog(){},fetch:async(url,options)=>{sent=JSON.parse(options.body);return {ok:true,json:async()=>({verified,state:{runtime:{targetTemperature:confirmed}}})};}});
vm.runInContext("let currentTempUnit='F',targetDialogContext=null,targetSnapshot={tentId:2};"+['targetNumber','targetSpec','targetDisplayValue','targetCanonicalValue','formatTargetInput','targetValueValid','targetError','saveTargetDialog'].map(extract).join('\n'),ctx);
assert.equal(vm.runInContext("targetSpec('temperature').unit",ctx),'°F');
for(const c of [18,18.5,23,23.5,30]){
 ctx.c=c;assert.equal(vm.runInContext("targetCanonicalValue({spec:targetSpec('temperature')},targetDisplayValue({spec:targetSpec('temperature')},c))",ctx),c);
 assert.equal(vm.runInContext("targetValueValid({spec:targetSpec('temperature')},c*1.8+32)",ctx),true);
}
assert.equal(vm.runInContext("formatTargetInput({spec:targetSpec('temperature')},23)",ctx),'73.4');
for(const v of [64,86.1,74,NaN]){ctx.v=v;assert.equal(vm.runInContext("targetValueValid({spec:targetSpec('temperature')},v)",ctx),false);}
vm.runInContext("targetDialogContext={tentId:2,spec:targetSpec('temperature'),current:23,loaded:true,dirty:true,busy:false}",ctx);
await vm.runInContext('saveTargetDialog({preventDefault(){}})',ctx);
assert.deepEqual(sent,{targetTemperature:23.5});assert.equal(status,'targetSaved');assert.equal(input.value,'74.3');assert.equal(vm.runInContext('targetSnapshot.targetTemperature',ctx),23.5);
// An unverified write must not update the canonical cache.
verified=false;input.value='75.2';confirmed=24;vm.runInContext('targetDialogContext.dirty=true',ctx);await vm.runInContext('saveTargetDialog({preventDefault(){}})',ctx);assert.equal(status,'targetNotConfirmed');assert.equal(vm.runInContext('targetSnapshot.targetTemperature',ctx),23.5);
vm.runInContext("currentTempUnit='C'",ctx);assert.equal(vm.runInContext("formatTargetInput({spec:targetSpec('temperature')},23)",ctx),'23');assert.equal(vm.runInContext("targetSpec('temperature').step",ctx),0.5);
assert.equal(vm.runInContext("formatTargetInput({spec:targetSpec('vpd')},1.17)",ctx),'1.17');
console.log('Temperature editor C/F grid, display, Celsius PATCH, verified confirmation and VPD isolation passed');

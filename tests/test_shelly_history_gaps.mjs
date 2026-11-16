import fs from 'node:fs';import assert from 'node:assert/strict';import vm from 'node:vm';
const source=fs.readFileSync(new URL('../api/app.py',import.meta.url),'utf8');
function extract(name){const a=source.indexOf('function '+name+'(');assert.ok(a>=0);let i=source.indexOf('{',a)+1,d=1;while(d){d+=(source[i]==='{')-(source[i]==='}');i++;}return source.slice(a,i);}
const context=vm.createContext({});
vm.runInContext(['finiteNumber','shellyHistoryPower'].map(extract).join('\n'),context);
for(const key of ['mainW','lightW','humidifierW','heatmatW','exhaustW']){
 context.key=key;context.points=[{[key]:4.8},{[key]:null},{[key]:4.7},{[key]:0},{}, {[key]:''},{[key]:false},{[key]:'5.12'}];
 assert.deepEqual(Array.from(vm.runInContext('points.map(p=>shellyHistoryPower(p,key))',context)),[4.8,null,4.7,0,null,null,null,5.1]);
 assert.ok(source.includes("const "+key+" = points.map(p => shellyHistoryPower(p,'"+key+"'));"));
}
console.log('Production Shelly history mappers: missing stays a gap, true zero remains zero for all five power series');

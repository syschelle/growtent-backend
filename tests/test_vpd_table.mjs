import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),api=require('../api/static/vpd-table.js');
assert.ok(Math.abs(api.calculate(24,60,-1.5)-0.9350402012690924)<1e-10);
assert.ok(api.calculate(24,60,0)>api.calculate(24,60,-1.5));
assert.equal(api.calculate(22,100,-5),0);
for(const v of [null,'',false,NaN,Infinity]){assert.equal(api.calculate(v,50,-1.5),null);assert.equal(api.calculate(22,50,v),null);}
for(const rh of [-1,101,null])assert.equal(api.calculate(22,rh,-1.5),null);
const now=Date.parse('2026-11-15T12:00:00Z'),payload={'sensors.cur.temperatureC':23.8,'sensors.cur.humidityPct':52.6,'sensors.cur.vpdKpa':1.16,'sensors.smoothed.vpdKpa':2,'settings.grow.targetVPD':1.17,'settings.grow.offsetLeafTemperature':-1.5};
let s=api.snapshot(payload,new Date(now).toISOString(),now);assert.equal(s.vpd,1.16);assert.equal(s.target,1.17);assert.equal(s.valid,true);
for(const flag of [false,null,0,'true'])assert.equal(api.snapshot({...payload,'sensors.climate.fresh':flag},new Date(now).toISOString(),now).valid,false);
assert.equal(api.snapshot(payload,new Date(now-120001).toISOString(),now).valid,false);
assert.equal(api.snapshot(payload,null,now).valid,false);assert.equal(api.snapshot({...payload,'sensors.cur.vpdKpa':null},new Date(now).toISOString(),now).vpd,null);
assert.equal(api.snapshot({...payload,'settings.grow.offsetLeafTemperature':null},new Date(now).toISOString(),now).offset,null);
assert.deepEqual(api.nearest(23.8,52.6),{temperature:24,humidity:52.5});assert.equal(api.nearest(19.9,52),null);assert.equal(api.nearest(24,86),null);
assert.equal(api.band(0.7),'low');assert.equal(api.band(1.17),'mid');assert.equal(api.band(null),'unknown');
const source=fs.readFileSync(new URL('../api/app.py',import.meta.url),'utf8');assert.ok(source.includes('GrowTentVpdTable?.update(requestedTentId,j.latest||{},j.captured_at)'));assert.ok(source.includes('GrowTentVpdTable?.invalidate(requestedTentId)'));
console.log('VPD table reference formula, offset, central ESP source, stale/null handling, nearest grid, ranges and backend polling hooks passed');
// Final user-supplied legend: late vegetation and early flower share 0.8–1.2.
const phase=(p,w,settings)=>api.phaseRange({'settings.grow.currentPhase':p,'settings.grow.currentPhaseWeek':w,'settings.grow.currentGrowWeek':99},settings);
for(const [p,w,min,max]of [[1,1,0.4,0.8],[1,2,0.4,0.8],[1,3,0.8,1.2],[1,7,0.8,1.2],[1,40,0.8,1.2],[2,1,0.8,1.2],[2,2,0.8,1.2],[2,3,1.2,1.6],[2,12,1.2,1.6]]){
 const r=phase(p,w);assert.equal(r.min,min);assert.equal(r.max,max);assert.equal(r.phase,p);
}
assert.equal(phase(1,7).extended,true);assert.equal(phase(2,1).late,false);
assert.equal(phase(1,3,{vegetative:5,flower:3}).max,0.8);
assert.equal(phase(2,3,{vegetative:5,flower:4}).max,1.2);
for(const w of [null,0,-1,1.5,true,''])assert.equal(phase(1,w).reason,'unknown');
assert.equal(phase(3,2).reason,'drying');assert.equal(phase(7,1).reason,'unknown');
assert.equal(api.phaseRange({'settings.grow.currentPhase':1,'settings.grow.currentGrowWeek':4}).reason,'unknown');
assert.equal(api.phaseRange({'settings.grow.currentPhase':1,'settings.grow.currentPhaseWeek':2},{vegetative:3,flower:3},false).reason,'unknown');
const memory=new Map(),storage={getItem:k=>memory.get(k)??null};
assert.deepEqual(api.loadPhaseSettings(2,storage),{vegetative:3,flower:3});
memory.set('gt_vpd_phase_split_2','{"vegetative":5,"flower":4}');assert.deepEqual(api.loadPhaseSettings(2,storage),{vegetative:5,flower:4});assert.equal(api.loadPhaseSettings(3,storage).vegetative,3);
for(const bad of ['invalid','null','{"vegetative":0,"flower":53}','{"vegetative":true,"flower":"4"}']){memory.set('gt_vpd_phase_split_2',bad);assert.deepEqual(api.loadPhaseSettings(2,storage),{vegetative:3,flower:3});}
assert.equal(api.inPhase(0.8,phase(1,3)),true);assert.equal(api.inPhase(1.17,phase(1,3)),true);assert.equal(api.inPhase(null,phase(1,3)),false);
console.log('Phase-aware reference: latest legend, week boundaries, extended phases, no guessed week, drying/stale, configurable per-tent splits passed');

// Table colour follows the displayed two-decimal value at every boundary.
assert.equal(api.calculate(33,60,-1.5).toFixed(2),'1.60');
assert.equal(api.band(api.calculate(33,60,-1.5)),'high');
for(const [v,expected]of [[0.3949,'outer'],[0.3951,'low'],[0.7949,'low'],[0.7951,'mid'],[1.1949,'mid'],[1.1951,'high'],[1.6049,'high'],[1.6051,'outer']])assert.equal(api.band(v),expected);
console.log('Displayed VPD rounding and colour boundary regressions passed');

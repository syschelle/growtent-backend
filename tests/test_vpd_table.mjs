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

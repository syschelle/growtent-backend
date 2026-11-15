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
const phase=(p,w)=>api.phaseRange({'settings.grow.currentPhase':p,'settings.grow.currentPhaseWeek':w,'settings.grow.currentGrowWeek':99});
for(const [p,w,min,max]of [[1,1,0.4,0.8],[1,2,0.4,0.8],[1,3,0.8,1.2],[1,7,0.8,1.2],[1,40,0.8,1.2],[2,1,0.8,1.2],[2,2,0.8,1.2],[2,3,1.2,1.6],[2,12,1.2,1.6]]){
 const r=phase(p,w);assert.equal(r.min,min);assert.equal(r.max,max);assert.equal(r.phase,p);
}
assert.equal(phase(1,7).extended,true);assert.equal(phase(2,1).late,false);
for(const w of [null,0,-1,1.5,true,''])assert.equal(phase(1,w).reason,'unknown');
assert.equal(phase(3,2).reason,'drying');assert.equal(phase(7,1).reason,'unknown');
assert.equal(api.phaseRange({'settings.grow.currentPhase':1,'settings.grow.currentGrowWeek':4}).reason,'unknown');
assert.equal(api.phaseRange({'settings.grow.currentPhase':1,'settings.grow.currentPhaseWeek':2},false).reason,'unknown');
assert.equal('loadPhaseSettings' in api,false);
assert.equal(api.inPhase(0.8,phase(1,3)),true);assert.equal(api.inPhase(1.17,phase(1,3)),true);assert.equal(api.inPhase(null,phase(1,3)),false);
console.log('Phase-aware reference: latest legend, week boundaries, extended phases, no guessed week, drying/stale, display-only defaults passed');

// Table colour follows the displayed two-decimal value at every boundary.
assert.equal(api.calculate(33,60,-1.5).toFixed(2),'1.60');
assert.equal(api.band(api.calculate(33,60,-1.5)),'high');
for(const [v,expected]of [[0.3949,'outer'],[0.3951,'low'],[0.7949,'low'],[0.7951,'mid'],[1.1949,'mid'],[1.1951,'high'],[1.6049,'high'],[1.6051,'outer']])assert.equal(api.band(v),expected);
console.log('Displayed VPD rounding and colour boundary regressions passed');

// Night display: actual light state wins over a fresh daily schedule.
const at=Date.parse('2026-11-15T22:00:00Z');
const schedule={ok:true,checked_at:new Date(at).toISOString(),on_minutes:18*60,off_minutes:6*60,matches:[{action:'on',timespec:'0 0 18 * * *'},{action:'off',timespec:'0 0 6 * * *'}]};
assert.equal(api.lightState({},schedule,at),'day');
assert.equal(api.lightState({'cur.shelly.light.isOn':false},schedule,at),'night');
assert.equal(api.lightState({'cur.shelly.light.isOn':true},null,at),'day');
assert.equal(api.lightState({},schedule,at+600001),'unknown');
assert.equal(api.lightState({},{...schedule,matches:[{action:'on',timespec:'0 0 18 * * MON'}]},at),'unknown');
for(const [iso,expected]of [['2026-11-15T05:00:00Z','night'],['2026-11-15T17:00:00Z','day'],['2026-11-16T00:00:00Z','day']]){
 const n=Date.parse(iso);assert.equal(api.lightState({},{...schedule,checked_at:iso},n),expected);
}
assert.equal(api.lightState({},null,at),'unknown');
const tracker=api.humidityTracker();
const reading=(elapsed,humidity=70,valid=true)=>({valid,humidity,capturedAt:new Date(at+elapsed).toISOString()});
for(let elapsed=0;elapsed<300000;elapsed+=60000)assert.equal(tracker(2,reading(elapsed),true,at+elapsed),false);
assert.equal(tracker(2,reading(300000),true,at+300000),true);
assert.equal(tracker(2,reading(360000,69.9),true,at+360000),false);
assert.equal(tracker(2,reading(420000),true,at+420000),false);
assert.equal(tracker(2,reading(720000),true,at+720000),false); // missing samples reset continuity
assert.equal(tracker(3,reading(780000),true,at+780000),false);
assert.equal(tracker(3,reading(840000,70,false),true,at+840000),false);
assert.equal(tracker(3,reading(900000),false,at+900000),false);
const frozen=api.humidityTracker();assert.equal(frozen(2,reading(0),true,at),false);assert.equal(frozen(2,reading(0),true,at+300000),false);
console.log('Night light state, midnight schedule and sustained humidity regressions passed');

// Exercise the production render with the table closed, as on the dashboard.
const nodes=new Map();
for(const id of ['vpdTableDialog','openVpdTableBtn','vpdTableTitle','closeVpdTableBtn','vpdRangeAssessment','vpd'])nodes.set(id,{textContent:'',title:'',open:false,addEventListener(){},classList:{remove(){},add(){}}});
const ctx={tent:2,language:'de',unit:'C'};let wall=at,tick;
const mounted=api.mount({document:{getElementById:id=>nodes.get(id)},getContext:()=>ctx,clock:()=>wall,setTimer:fn=>tick=fn});
const nightSample={...payload,'settings.grow.currentPhase':2,'settings.grow.currentPhaseWeek':3,'cur.shelly.light.isOn':false,'sensors.cur.humidityPct':70};
for(let i=0;i<=5;i++){wall=at+i*60000;mounted.update(2,nightSample,new Date(wall).toISOString());}
assert.equal(nodes.get('vpdRangeAssessment').textContent,'Nachtphase · Luftfeuchtigkeit seit ≥5 Min. ≥70 %');
ctx.language='en';mounted.refresh();assert.match(nodes.get('vpdRangeAssessment').textContent,/Night phase.*Humidity/);
wall+=120001;tick();assert.equal(nodes.get('vpdRangeAssessment').textContent,'Reference unavailable');
wall+=1;mounted.update(2,{...nightSample,'cur.shelly.light.isOn':true},new Date(wall).toISOString());assert.equal(nodes.get('vpdRangeAssessment').textContent,'Outside reference range');
console.log('Production dashboard render: DE/EN night humidity notice, stale expiry and daytime assessment passed');

// Same physical 20–35 C grid under both unit preferences; offsets are differences.
assert.deepEqual(api.nearest(35,50),{temperature:35,humidity:50});
assert.equal(api.nearest(35.01,50),null);
assert.equal(api.nearest(40,50),null);
assert.equal(api.temperatureDisplay(20,'F'),68);
assert.equal(api.temperatureDisplay(35,'F'),95);
assert.equal(api.temperatureDisplay(-1.5,'F',true),-2.7);
assert.equal(api.temperatureDisplay(-1.5,'C',true),-1.5);
assert.equal(api.temperatureDisplay(null,'F'),null);
console.log('20–35 C / 68–95 F table bounds and Fahrenheit temperature differences passed');

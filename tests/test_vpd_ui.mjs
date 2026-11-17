import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../api/app.py',import.meta.url),'utf8');
function extract(signature){const a=source.indexOf(signature);assert.ok(a>=0,signature);let i=source.indexOf('{',a)+1,depth=1;while(depth){depth+=(source[i]==='{')-(source[i]==='}');i++;}return source.slice(a,i);}
const config=[];
class Chart{constructor(ctx,cfg){this.data=cfg.data;this.options=cfg.options;config.push(cfg);}destroy(){}update(){}}
Chart.defaults={plugins:{legend:{labels:{generateLabels:chart=>chart.data.datasets.map((ds,i)=>({text:ds.label,datasetIndex:i}))}}}};
const preferences=new Map();
const localStorage={getItem:key=>preferences.get(key)??null,setItem:(key,value)=>preferences.set(key,value)};
const context={Chart,localStorage,document:{documentElement:{getAttribute:()=> 'dark'},getElementById:id=>id==='vpdChart'?{}:null},console};
vm.createContext(context);
const functions=['finiteNumber','espControlVpd','vpdHistoryValue','fmtNum','firstNum','chartLegendColor','legendLabelsWithCurrent','targetLineColor','climateChartRange','chartRangeSettings','buildCharts'];
vm.runInContext(`let currentLang='de',currentTempUnit='C',targetVpdChart=1.17,targetTempCChart=22;
let tempChart,humChart,vpdChart,soilMoistureChart,extTempChart,mainWChart,lightWChart,humidifierWChart,heatmatWChart,exhaustWChart,alphaChart,heapChart;
const tr=k=>({vpd:'VPD',average:'Durchschnitt',target:'Sollwert'}[k]||k);
function isHeatmatHistoryVisible(){return false;}function isExhaustHistoryVisible(){return false;}function syncRightAxisToLeft(){}function buildSingleChart(){return null;}function buildSoilMoistureChart(){}function extTempLabelBase(){return 'DS18B20';}
`+functions.map(n=>extract('function '+n+'(')).join('\n'),context);
context.payload={'sensors.cur.vpdKpa':0.94,'sensors.smoothed.vpdKpa':1.069,'curVpd':2};
assert.equal(vm.runInContext('espControlVpd(payload)',context),0.94);
for(const value of [null,undefined,'',' ',false,true,NaN,Infinity,-1]){
 context.payload['sensors.cur.vpdKpa']=value;assert.equal(vm.runInContext('espControlVpd(payload)',context),null);
 assert.equal(vm.runInContext('fmtNum(espControlVpd(payload),2)',context),'-');
}
context.payload['sensors.cur.vpdKpa']=0;assert.equal(vm.runInContext('espControlVpd(payload)',context),0);
context.payload['sensors.climate.fresh']=false;assert.equal(vm.runInContext('espControlVpd(payload)',context),null);
function chart(values){config.length=0;context.values=values;vm.runInContext('buildCharts(values.map((_,i)=>String(i)),[],[],values,[],[],[],[],[],[],[],[],[],[],[],[],[],[])',context);assert.equal(config.length,1);return config[0];}
let c=chart([0.94,null,0.96]);assert.deepEqual(Array.from(c.data.datasets[0].data),[0.94,null,0.96]);assert.equal(c.data.datasets[0].label,'VPD kPa');assert.equal(c.data.datasets[0].spanGaps,false);
assert.equal(c.data.datasets[2].data[0],0.95);assert.match(c.data.datasets[2].legendAfter,/min 0.94 \/ max 0.96/);
assert.ok(c.data.datasets.every(ds=>!ds.label.includes('Roh')));
c=chart([0.94,null]);assert.equal(c.data.datasets[2].data[0],0.94);
const labels=c.options.plugins.legend.labels.generateLabels({data:c.data});assert.equal(labels[0].text,'VPD kPa: -');
c=chart([null,null]);assert.ok(c.data.datasets[2].data.every(v=>v===null));assert.equal(c.data.datasets[2].legendAfter,'');
c=chart([0,1]);assert.equal(c.data.datasets[2].data[0],0.5);
assert.ok(source.includes('const vpd = points.map(vpdHistoryValue);'));
assert.equal((source.match(/const vpdKpa = espControlVpd\(payload\)/g)||[]).length,1);
assert.equal((source.match(/const vpdRaw  = espControlVpd\(d\)/g)||[]).length,1);
console.log('ESP VPD UI: strict source, null gaps, no zero/fallback, exact chart data, valid-only average/min/max and latest legend passed');

// Actual production chart configuration: wider climate axes, unchanged samples.
context.document.getElementById=id=>['tempChart','humChart'].includes(id)?{}:null;
vm.runInContext("function convertTempFromC(v){return currentTempUnit==='F'?v*9/5+32:v;}",context);
function climate(temp,hum,rawT=temp,rawH=hum){
 config.length=0;Object.assign(context,{temp,hum,rawT,rawH});
 vm.runInContext('buildCharts(temp.map((_,i)=>String(i)),temp,hum,[],[],[],[],[],[],[],[],[],rawT,rawH,[],[],[],[])',context);
 assert.equal(config.length,2);return config;
}
let [tc,hc]=climate([21.6,22],[56.4,58.4]);
assert.equal(tc.options.scales.y.suggestedMin,17);assert.equal(tc.options.scales.y.suggestedMax,27);
assert.equal(tc.options.scales.yR.suggestedMin,17);assert.equal(tc.options.scales.yR.suggestedMax,27);
assert.deepEqual(Array.from(tc.data.datasets[0].data),[21.6,22]);
assert.equal(hc.options.scales.y.suggestedMin,52.4);assert.equal(hc.options.scales.y.suggestedMax,62.4);
assert.equal(tc.options.scales.y.min,undefined);assert.equal(tc.options.scales.y.max,undefined);
[tc,hc]=climate([5,40],[1,99]);
assert.deepEqual(Array.from(tc.data.datasets[0].data),[5,40]); // suggestions allow Chart.js to include outliers
assert.equal(hc.options.scales.y.min,undefined);assert.equal(hc.options.scales.y.max,undefined);
vm.runInContext("currentTempUnit='F'",context);
[tc]=climate([71,72],[55,56]);assert.ok(Math.abs(tc.options.scales.y.suggestedMin-62.6)<1e-9);assert.ok(Math.abs(tc.options.scales.y.suggestedMax-80.6)<1e-9);
vm.runInContext("currentTempUnit='C';targetTempCChart=null",context);
[tc,hc]=climate([null,20],[null,0],[null,22],[null,0]);
assert.equal(tc.options.scales.y.suggestedMin,16);assert.equal(tc.options.scales.y.suggestedMax,26);
assert.equal(hc.options.scales.y.suggestedMin,0);assert.equal(hc.options.scales.y.suggestedMax,10);
[tc,hc]=climate([null],[null]);assert.equal(tc.options.scales.y.suggestedMin,undefined);assert.equal(hc.options.scales.y.suggestedMin,undefined);
console.log('Climate chart ranges: target ±5 C / ±9 F, humidity ±5 points, nulls, raw readings and unbounded excursions passed');

// Saved preferences drive production chart config; malformed values retain safe defaults.
assert.equal(vm.runInContext('chartRangeSettings().temperature',context),5);
for(const bad of ['broken','null','[]','{"temperature":false,"humidity":"15","vpd":-1}']) {
 localStorage.setItem('gt_chart_ranges',bad);
 assert.deepEqual(JSON.parse(vm.runInContext('JSON.stringify(chartRangeSettings())',context)),{temperature:5,humidity:10,vpd:0});
}
localStorage.setItem('gt_chart_ranges',JSON.stringify({temperature:2,humidity:20,vpd:0.4}));
vm.runInContext('targetTempCChart=22;targetVpdChart=1.17',context);
[tc,hc]=climate([21.8],[57]);assert.equal(tc.options.scales.y.suggestedMin,20);assert.equal(tc.options.scales.y.suggestedMax,24);assert.equal(hc.options.scales.y.suggestedMin,47);assert.equal(hc.options.scales.y.suggestedMax,67);
context.document.getElementById=id=>id==='vpdChart'?{}:null;
c=chart([1.15,1.18]);assert.ok(Math.abs(c.options.scales.y.suggestedMin-0.97)<1e-9);assert.ok(Math.abs(c.options.scales.y.suggestedMax-1.37)<1e-9);assert.equal(c.options.scales.y.min,undefined);assert.equal(c.options.scales.y.max,undefined);
localStorage.setItem('gt_chart_ranges',JSON.stringify({temperature:0,humidity:0,vpd:0}));
c=chart([1.15,1.18]);assert.equal(c.options.scales.y.suggestedMin,undefined);
context.document.getElementById=id=>['tempChart','humChart'].includes(id)?{}:null;
[tc,hc]=climate([21.8],[57]);assert.equal(tc.options.scales.y.suggestedMin,undefined);assert.equal(hc.options.scales.y.suggestedMin,undefined);
vm.runInContext("currentTempUnit='F'",context);localStorage.setItem('gt_chart_ranges','{"temperature":2}');[tc]=climate([71.6],[57]);assert.ok(Math.abs(tc.options.scales.y.suggestedMin-68)<1e-9);assert.ok(Math.abs(tc.options.scales.y.suggestedMax-75.2)<1e-9);
console.log('Saved chart preferences: defaults, corruption, bounds, custom ranges, automatic mode and Fahrenheit passed');

// Humidity average uses only the displayed smoothed series, not raw readings.
// Rebuilding with a different period must replace the statistics, including gaps.
const humidityAverage=(hum,raw=hum)=>climate(hum.map(()=>22),hum,hum.map(()=>22),raw)[1];
function checkHumidity(hum,raw,avg,suffix,legendText){
 const hc=humidityAverage(hum,raw);
 const [main,rawDs,right,mean,white]=hc.data.datasets;
 assert.deepEqual(Array.from(main.data),hum);
 assert.deepEqual(Array.from(rawDs.data),raw);
 assert.equal(right.yAxisID,'yR');
 assert.equal(mean.label,'Durchschnitt %');
 assert.equal(mean.legendAfter,suffix);
 assert.deepEqual(Array.from(mean.data),hum.map(()=>avg));
 assert.deepEqual(Array.from(white.data),hum.map(()=>avg));
 assert.equal(mean.borderColor,'#ef4444');
 assert.deepEqual(Array.from(mean.borderDash),[8,8]);
 assert.equal(white.borderColor,'#ffffff');
 assert.equal(white.borderDashOffset,8);
 const legend=hc.options.plugins.legend.labels.generateLabels({data:hc.data});
 assert.equal(legend[3].text,legendText);
 assert.equal(legend[4].text,'');
 assert.equal(hc.options.plugins.legend.labels.filter(legend[4]),false);
 return hc;
}
checkHumidity([56.4,null,58.4],[90,91,92],57.4,' (min 56.4 / max 58.4)','Durchschnitt %: 57.4 (min 56.4 / max 58.4)');
checkHumidity([null,undefined,'',false,NaN,Infinity,0,20],[50,50,50,50,50,50,50,50],10,' (min 0.0 / max 20.0)','Durchschnitt %: 10.0 (min 0.0 / max 20.0)');
checkHumidity([null,null],[70,80],null,'','Durchschnitt %: -');
checkHumidity([0],[50],0,' (min 0.0 / max 0.0)','Durchschnitt %: 0.0 (min 0.0 / max 0.0)');
checkHumidity([100,100],[99,98],100,' (min 100.0 / max 100.0)','Durchschnitt %: 100.0 (min 100.0 / max 100.0)');
checkHumidity([49,50,51.1],[49,50,51.1],50,' (min 49.0 / max 51.1)','Durchschnitt %: 50.0 (min 49.0 / max 51.1)');
assert.ok(source.includes("average: 'Average'"));
console.log('Humidity history: smoothed-only mean, min/max, missing/invalid values, real zero, one-decimal legend, range rebuild and matching line style passed');

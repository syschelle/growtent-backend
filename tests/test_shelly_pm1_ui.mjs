import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync(new URL('../api/app.py',import.meta.url),'utf8');
function extract(name){const a=source.indexOf('function '+name+'(');assert.ok(a>=0);let i=source.indexOf('{',a)+1,d=1;while(d){d+=(source[i]==='{')-(source[i]==='}');i++;}return source.slice(a,i);}
const container={innerHTML:'',querySelectorAll:()=>[]};
const context=vm.createContext({document:{getElementById:()=>container},tr:k=>({on:'AN',off:'AUS'}[k]||k),shellyIcon:()=>'',shellyName:()=> 'Heizmatte',formatShellyChangeTime:()=>'-',shellyLastSwitches:{},shellyLastActivity:{},shellyLastActivityDirect:{},shellyMainDirectTs:null});
vm.runInContext(['finiteNumber','normalizeShellyDeviceFromPayload','applyDirectShellyReading','renderShellyDevices'].map(extract).join('\n'),context);
context.data={'settings.shelly.heatmat.ip':'192.0.2.1','settings.shelly.heatmat.gen':3,'cur.shelly.heatmat.isOn':true,'cur.shelly.heatmat.Watt':46.1,'cur.shelly.heatmat.Wh':40.7};
context.state={isOn:true,meteringOnly:true,Watt:46.1,Wh:40.7};
vm.runInContext("applyDirectShellyReading(data,'heatmat',state);renderShellyDevices(data)",context);
assert.match(container.innerHTML,/46\.1 W/);assert.match(container.innerHTML,/0\.041 kWh/);assert.match(container.innerHTML,/shelly-card-on/);assert.match(container.innerHTML,/>AN</);assert.doesNotMatch(container.innerHTML,/data-shelly-toggle/);
context.state={isOn:true,meteringOnly:true,Watt:null,Wh:null};vm.runInContext("applyDirectShellyReading(data,'heatmat',state)",context);assert.equal(context.data['cur.shelly.heatmat.Watt'],46.1);assert.equal(context.data['cur.shelly.heatmat.Wh'],40.7);
context.state={isOn:true,meteringOnly:true,Watt:0,Wh:40.7};vm.runInContext("applyDirectShellyReading(data,'heatmat',state);renderShellyDevices(data)",context);assert.match(container.innerHTML,/0\.0 W/);assert.match(container.innerHTML,/>AN</);
context.data['cur.shelly.heatmat.Watt']=null;context.data['cur.shelly.heatmat.Wh']=null;vm.runInContext('renderShellyDevices(data)',context);assert.doesNotMatch(container.innerHTML,/0\.0 W|0\.000 kWh/);
context.data['cur.shelly.heatmat.isOn']=false;vm.runInContext('renderShellyDevices(data)',context);assert.match(container.innerHTML,/shelly-card-off/);assert.match(container.innerHTML,/>AUS</);
console.log('PM1 live direct merge and production dashboard: ON/green, real Watt/Wh, zero load, no null-to-zero and no heatmat toggle passed');

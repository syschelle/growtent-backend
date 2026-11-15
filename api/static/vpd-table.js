/* Read-only VPD reference table. Never supplies a controller value or write API. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.GrowTentVpdTable=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 function number(v){if(v===null||typeof v==='boolean'||!['string','number'].includes(typeof v)||(typeof v==='string'&&!v.trim()))return null;const n=Number(v);return Number.isFinite(n)?n:null;}
 function calculate(t,rh,offset){t=number(t);rh=number(rh);offset=number(offset);if(t===null||rh===null||offset===null||rh<0||rh>100)return null;
  const svp=v=>0.6107*Math.pow(10,7.5*v/(237.3+v));const v=svp(t+offset)-rh/100*svp(t);return Number.isFinite(v)?Math.max(0,v):null;
 }
 function snapshot(data,capturedAt,now=Date.now()){
  data=data||{};const at=Date.parse(capturedAt);const fresh=Number.isFinite(at)&&now-at>=-60000&&now-at<=120000&&(!('sensors.climate.fresh'in data)||data['sensors.climate.fresh']===true)&&(!('sensors.climate.status'in data)||data['sensors.climate.status']==='ok');
  const t=number(data['sensors.cur.temperatureC']),rh=number(data['sensors.cur.humidityPct']),vpd=number(data['sensors.cur.vpdKpa']);
  const valid=fresh&&t!==null&&rh!==null&&rh>=0&&rh<=100&&vpd!==null&&vpd>=0;
  const target=number(data['settings.grow.targetVPD']);
  return {valid,temperature:valid?t:null,humidity:valid?rh:null,vpd:valid?vpd:null,
   target:target!==null&&target>=0?target:null,offset:number(data['settings.grow.offsetLeafTemperature']),capturedAt:capturedAt||null};
 }
 function nearest(t,rh){if(t===null||rh===null||t<20||t>40||rh<25||rh>85)return null;return{temperature:Math.round(t),humidity:Math.round(rh/2.5)*2.5};}
 function band(v){if(v!==null)v=Number(v.toFixed(2));return v===null?'unknown':v<0.4||v>1.6?'outer':v<0.8?'low':v<1.2?'mid':'high';}
 function phaseRange(data,available=true){
  if(!available)return{reason:'unknown'};
  const phase=number(data?.['settings.grow.currentPhase']),week=number(data?.['settings.grow.currentPhaseWeek']);
  if(phase===3)return{phase,reason:'drying'};
  if(![1,2].includes(phase)||!Number.isInteger(week)||week<1)return{reason:'unknown'};
  const late=week>=3;
  const range=phase===1?(late?[0.8,1.2]:[0.4,0.8]):(late?[1.2,1.6]:[0.8,1.2]);
  return{phase,week,late,extended:week>5,min:range[0],max:range[1]};
 }
 function inPhase(value,range){return value!==null&&Number.isFinite(value)&&range.min!==undefined&&value>=range.min&&value<=range.max;}
 // Prefer actual switch state; only simple, fresh daily schedules are a fallback.
 function lightState(data,schedule,now=Date.now()){
  const value=data?.['cur.shelly.light.isOn'];
  if(value===true||value===1||value==='true'||value==='1')return 'day';
  if(value===false||value===0||value==='false'||value==='0')return 'night';
  const age=now-Date.parse(schedule?.checked_at);
  if(schedule?.ok!==true||!Number.isFinite(age)||age<0||age>600000)return 'unknown';
  const matches=schedule.matches;
  if(!Array.isArray(matches)||matches.length!==2||!['on','off'].every(a=>matches.filter(m=>m.action===a).length===1))return 'unknown';
  if(!matches.every(m=>{const parts=String(m.timespec||'').trim().split(/\s+/);return parts.length===6&&parts.slice(3).every(p=>p==='*');}))return 'unknown';
  const on=number(schedule.on_minutes),off=number(schedule.off_minutes);
  if(!Number.isInteger(on)||!Number.isInteger(off)||on<0||off<0||on>=1440||off>=1440||on===off)return 'unknown';
  const parts=new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Berlin',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(now));
  const minute=Number(parts.find(p=>p.type==='hour').value)*60+Number(parts.find(p=>p.type==='minute').value);
  return ((minute-on+1440)%1440<(off-on+1440)%1440)?'day':'night';
 }
 function humidityTracker(){
  let state=null;
  return (tent,s,night,now)=>{
   const at=Date.parse(s.capturedAt);
   if(!night||!s.valid||s.humidity<70){state=null;return false;}
   if(!state||state.tent!==String(tent)||at<state.last||at-state.last>120000)state={tent:String(tent),since:at,last:at};
   if(at>state.last)state.last=at;
   return state.last-state.since>=300000;
  };
 }
 let controller=null;
 function mount({getContext,document:doc=globalThis.document,clock=()=>Date.now(),setTimer=globalThis.setInterval}){
  const dialog=doc.getElementById('vpdTableDialog'),button=doc.getElementById('openVpdTableBtn');if(!dialog||!button)return;
  let latest=null,centerMarker=false,lastRenderedTent=null;const humidWarning=humidityTracker();
  function render(){
   const ctx=getContext(),de=ctx.language==='de',unit=ctx.unit==='F'?'F':'C';
   const labels=de?{title:'VPD-Tabelle',close:'Schließen',temp:'Temperatur',humidity:'Luftfeuchtigkeit',control:'IST-VPD',target:'Soll-VPD',offset:'Blatt-Offset',reference:'Referenz aus T/rF',current:'Aktuelle Werte',missing:'Keine aktuellen gültigen ESP-Klimawerte.',noOffset:'Blatt-Offset fehlt: Referenzwerte nicht verfügbar.',outside:'Aktueller Messpunkt liegt außerhalb des Tabellenbereichs.',hint:'Referenzwerte aus Temperatur, Luftfeuchtigkeit und Blatt-Offset.',legend:'VPD-Referenzbereiche (kPa), keine automatische Sollwertvorgabe.',caption:'Temperatur × relative Luftfeuchtigkeit – Referenz-VPD in kPa'}:
    {title:'VPD table',close:'Close',temp:'Temperature',humidity:'Relative humidity',control:'Actual VPD',target:'Target VPD',offset:'Leaf offset',reference:'Reference from T/RH',current:'Current readings',missing:'No current valid ESP climate readings.',noOffset:'Leaf offset unavailable: reference values unavailable.',outside:'Current readings are outside the table range.',hint:'Reference values from temperature, humidity and leaf offset. ESP control VPD is unchanged and may differ due to smoothing. The marker is rounded to the nearest grid cell.',legend:'VPD reference bands (kPa), not automatic target settings.',caption:'Temperature × relative humidity – reference VPD in kPa'};
   button.textContent=labels.title;doc.getElementById('vpdTableTitle').textContent=labels.title;doc.getElementById('closeVpdTableBtn').textContent=labels.close;
   if(lastRenderedTent!==String(ctx.tent)){centerMarker=true;lastRenderedTent=String(ctx.tent);}
   const s=latest&&String(latest.tent)===String(ctx.tent)?snapshot(latest.data,latest.at,clock()):snapshot({},null,clock());
   const marker=s.valid?nearest(s.temperature,s.humidity):null;
   const sameTent=String(latest?.tent)===String(ctx.tent);
   const light=s.valid&&sameTent?lightState(latest.data,ctx.lightSchedule,clock()):'unknown';
   const night=light==='night';
   const warning=humidWarning(ctx.tent,s,night,clock());
   const nightText=de?'Nachtphase':'Night phase';
   const nightAssessment=nightText+(warning?(de?' · Luftfeuchtigkeit seit ≥5 Min. ≥70 %':' · Humidity ≥70% for ≥5 min'):'');
   const range=night?{reason:'night'}:phaseRange(latest?.data,s.valid&&sameTent);
   const assessment=doc.getElementById('vpdRangeAssessment');
   if(assessment){const text=night?nightAssessment:range.reason?(range.reason==='drying'?(de?'Trocknung': 'Drying'):(de?'Referenzbereich offen':'Reference unavailable')):(inPhase(s.vpd,range)?(de?'Im Referenzbereich':'Within reference range'):(de?'Außerhalb des Referenzbereichs':'Outside reference range'));assessment.textContent=text;assessment.title=text;}
   const current=doc.getElementById('vpd');
   if(current){for(const name of ['outer','low','mid','high','unknown'])current.classList.remove('vpd-band-'+name);current.classList.add('vpd-band-'+band(s.vpd));}
   if(!dialog.open)return;
   const format=(v,d=2)=>v===null?'—':v.toLocaleString(de?'de-DE':'en-GB',{minimumFractionDigits:d,maximumFractionDigits:d});
   const temp=v=>v===null?null:unit==='F'?v*1.8+32:v;
   const phaseText=night?nightText:range.reason?(range.reason==='drying'?(de?'Trocknung – kein Phasenbereich markiert.':'Drying – no phase range highlighted.'):(de?'Phase/Woche offen – kein Phasenbereich markiert.':'Phase/week unavailable – no phase range highlighted.')):
    `${range.phase===1?(de?'Vegetativ':'Vegetative'):(de?'Blüte':'Flowering')} · ${de?'Woche':'Week'} ${range.week} · ${range.late?(de?'spät':'late'):(de?'früh':'early')} · ${format(range.min)}–${format(range.max)} kPa`;
   doc.getElementById('vpdTablePhase').textContent=phaseText;
   doc.getElementById('vpdTablePhaseAssessment').textContent=night?nightAssessment:range.reason?'':(inPhase(s.vpd,range)?(de?'IST-VPD im Referenzbereich.':'ESP control value within reference range.'):(de?'IST-VPD außerhalb des Referenzbereichs.':'ESP control value outside reference range.'));
   doc.getElementById('vpdPhaseRangeKey').textContent=de?'Umrandung: aktueller Phasenbereich':'Outline: current phase range';

   const summary=doc.getElementById('vpdTableReadings');summary.replaceChildren();
   const data=[[labels.temp,format(temp(s.temperature),1)+' °'+unit],[labels.humidity,format(s.humidity,1)+' %'],[labels.control,format(s.vpd)+' kPa'],[labels.target,format(s.target)+' kPa'],[labels.offset,format(s.offset)+' °C'],[labels.reference,format(calculate(s.temperature,s.humidity,s.offset))+' kPa']];
   for(const[label,value]of data){const item=doc.createElement('div'),dt=doc.createElement('dt'),dd=doc.createElement('dd');dt.textContent=label;dd.textContent=value;item.append(dt,dd);summary.append(item);}
   const note=[!s.valid?labels.missing:'',s.offset===null?labels.noOffset:'',s.valid&&!marker?labels.outside:''].filter(Boolean).join(' ');
   doc.getElementById('vpdTableState').textContent=note;
   doc.getElementById('vpdTableHint').textContent=labels.hint;
   doc.getElementById('vpdTableLegendText').textContent=labels.legend;
   doc.getElementById('vpdTableGridCaption').textContent=labels.caption;
   const table=doc.getElementById('vpdReferenceTable'),scroll=table.parentElement,top=scroll.scrollTop,left=scroll.scrollLeft;table.replaceChildren();
   table.classList.toggle('vpd-reference-active',!range.reason);
   const caption=doc.createElement('caption');caption.textContent=labels.caption;table.append(caption);
   const head=doc.createElement('thead'),hr=doc.createElement('tr'),corner=doc.createElement('th');corner.textContent='°'+unit+' / %';corner.scope='col';hr.append(corner);
   const humidities=Array.from({length:25},(_,i)=>85-i*2.5);
   for(const rh of humidities){const th=doc.createElement('th');th.scope='col';th.textContent=format(rh,1);if(marker&&marker.humidity===rh)th.className='vpd-current-axis';hr.append(th);}head.append(hr);table.append(head);
   const body=doc.createElement('tbody');
   for(let t=20;t<=40;t++){
    const row=doc.createElement('tr'),th=doc.createElement('th');th.scope='row';th.textContent=format(temp(t),unit==='F'?1:0);if(marker&&marker.temperature===t)th.className='vpd-current-axis';row.append(th);
    for(const rh of humidities){const td=doc.createElement('td'),v=calculate(t,rh,s.offset);td.textContent=format(v);td.className='vpd-band-'+band(v);if(inPhase(v===null?null:Math.round(v*100)/100,range))td.dataset.phaseRange='true';td.title=`${format(temp(t),1)} °${unit} / ${format(rh,1)} %: ${format(v)} kPa`;
     if(marker&&s.offset!==null&&marker.temperature===t&&marker.humidity===rh){td.dataset.current='true';td.setAttribute('aria-current','true');td.textContent+=' ★';}
     row.append(td);
    }body.append(row);
   }table.append(body);scroll.scrollTop=top;scroll.scrollLeft=left;
   if(centerMarker){const cell=table.querySelector('[data-current]');if(cell){const c=cell.getBoundingClientRect(),r=scroll.getBoundingClientRect();scroll.scrollLeft+=c.left-r.left-scroll.clientWidth/2+c.width/2;scroll.scrollTop+=c.top-r.top-scroll.clientHeight/2+c.height/2;}centerMarker=false;}
  }
  button.addEventListener('click',()=>{centerMarker=true;dialog.showModal();render();});
  doc.getElementById('closeVpdTableBtn').addEventListener('click',()=>dialog.close());
  setTimer(()=>render(),5000);
  controller={update(tent,data,at){if(String(tent)!==String(getContext().tent))return;latest={tent,data:{...data},at};render();},invalidate(tent){if(String(tent)===String(getContext().tent)){latest=null;render();}},refresh:render};
  render();return controller;
 }
 return {calculate,snapshot,nearest,band,phaseRange,inPhase,lightState,humidityTracker,mount,update(...args){controller?.update(...args);},invalidate(...args){controller?.invalidate(...args);},refresh(){controller?.refresh();}};
});

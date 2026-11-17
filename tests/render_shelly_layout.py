"""Isolated production dashboard styles and Shelly renderer; no live devices."""
import sys,json,re
from pathlib import Path
import ast
node=next(n for n in ast.parse((Path(__file__).resolve().parents[1]/'api/app.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='dashboard_page')
html=max((n.value for n in ast.walk(node) if isinstance(n,ast.Constant) and isinstance(n.value,str)),key=len);js='\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',html,re.S));a=js.index('          function renderShellyDevices(d)');b=js.index('          let tempChart;',a)
css='\n'.join(re.findall(r'<style[^>]*>(.*?)</style>',html,re.S))
helpers='''const finiteNumber=v=>Number(v); const shellyLastSwitches={},shellyLastActivity={},shellyLastActivityDirect={}; const shellyMainDirectTs=null; const formatShellyChangeTime=()=> 'vor 2 Min'; const shellyIcon=()=> '♨'; const shellyName=k=>({main:'Hauptschalter',light:'Licht',humidifier:'Luftbefeuchter',heater:'Heizung',heatmat:'Heizmatte',fan:'Lüfter',exhaust:'Abluft'})[k]; const tr=k=>({on:'AN',off:'AUS',lastChange:'Update',scheduleOn:'AN',scheduleOff:'AUS',lblIp:'IP',lblGen:'Gen',lblEnergy:'Energie',lblCost:'Kosten',toggle:'Umschalten',openShelly:'Shelly öffnen'})[k]||k; const normalizeShellyDeviceFromPayload=(d,k)=>({key:k,isOn:true,watt:218.4,wh:214416,cost:83.62,ip:'192.168.178.191',gen:3,line:'ON 0:00|OFF 0:00',meteringOnly:k==='heatmat'});'''
Path(sys.argv[1]).write_text(json.dumps({'html':'<html><head><style>'+css+'</style></head><body><div class="layout"><aside class="sidebar">Navigation</aside><main class="content"><div class="card"><div class="label">Shelly-Geräte</div><div id="shellyDevices" class="grid"></div></div></main></div></body></html>','js':helpers+js[a:b]+'renderShellyDevices({});'}))

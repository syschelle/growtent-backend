import json
import subprocess
from pathlib import Path
from test_irrigation_ui_runtime import render
from test_irrigation_integration import service_fixture


def test_backend_passes_through_esp_forecast_and_labels_older_firmware():
    service,store,client=service_fixture()
    client.state.update(next_run_at=1794646800,next_run_status='ready')
    summary=service.get(1)
    assert summary['next_run_at']==1794646800 and summary['next_run_status']=='ready'
    service,store,client=service_fixture()
    assert service.get(1)['next_run_status']=='firmware_update_required'
    client.state['enabled']=False;store.snapshot_value['state']=None;store.snapshot_value['checked_at']=None
    assert service.get(1)['next_run_status']=='disabled'


def test_production_next_run_label_ready_stale_blocked_and_s3():
    source=(Path(__file__).parents[1]/'api/app.py').read_text()
    start=source.index('          function irrigationNextLabel(')
    end=source.index('          async function readLightScheduleOnDemand(',start)
    formatter=source[start:end]
    js='''const vm=require('node:vm');const assert=require('node:assert/strict');
const code=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const context=vm.createContext({currentLang:'de',Date,formatNextRunDate:date=>'DATE:'+date.toISOString()});
vm.runInContext(code,context);
const show=data=>{context.summary=data;return vm.runInContext('irrigationNextLabel(summary)',context);};
const future=Math.floor(Date.now()/1000)+3600;
assert.ok(show({next_run_at:future,next_run_status:'ready'}).startsWith('DATE:'));
assert.ok(show({next_run_at:future,next_run_status:'stale_shelly'}).includes('Zeitplan veraltet'));
assert.ok(show({next_run_at:future,next_run_status:'ready',stale:true}).startsWith('Stand veraltet'));
assert.equal(show({next_run_at:null,next_run_status:'disabled'}),'Deaktiviert');
assert.equal(show({next_run_status:'drying_blocked'}),'Trocknung: gesperrt');
assert.ok(show({next_run_status:'firmware_update_required'}).includes('ESP-Update'));
assert.ok(show({next_run_at:future-7200,next_run_status:'ready'}).includes('Aktualisierung'));
assert.equal(show(null),'Nicht verfügbar');
context.currentLang='en';assert.equal(show({next_run_status:'disabled'}),'Disabled');
assert.equal(show({next_run_status:'watering_running'}),'Watering in progress');
'''
    subprocess.run(['node','-e',js],input=json.dumps(formatter),text=True,check=True)
    html=render('dashboard_page')
    assert 'if (c === 6 || c === 8)' in html
    assert 'computeNextIrrigationDateFromOnMin' not in html
    assert 'irrigationNextLabel(currentIrForecastState)' in html

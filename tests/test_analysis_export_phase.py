"""Historical phase labels, parity with the VPD table, and aggregation boundaries."""
import json
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from services.analysis_export import build_analysis_export, analysis_context, grow_phase_key, grow_phase_info
from test_analysis_export import END, exporter, reading
from test_vpd_source import Database

START=END-timedelta(hours=1)


def data(phase,week):
    return {'settings.grow.currentPhase':phase,'settings.grow.currentPhaseWeek':week,
            'settings.grow.currentGrowWeek':99}


@pytest.mark.parametrize('phase,week,stage,limits',[
    (1,1,'early',(0.4,0.8)),(1,2,'early',(0.4,0.8)),(1,3,'late',(0.8,1.2)),
    (2,1,'early',(0.8,1.2)),(2,2,'early',(0.8,1.2)),(2,3,'late',(1.2,1.6)),
    (2,6,'late',(1.2,1.6)),('2','12','late',(1.2,1.6)),(3,2,None,None),
    (2,None,None,None),(2,0,None,None),(2,2.5,None,None),(1,True,None,None)])
def test_reference_phase(phase,week,stage,limits):
    value=grow_phase_info(grow_phase_key(analysis_context(data(phase,week))))
    assert value['stage']==stage
    assert value['reference_vpd_kpa']==({'min':limits[0],'max':limits[1]} if limits else None)
    if stage:assert value['week']==int(week)
    elif int(phase)!=3:assert value['week'] is None


@pytest.mark.skipif(not shutil.which('node'),reason='Node.js unavailable')
def test_matches_production_vpd_table_phase_range():
    inputs=[data(p,w) for p in (0,1,2,3,4,None) for w in (None,0,1,2,3,6,30,2.5,True,'6')]
    js=Path(__file__).parents[1]/'api/static/vpd-table.js'
    results=json.loads(subprocess.check_output(['node','-e',
        'const api=require(process.argv[1]); const fs=require("fs"); console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,"utf8")).map(d=>api.phaseRange(d))));',str(js)],input=json.dumps(inputs).encode()))
    for payload,expected in zip(inputs,results):
        result=grow_phase_info(grow_phase_key(analysis_context(payload)))
        if 'min' in expected:
            assert result['reference_vpd_kpa']=={'min':expected['min'],'max':expected['max']}
            assert result['stage']==('late' if expected['late'] else 'early')
        else:assert result is None or result['reference_vpd_kpa'] is None


def test_labels_and_historical_bucket_context():
    rows=[(START,data(2,6)),(START+timedelta(seconds=10),data(2,6)),
          (START+timedelta(seconds=240),data(2,7))]
    out=build_analysis_export(2,rows,END,1)
    first=out['points'][0]['grow_phase']
    assert first=={'phase':'flowering','week':6,'stage':'late','label_de':'Blüte · Woche 6 · spät',
        'label_en':'Flowering · Week 6 · late','reference_vpd_kpa':{'min':1.2,'max':1.6}}
    assert out['points'][1]['grow_phase'] is None
    assert out['points'][2]['grow_phase']['week']==7
    assert out['grow_phase']==out['points'][2]['grow_phase']
    assert out['grow_phase_observed_at']=='2026-11-15T11:04:00.000Z'
    assert 'grow_phase_counts' not in out['points'][0]


def test_mixed_phase_including_missing_is_never_assigned_one_label():
    rows=[(START,data(1,2)),(START+timedelta(seconds=10),data(2,1)),
          (START+timedelta(seconds=20),{}),(START+timedelta(seconds=30),data(1,2))]
    out=build_analysis_export(2,rows,END,1)
    point=out['points'][0];assert point['grow_phase'] is None
    counts=point['grow_phase_counts']
    assert [c['n'] for c in counts]==[2,1,1]
    assert [c['grow_phase']['phase'] if c['grow_phase'] else None for c in counts]==['vegetative','flowering',None]
    assert sum(c['n'] for c in counts)==point['samples']
    assert out['grow_phase']['phase']=='vegetative'


def test_missing_latest_and_drying_do_not_reuse_previous_phase():
    out=build_analysis_export(2,[(START,data(3,1)),(START+timedelta(seconds=120),data(99,6))],END,1)
    assert out['points'][0]['grow_phase']['label_de']=='Trocknung'
    assert out['points'][0]['grow_phase']['reference_vpd_kpa'] is None
    assert out['points'][1]['grow_phase'] is None and out['grow_phase'] is None
    assert build_analysis_export(2,[],END,1)['grow_phase_observed_at'] is None


def test_adapted_attachment_keeps_phase_counts_and_existing_metrics():
    start=END-timedelta(hours=24);rows=[]
    for i in range(8640):
        payload=reading(**data(2,2 if i<4321 else 3))
        for role in ('main','light','humidifier','heater','heatmat','fan','exhaust'):
            payload[f'cur.shelly.{role}.Watt']=float(i%50)
            payload[f'cur.shelly.{role}.isOn']=bool(i%2)
        rows.append((start+timedelta(seconds=10*i),payload))
    response=exporter(Database(rows))(2,'24h');out=json.loads(response.body)
    assert len(response.body)<=1_000_000 and out['sizeAdapted']
    assert out['grow_phase']['stage']=='late'
    total={'early':0,'late':0}
    for p in out['points']:
        if 'grow_phase_counts' in p:
            for item in p['grow_phase_counts']:total[item['grow_phase']['stage']]+=item['n']
        elif p['grow_phase']:total[p['grow_phase']['stage']]+=p['samples']
    assert total=={'early':4321,'late':4319}
    assert sum(p['metrics']['exhaust_watt']['n'] for p in out['points'])==8640

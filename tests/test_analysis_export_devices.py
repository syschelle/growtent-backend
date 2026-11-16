"""Historical Shelly/context export: no live reads, guessed states or backfill."""
import copy
import json
from datetime import datetime, timedelta, timezone
import pytest
from services.analysis_export import build_analysis_export, SHELLY_ROLES
from test_analysis_export import exporter
from test_vpd_source import Database

END=datetime(2026,11,15,12,tzinfo=timezone.utc)
START=END-timedelta(hours=1)

def device(role, state=True, power=46.1, fresh=True, **extras):
    return {f'cur.shelly.{role}.isOn':state, f'cur.shelly.{role}.Watt':power,
        f'cur.shelly.{role}.Wh':40.7,f'cur.shelly.{role}.fresh':fresh,
        f'cur.shelly.{role}.ageMs':1500,**extras}

def test_all_roles_actual_metrics_and_source_unchanged():
    data={}
    for role in SHELLY_ROLES:data.update(device(role))
    before=copy.deepcopy(data)
    first=build_analysis_export(2,[(START,data)],END,1)['points'][0]
    assert set(first['shelly'])==set(SHELLY_ROLES)
    for result in first['shelly'].values():
        assert result['power_w']=={'avg':46.1,'min':46.1,'max':46.1,'n':1}
        assert result['energy_wh']['last']==40.7
        assert result['age_ms']['max']==1500
        assert result['state_last'] is True and result['fresh_samples']==1
    assert data==before


def test_zero_missing_and_stale_are_distinct_without_inferred_state():
    rows=[(START,device('heatmat',state=None,power=0)),
        (START+timedelta(seconds=10),device('heatmat',state=True,power=46.1,fresh=False)),
        (START+timedelta(seconds=20),device('heatmat',state=False,power=46.1)),
        (START+timedelta(seconds=30),{})]
    result=build_analysis_export(2,rows,END,1)['points'][0]['shelly']['heatmat']
    assert result['samples']==3 and result['unknown_samples']==2 and result['off_samples']==1
    assert result['power_w']['n']==2 and result['power_w']['min']==0
    assert result['fresh_samples']==2 and result['stale_samples']==1
    assert result['observed_changes']==0  # unknown breaks transition continuity
    legacy=device('light');del legacy['cur.shelly.light.fresh']
    result=build_analysis_export(2,[(START,legacy)],END,1)['points'][0]['shelly']['light']
    assert result['freshness_unknown_samples']==1 and result['fresh_samples']==0
    assert result['state_last'] is True


def test_gaps_missing_roles_and_event_limits():
    rows=[(START+timedelta(seconds=i),device('light',bool(i%2)))for i in range(30)]
    out=build_analysis_export(2,rows,END,1);d=out['points'][0]['shelly']['light']
    assert d['observed_changes']==29 and len(d['transitions'])==8
    assert out['eventDetailsOmitted']==21
    rows=[(START,device('light',False)),(START+timedelta(seconds=10),{}),
        (START+timedelta(seconds=20),device('light',True)),
        (START+timedelta(seconds=300),device('light',False))]
    out=build_analysis_export(2,rows,END,1)
    assert sum(p['shelly'].get('light',{}).get('observed_changes',0)for p in out['points'])==0


def test_phase_and_schedule_timeline_preserves_missing_and_changed_values():
    initial={'settings.grow.currentPhase':2,'settings.grow.currentPhaseWeek':6,
        'settings.shelly.light.on':'17:00','settings.shelly.light.off':'5:00',
        'settings.shelly.light.line':'192.0.2.1 | PASSWORD should never be exported'}
    changed={**initial,'settings.grow.currentPhaseWeek':7,'settings.shelly.light.off':'06:00'}
    out=build_analysis_export(2,[(START,initial),(START+timedelta(seconds=10),changed),
        (START+timedelta(seconds=20),{})],END,1)
    assert out['context_first']['phase_week']==6
    assert out['context_first']['light_schedule']=={'on':'17:00','off':'05:00'}
    assert out['context_timeline'][1]['phase_week']==7 and out['context_change_count']==2
    assert out['context_last']['phase'] is None
    assert out['context_last']['light_schedule']=={'on':None,'off':None}
    assert 'PASSWORD' not in json.dumps(out) and '192.0.2.1' not in json.dumps(out)
    empty=build_analysis_export(2,[],END,1)
    assert empty['context_first'] is None and empty['context_timeline']==[]


def test_context_cap_keeps_final_state_and_change_count():
    rows=[(START+timedelta(seconds=i),{'settings.grow.currentPhaseWeek':i+1}) for i in range(140)]
    out=build_analysis_export(2,rows,END,1)
    assert len(out['context_timeline'])==128 and out['context_change_count']==139
    assert out['context_details_omitted']==12 and out['context_last']['phase_week']==140


def test_size_guard_all_devices_keeps_counts_extrema_and_final_context():
    start=END-timedelta(hours=24);rows=[]
    for i in range(8640):
        data={'settings.grow.currentPhase':2,'settings.grow.currentPhaseWeek':6,
            'settings.shelly.light.on':'05:00','settings.shelly.light.off':'17:00'}
        for role in SHELLY_ROLES:data.update(device(role,bool(i%2),power=float(i%50)))
        rows.append((start+timedelta(seconds=i*10),data))
    response=exporter(Database(rows))(2,'24h');out=json.loads(response.body)
    assert len(response.body)<=1_000_000 and out['sizeAdapted'] is True
    assert out['sampleCount']==8640
    for role in SHELLY_ROLES:
        devices=[p['shelly'][role]for p in out['points']]
        assert sum(d['samples']for d in devices)==8640
        assert sum(d['on_samples']for d in devices)==4320
        assert sum(d['observed_changes']for d in devices)==8639
        assert max(d['power_w']['max']for d in devices)==49
    assert out['context_last']['phase_week']==6


def test_invalid_values_are_json_safe():
    data=device('light',power=float('inf'),fresh='true')
    data['cur.shelly.light.Wh']=float('nan')
    out=build_analysis_export(2,[(START,data)],END,1)
    d=out['points'][0]['shelly']['light']
    assert d['power_w']['n']==0 and d['unknown_samples']==1
    json.dumps(out,allow_nan=False)

import ast
import copy
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import Response
import pytest
from services.analysis_export import build_analysis_export,read_irrigation_events,HOURS
from test_vpd_source import Database,sample

END=datetime(2026,11,15,12,0,tzinfo=timezone.utc)

def reading(vpd=1.17,**extra):
    return sample(vpd,**{'sensors.smoothed.temperatureC':22.0,'sensors.smoothed.humidityPct':55.0,
        'settings.grow.targetTemperature':22,'settings.grow.targetVPD':1.17,
        'cur.shelly.humidifier.fresh':True,'cur.shelly.humidifier.isOn':False,
        'cur.shelly.humidifier.Watt':0,'sensors.cur.effectiveAlfaTempC':0.15,'sensors.cur.effectiveAlfaHumPct':0.15,**extra})

def test_daily_size_extrema_and_source_rows_unchanged():
    start=END-timedelta(hours=24)
    rows=[(start+timedelta(seconds=i*10),reading(1.0+(i%20)/100)) for i in range(8640)]
    before=copy.deepcopy(rows);out=build_analysis_export(2,rows,END)
    assert len(out['points'])==720 and out['bucketSeconds']==120 and out['sampleCount']==8640
    first=out['points'][0];assert first['samples']==12
    assert first['metrics']['vpd']=={'avg':1.055,'min':1,'max':1.11,'n':12}
    assert first['targets_last']['vpd']==1.17
    assert len(json.dumps(out,separators=(',',':'),ensure_ascii=False).encode())<1024*1024
    assert rows==before

@pytest.mark.parametrize('hours',[1,6,12,24,48])
def test_periods_and_empty_windows(hours):
    out=build_analysis_export(2,[],END,hours)
    assert out['bucketSeconds']==(240 if hours==48 else 120)
    assert out['count']<=720 and out['sampleCount']==0
    assert all(p['metrics']['vpd']['avg'] is None and p['metrics']['vpd']['n']==0 and p['targets_last'] is None for p in out['points'])
    assert out['gaps'][0]['seconds']==hours*3600


def test_raw_extremes_targets_and_observed_changes_are_not_averaged_away():
    start=END-timedelta(hours=1)
    rows=[(start,reading(**{'cur.shelly.humidifier.isOn':False})),
        (start+timedelta(seconds=10),reading(0.88,**{'sensors.cur.vpdRawKpa':0.6,'cur.shelly.humidifier.isOn':True,'cur.shelly.humidifier.Watt':20,'settings.grow.targetVPD':1.2})),
        (start+timedelta(seconds=30),reading(**{'cur.shelly.humidifier.isOn':False,'settings.grow.targetVPD':1.2}))]
    p=build_analysis_export(2,rows,END,1)['points'][0]
    assert p['metrics']['vpd']['min']==0.88 and p['metrics']['vpd_raw']['min']==0.6
    assert p['metrics']['humidifier_watt']['max']==20
    assert p['target_change_count']==1 and p['target_changes'][0]['vpd']==1.2
    assert p['targets_first']['vpd']==1.17 and p['targets_last']['vpd']==1.2
    assert p['humidifier']['observed_changes']==2 and [e['on'] for e in p['humidifier']['transitions']]==[True,False]


def test_unknown_and_gaps_never_become_off_or_inferred_transitions():
    start=END-timedelta(hours=1)
    rows=[(start,reading(**{'cur.shelly.humidifier.isOn':True})),
        (start+timedelta(seconds=10),reading(**{'cur.shelly.humidifier.fresh':False,'sensors.climate.fresh':False})),
        (start+timedelta(seconds=20),reading(**{'cur.shelly.humidifier.isOn':False})),
        (start+timedelta(seconds=240),reading(**{'cur.shelly.humidifier.isOn':True}))]
    out=build_analysis_export(2,rows,END,1)
    assert sum(p['humidifier']['observed_changes'] for p in out['points'])==0
    first=out['points'][0];assert first['humidifier']['unknown_samples']==1
    assert first['metrics']['vpd']['n']==2 and first['metrics']['humidifier_watt']['n']==2
    assert out['points'][1]['samples']==0
    assert any(gap['seconds']==220 for gap in out['gaps'])


def test_window_boundaries_and_nonfinite_values():
    start=END-timedelta(hours=1)
    rows=[(start-timedelta(seconds=1),reading()),(start,reading(**{'sensors.cur.vpdKpa':float('inf'),'settings.grow.targetVPD':float('nan'),'cur.shelly.humidifier.Watt':float('inf')})),(END,reading())]
    out=build_analysis_export(2,rows,END,1)
    assert out['sampleCount']==1
    assert out['points'][0]['metrics']['vpd']['avg'] is None
    json.dumps(out,allow_nan=False)


def test_event_detail_limits_keep_counts_and_last_targets():
    start=END-timedelta(hours=1)
    rows=[(start+timedelta(seconds=i),reading(**{'cur.shelly.humidifier.isOn':bool(i%2),'settings.grow.targetVPD':i/100})) for i in range(30)]
    out=build_analysis_export(2,rows,END,1);p=out['points'][0]
    assert p['humidifier']['observed_changes']==29 and len(p['humidifier']['transitions'])==8
    assert p['target_change_count']==29 and len(p['target_changes'])==4
    assert p['targets_last']['vpd']==0.29 and out['eventDetailsOmitted']==46


class ExportDatabase(Database):
    def __init__(self,rows=(),events=()):
        super().__init__(rows);self.events=list(events)
    def fetchall(self):
        return self.events if 'FROM irrigation_events' in self.statements[-1][0] else self.rows


def exporter(db):
    # Legacy telemetry-only test doubles do not have a journal.
    if not isinstance(db,ExportDatabase):
        original_fetchall=db.fetchall
        db.fetchall=lambda: [] if 'FROM irrigation_events' in db.statements[-1][0] else original_fetchall()

    node=next(n for n in ast.parse((Path(__file__).parents[1]/'api/app.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='export_analysis_json')
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return END
    ns={'datetime':Clock,'timezone':timezone,'timedelta':timedelta,'HTTPException':HTTPException,'Response':Response,'json':json,
        'get_conn':db.connection,'get_tent_by_id':lambda tid: {'id':tid, 'name':'Zelt 2', 'pot_strains':{'pot1':'Oreoz','pot2':'White Widow','pot3':''}} if tid==2 else None,
        '_normalise_pot_strains':lambda p: {k: (p or {}).get(k,'') for k in ('pot1','pot2','pot3')},
        'build_analysis_export':build_analysis_export,'read_irrigation_events':read_irrigation_events,'ANALYSIS_EXPORT_HOURS':HOURS,'POLL_INTERVAL_SECONDS':10}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'api/app.py','exec'),ns)
    return ns['export_analysis_json']


def test_attachment_and_bounded_read_query():
    db=Database([(END-timedelta(seconds=15),reading())]);before=copy.deepcopy(db.rows)
    response=exporter(db)(2,'24h');out=json.loads(response.body)
    assert response.headers['content-disposition']=='attachment; filename="growtent-2_2026-11-15_1200Z_24h.json"'
    assert response.headers['cache-control']=='no-store' and response.media_type=='application/json'
    assert out['hours']==24 and out['sampleCount']==1 and db.rows==before
    assert out['tentId']==2 and out['tent_name']=='Zelt 2'
    assert out['pot_strains']=={'pot1':'Oreoz','pot2':'White Widow','pot3':''}
    assert out['pot_strains_source']=='current_tent_configuration'
    assert all(sql.lstrip().startswith('SELECT') for sql,_ in db.statements)
    assert db.statements[0][1]==(2,END-timedelta(hours=24),END)
    with pytest.raises(HTTPException) as e:exporter(db)(2,'all')
    assert e.value.status_code==400
    with pytest.raises(HTTPException) as e:exporter(db)(99,'24h')
    assert e.value.status_code==404


def test_file_size_guard_widens_windows_without_discarding_aggregate_statistics():
    start=END-timedelta(hours=24)
    rows=[(start+timedelta(seconds=i*10),reading(1+(i%20)/100,**{
        'settings.grow.targetVPD':1+(i%11)/100,
        'cur.shelly.humidifier.isOn':bool(i%2)})) for i in range(8640)]
    response=exporter(Database(rows))(2,'24h');out=json.loads(response.body)
    assert len(response.body)<=1_000_000
    assert out['sampleCount']==8640 and out['count']<=720
    assert sum(p['samples'] for p in out['points'])==8640
    assert min(p['metrics']['vpd']['min'] for p in out['points'])==1
    assert max(p['metrics']['vpd']['max'] for p in out['points'])==1.19
    assert out['sizeAdapted']==(out['bucketSeconds']>120)
    assert out['eventDetailsOmitted']>0

import json
from datetime import datetime, timedelta, timezone
from services.analysis_export import build_analysis_export
from test_analysis_export import exporter, ExportDatabase, END

START=END-timedelta(hours=1)


def sample(name='Topftemperatur',temp=23,amount=500):
    return {'sensors.cur.extTempC':temp,'sensors.cur.ds18b20Name':name,
            'irrigation.amountTotal':amount,'irrigation.amount':20,'irrigation.timePerTask':10,
            'irrigation.betweenTasks':3,'irrigation.pump1.enabled':True,
            'irrigation.pump2.enabled':False,'irrigation.pump3.enabled':True}


def event(at,kind='started',received=None,run='private-run'):
    return ({'occurred_at':int(at.timestamp()) if at else None,'type':kind,'run_id':run,'reason':'private-secret'},
            received or at,'http://private-ip:8080','private-stream')


def test_temperature_names_are_historical_and_stats_do_not_mix():
    rows=[(START,sample(temp=20)),(START+timedelta(seconds=10),sample(temp=24)),
          (START+timedelta(seconds=20),sample('Stecklingsbox',26)),
          (START+timedelta(seconds=30),sample('Stecklingsbox',-127)),
          (START+timedelta(seconds=40),sample('',float('inf')))]
    out=build_analysis_export(2,rows,END,1)
    assert out['points'][0]['external_temperatures']==[
        {'sensor_name':'Topftemperatur','avg':22,'min':20,'max':24,'n':2},
        {'sensor_name':'Stecklingsbox','avg':26,'min':26,'max':26,'n':1},
        {'sensor_name':'DS18B20','avg':None,'min':None,'max':None,'n':0}]
    assert out['externalTemperatureUnit']=='°C'
    assert 'external_temperatures' not in out['points'][1]


def test_journal_event_time_not_receipt_time_and_no_invented_volume():
    at=START+timedelta(seconds=15);done=at+timedelta(seconds=100)
    rows=[(START,sample()),(done-timedelta(seconds=5),sample(amount=800))]
    events=[event(done,'completed',received=END+timedelta(hours=1)),event(at,received=END+timedelta(hours=1)),
            event(None,'aborted',received=START+timedelta(seconds=200)),event(END),event(START-timedelta(seconds=1),received=START)]
    out=build_analysis_export(2,rows,END,1,irrigation_rows=events)
    a,b,c=out['irrigation_events']
    assert [a['type'],b['type'],c['type']]==['started','completed','aborted']
    assert a['occurred_at']=='2026-11-15T11:00:15.000Z'
    assert a['occurred_at_local']=='2026-11-15T12:00:15+01:00'
    assert a['run_ref']==b['run_ref']==c['run_ref']
    assert a['configured_amount_ml']==500 and b['configured_amount_ml']==800
    assert a['observed_settings']['pump_enabled']==[True,False,True]
    assert a['measured_amount_ml'] is None and b['measured_amount_ml'] is None
    assert c['occurred_at'] is None and c['configured_amount_ml'] is None
    assert 'private-' not in json.dumps(out,allow_nan=False)


def test_no_backfill_from_future_or_stale_configuration():
    at=START+timedelta(seconds=100)
    rows=[(START,sample()),(at+timedelta(seconds=1),sample(amount=900))]
    out=build_analysis_export(2,rows,END,1,irrigation_rows=[event(at)])
    assert out['irrigation_events'][0]['configured_amount_ml'] is None
    assert out['context_last']['irrigation_settings']['configured_amount_ml']==900


def test_endpoint_filters_by_tent_and_original_time():
    at=START+timedelta(seconds=30)
    db=ExportDatabase([(START,sample())],[event(at)])
    out=json.loads(exporter(db)(2,'1h').body)
    assert out['irrigation_events'][0]['configured_amount_ml']==500
    sql,args=db.statements[1]
    assert 'tent_id=%s' in sql and 'occurred_at' in sql
    assert args==(2,START.timestamp(),END.timestamp(),START,END)
    assert all(s.lstrip().startswith('SELECT') for s,_ in db.statements)


def test_size_adaptation_keeps_irrigation_journal_and_named_stats():
    start=END-timedelta(hours=24)
    rows=[(start+timedelta(seconds=i*10),{
        **sample(temp=20+i%7),
        **{f'cur.shelly.{role}.Watt':10 for role in ('main','light','humidifier','heater','heatmat','fan','exhaust')}
    }) for i in range(8640)]
    at=start+timedelta(seconds=10)
    events=[event(at),event(at+timedelta(seconds=100),'completed')]
    response=exporter(ExportDatabase(rows,events))(2,'24h');out=json.loads(response.body)
    assert len(response.body)<=1_000_000 and out['sizeAdapted']
    assert len(out['irrigation_events'])==2
    stats=[entry for p in out['points'] for entry in p.get('external_temperatures',[])]
    assert sum(e['n'] for e in stats)==8640
    assert min(e['min'] for e in stats)==20 and max(e['max'] for e in stats)==26

"""Real transaction tests. CI provides an isolated PostgreSQL service."""
import os
import uuid
from contextlib import contextmanager
from datetime import date
import psycopg2
import pytest
from services import irrigation_store as db
from services.irrigation_store import IrrigationStore,create_tables

URL=os.getenv('IRRIGATION_TEST_DATABASE_URL')
pytestmark=pytest.mark.skipif(not URL,reason='Requires IRRIGATION_TEST_DATABASE_URL')

@pytest.fixture
def store(monkeypatch):
    schema='irrigation_'+uuid.uuid4().hex
    root=psycopg2.connect(URL);root.autocommit=True
    with root.cursor() as cur:cur.execute('CREATE SCHEMA '+schema)
    @contextmanager
    def connection():
        conn=psycopg2.connect(URL,options='-c search_path='+schema)
        try:
            with conn:yield conn
        finally:conn.close()
    monkeypatch.setattr(db,'get_conn',connection)
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE tents(id INTEGER PRIMARY KEY,irrigation_plan_json TEXT,irrigation_last_run_date DATE);
                INSERT INTO tents VALUES(1,'{"enabled":true,"every_n_days":7,"offset_after_light_on_min":10}','2026-11-10');''')
            create_tables(cur);create_tables(cur)
    yield IrrigationStore()
    with root.cursor() as cur:cur.execute('DROP SCHEMA '+schema+' CASCADE')
    root.close()

def read(sql):
    with db.get_conn() as conn:
        with conn.cursor() as cur:cur.execute(sql);return cur.fetchall()

def event(seq=1):
    return {'seq':seq,'type':'started','occurred_at':1794560400,'run_id':'a'*32}

def notice(e):return {'title':'Start','message':'Original event time','priority':0}

def test_snapshot_retains_original_legacy_plan_and_cache_is_esp_authoritative(store):
    old=store.snapshot(1,'http://esp:8080')
    assert old['legacy']['plan']['every_n_days']==7
    store.cache(1,{'enabled':False,'every_n_days':3,'offset_after_light_on_min':30,'last_run_date':'2026-11-12','revision':4})
    state=store.snapshot(1,'http://esp:8080')
    assert state['state']['every_n_days']==3 and state['legacy']['plan']['every_n_days']==7
    assert read('SELECT irrigation_last_run_date FROM tents')[0][0]==date(2026,11,12)
    assert store.claim_poll(1) is True and store.claim_poll(1) is False

def test_event_outbox_commit_deduplicates_and_retries_failed_push(store):
    for _ in range(2):assert store.ingest(1,'http://esp:8080','stream',[event()],notice)==1
    assert read('SELECT count(*) FROM irrigation_events')[0][0]==1
    assert read('SELECT count(*) FROM irrigation_notifications')[0][0]==1
    store.deliver(lambda **kw:False)
    assert read('SELECT attempts,sent_at FROM irrigation_notifications')==[(1,None)]
    with db.get_conn() as conn:
        with conn.cursor() as cur:cur.execute('UPDATE irrigation_notifications SET next_attempt_at=NOW()')
    sent=[];store.deliver(lambda **kw:sent.append(kw) or True);store.deliver(lambda **kw:sent.append(kw) or True)
    assert len(sent)==1
    assert read('SELECT sent_at IS NOT NULL FROM irrigation_notifications')[0][0]

def test_outbox_failure_rolls_back_event_so_no_ack_can_be_issued(store):
    def fail(e):raise RuntimeError('outbox failure')
    with pytest.raises(RuntimeError):store.ingest(1,'http://esp:8080','stream',[event()],fail)
    assert read('SELECT count(*) FROM irrigation_events')[0][0]==0
    assert read('SELECT count(*) FROM irrigation_notifications')[0][0]==0

def test_cross_worker_lock_and_persistent_manual_identity(store):
    with store.lock(1) as held:
        assert held
        with IrrigationStore().lock(1) as second:assert not second
    with IrrigationStore().lock(1) as second:assert second
    first='a'*32;other='b'*32
    assert store.command(1,'http://esp:8080',first,100)['expires']==100
    store.command_status(1,first,'uncertain')
    assert store.command(1,'http://esp:8080',other,110)['blocked_by']==first
    store.resolve_commands(1,'http://esp:8080',{'manual_commands':[{'command_id':first,'status':'aborted'}]},90)
    assert store.command(1,'http://esp:8080',first,500)['status']=='aborted'
    assert store.command(1,'http://esp:8080',first,500)['expires']==100
    assert store.command(1,'http://esp:8080',other,110)['status']=='prepared'
    store.resolve_commands(1,'http://esp:8080',{'manual_commands':[]},111)
    assert store.command(1,'http://esp:8080',other,500)['status']=='expired'

def test_provider_retry_gets_retrospective_label_at_delivery(store):
    import time
    store.warning(1,'delayed',{'title':'Event','message':'Original timestamp.','priority':0,'_occurred_at':int(time.time())-3600,'_delayed':False})
    sent=[];store.deliver(lambda **payload:sent.append(payload) or True)
    assert 'Nachträglich' in sent[0]['message']
    assert '_occurred_at' not in sent[0]

def test_event_error_is_separate_from_signed_plan_confirmation(store):
    store.snapshot(1,'http://esp:8080')
    state={'enabled':True,'every_n_days':2,'offset_after_light_on_min':60,'last_run_date':'2026-11-13','revision':4}
    store.cache(1,state)
    before=store.snapshot(1,'http://esp:8080')
    store.event_error(1,'event_sequence_gap')
    after=store.snapshot(1,'http://esp:8080')
    assert after['error'] is None and after['event_error']=='event_sequence_gap'
    assert after['checked_at']==before['checked_at']
    store.event_error(1)
    assert store.snapshot(1,'http://esp:8080')['event_error'] is None

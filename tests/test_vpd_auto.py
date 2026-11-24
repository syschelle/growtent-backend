"""VPD schedule is opt-in, tent-scoped and applies 0.90 kPa during drying."""
import json
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services import vpd_auto
# Local unit environments may not have the optional PostgreSQL/2FA packages.
# Never replace a real installed driver (needed by PostgreSQL CI tests).
try:
    import psycopg2
except ModuleNotFoundError as exc:
    if exc.name != 'psycopg2': raise
    pg = types.ModuleType('psycopg2')
    pg.Error = type('DatabaseError', (Exception,), {})
    pg.connect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('PostgreSQL unavailable locally'))
    sys.modules['psycopg2'] = pg
try:
    import pyotp
except ModuleNotFoundError as exc:
    if exc.name != 'pyotp': raise
    twofa = types.ModuleType('pyotp')
    twofa.TOTP = type('TOTP', (), {'interval': 30})
    twofa.random_base32 = lambda: 'DUMMY'
    sys.modules['pyotp'] = twofa

import fastapi.staticfiles
if not Path('/app/static').is_dir():
    class _MockStaticFiles:
        def __init__(self,*a,**k):pass
        async def __call__(self,*a,**k):pass
    fastapi.staticfiles.StaticFiles = _MockStaticFiles

from services import vpd_auto_store as store


def snapshot(phase=1, week=1, current=0.8):
    return {'settings.grow.currentPhase': phase,
            'settings.grow.currentPhaseWeek': week,
            'settings.grow.targetVPD': current}


def test_disabled_by_default_and_weekly_targets_are_in_reference_ranges():
    plan = vpd_auto.default_plan()
    assert plan['enabled'] is False
    assert vpd_auto.target_for(plan, 1, 1) is None
    plan['enabled'] = True
    assert vpd_auto.target_for(plan, 1, 1) == 0.60
    assert vpd_auto.target_for(plan, 1, 2) == 0.70
    assert vpd_auto.target_for(plan, 1, 5) == 1.10
    assert vpd_auto.target_for(plan, 1, 60) == 1.15
    assert vpd_auto.target_for(plan, 2, 1) == 1.00
    assert vpd_auto.target_for(plan, 2, 6) == 1.40
    assert vpd_auto.target_for(plan, 2, 60) == 1.30
    assert vpd_auto.target_for(plan, 3, 1) == 0.90


@pytest.mark.parametrize('bad', [
    {}, {'enabled': True, 'vegetative': [], 'flowering': [1.2]},
    {'enabled': 'true', 'vegetative': [0.6], 'flowering': [1.2]},
    {'enabled': False, 'vegetative': [float('nan')], 'flowering': [1.2]},
    {'enabled': True, 'vegetative': [True], 'flowering': [1.2]},
    {'enabled': True, 'vegetative': [0.49], 'flowering': [1.2]},
    {'enabled': True, 'vegetative': [0.6], 'flowering': [3.51]},
    {'enabled': False, 'vegetative': [0.6], 'flowering': [1.201]},
    {'enabled': False, 'vegetative': [0.6], 'flowering': [1.2], 'hmacSecret': 'x'},
    {'enabled': True, 'vegetative': [0.6] * 21, 'flowering': [1.2]},
    'not-json', [],
])
def test_plan_validation_refuses_untrusted_values(bad):
    with pytest.raises(ValueError): vpd_auto.normalize_plan(bad)


@pytest.mark.parametrize('phase,week', [(0, 1), (4, 1), (1, 0),
                                        (1, 261), (None, 2), (1, None),
                                        (1, '2'), (True, 1), (1, True),
                                        (float('nan'), 1), (1, float('inf'))])
def test_unknown_phase_or_invalid_growth_week_never_gets_a_target(phase, week):
    assert vpd_auto.phase_week(snapshot(phase, week)) is None


def test_phase_week_uses_live_esp_state_not_an_assumed_date():
    assert vpd_auto.phase_week(snapshot(2, 7)) == (2, 7)
    assert vpd_auto.phase_week(snapshot(1, 3)) == (1, 3)


def test_retry_is_delayed_30_minutes_for_same_phase_week_and_immediate_when_changed():
    now = datetime.now(timezone.utc)
    desired = (2, 6, 1.4)
    assert not vpd_auto.retry_ready(now-timedelta(minutes=12), desired, desired, now)
    assert vpd_auto.retry_ready(now-timedelta(minutes=31), desired, desired, now)
    assert vpd_auto.retry_ready(now-timedelta(minutes=1), (2, 5, 1.35), desired, now)
    assert vpd_auto.should_apply(desired, *desired) is False
    assert vpd_auto.should_apply((1, 6, 1.15), *desired) is True


class FakeDB:
    def __init__(self, plans=None, *, writes_ready=True):
        self.plans = plans or {1:vpd_auto.default_plan(), 2:vpd_auto.default_plan()}
        self.writes_ready = writes_ready
        self.calls=[]
        self.row=None
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self
    def execute(self, sql, args):
        self.calls.append((sql, args))
        tid=args[0] if args else None
        if sql.strip().startswith('SELECT vpd_auto_plan_json'):
            plan=self.plans.get(tid)
            if 'backend_write_enabled' in sql:
                self.row=(json.dumps(plan),self.writes_ready,'http://esp:8080','hmac') if plan else None
            else:
                self.row=(json.dumps(plan),) if plan else None
        elif 'FROM tent_vpd_auto_state' in sql: self.row=None
        elif sql.strip().startswith('UPDATE tents SET vpd_auto_plan_json'):
            self.plans[args[1]]=json.loads(args[0]);self.row=None
        elif sql.strip().startswith('DELETE FROM tent_vpd_auto_state'): self.row=None
        else: raise AssertionError(sql)
    def fetchone(self):return self.row


def test_tent_plan_isolation_and_disabled_plans(monkeypatch):
    one = vpd_auto.default_plan();one.update(enabled=True,vegetative=[0.6,0.8])
    two = vpd_auto.default_plan();two.update(enabled=False,flowering=[1.3,1.4])
    db=FakeDB({1:one,2:two})
    monkeypatch.setattr(store, 'get_conn', lambda: db)
    # The status query also references the own tent id, never last visited tent.
    assert store.get_plan(1)['plan']==one
    assert store.get_plan(2)['plan']==two
    assert store.get_plan(1)['plan']==one
    assert all('WHERE tent_id=%s' in sql and args in ((1,),(2,))
               for sql,args in db.calls if 'FROM tent_vpd_auto_state' in sql)


def test_enabling_requires_hmac_and_changes_only_selected_tent(monkeypatch):
    db=FakeDB(writes_ready=False)
    monkeypatch.setattr(store,'get_conn',lambda:db)
    new=vpd_auto.default_plan();new['enabled']=True
    with pytest.raises(HTTPException) as exc: store.save_plan(1,new)
    assert exc.value.status_code==409 and db.plans[1]['enabled'] is False
    db.writes_ready=True
    result=store.save_plan(1,new)
    assert result['plan']['enabled'] is True
    assert db.plans[2]['enabled'] is False
    assert any('UPDATE tents SET vpd_auto_plan_json' in sql and args[1]==1 for sql,args in db.calls)


def test_reconcile_invalid_or_disabled_never_write(monkeypatch):
    db=FakeDB()
    monkeypatch.setattr(store,'get_conn',lambda:db)
    claims=[]
    monkeypatch.setattr(store,'_claim',lambda *a: claims.append(a) or True)
    for state in (snapshot(3,1),snapshot(1,None),snapshot(2,0)):
        store.reconcile(1,state)
    store.reconcile(1,snapshot())  # disabled plan
    assert not claims


def test_reconcile_writes_only_target_vpd_and_never_changes_phase_or_temperature(monkeypatch):
    enabled=vpd_auto.default_plan();enabled['enabled']=True
    db=FakeDB({2:enabled})
    monkeypatch.setattr(store,'get_conn',lambda:db)
    monkeypatch.setattr(store,'_claim',lambda *a: True)
    finished=[]
    monkeypatch.setattr(store,'_finish',lambda *a: finished.append(a))
    import services.tent_service as tent_service
    calls=[]
    monkeypatch.setattr(tent_service.TentService,'update_grow_profile',lambda self,tid,payload,username: calls.append((tid,payload.model_dump(exclude_unset=True),username)))
    store.reconcile(2,snapshot(2,6,.85))
    assert calls == [(2,{'targetVPD':1.4},'vpd-automation')]
    assert finished[-1][-2:] == ('applied',True)
    # If already at target, never send another HTTP write.
    store.reconcile(2,snapshot(2,6,1.4))
    assert len(calls)==1
    assert finished[-1][-2:]==('already_at_target',True)


def test_reconcile_failure_is_nonfatal_and_pending_retry(monkeypatch):
    enabled=vpd_auto.default_plan(); enabled['enabled']=True
    monkeypatch.setattr(store,'get_conn',lambda:FakeDB({1:enabled}))
    monkeypatch.setattr(store,'_claim',lambda *a:True)
    seen=[]
    monkeypatch.setattr(store,'_finish',lambda *a:seen.append(a))
    import services.tent_service as tent_service
    def raise_error(*args):raise RuntimeError('simulated unreachable ESP')
    monkeypatch.setattr(tent_service.TentService,'update_grow_profile',raise_error)
    store.reconcile(1,snapshot())
    assert seen[-1][-2:]==('failed_retry_later',False)


def test_modular_router_allows_only_administrators(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app as legacy
    from routes.tents import router

    app = FastAPI()
    app.include_router(router)
    auth = {'role':'guest'}
    monkeypatch.setattr(legacy, 'get_session', lambda token: auth if token else None)
    monkeypatch.setattr(store, 'get_plan', lambda tid: {'tentId':tid, 'plan':vpd_auto.default_plan()})
    writes=[]
    monkeypatch.setattr(store, 'save_plan', lambda tid,body: writes.append((tid,body)) or {'tentId':tid,'plan':body})
    client = TestClient(app)
    client.cookies.set('caop_session','test')
    assert client.get('/tents/1/vpd-auto').status_code==403
    assert client.put('/tents/1/vpd-auto',json=vpd_auto.default_plan()).status_code==403
    assert not writes
    auth['role']='admin'
    response=client.get('/tents/2/vpd-auto')
    assert response.status_code==200 and response.json()['tentId']==2
    plan=vpd_auto.default_plan()
    plan['enabled']=True
    response=client.put('/tents/2/vpd-auto',json=plan)
    assert response.status_code==200 and writes==[(2,plan)]

@pytest.mark.parametrize('plan,status,expected_enabled,expected_failed', [
    (vpd_auto.default_plan(), None, False, False),
    ({**vpd_auto.default_plan(), 'enabled': True}, None, True, False),
    ({**vpd_auto.default_plan(), 'enabled': True}, 'applied', True, False),
    ({**vpd_auto.default_plan(), 'enabled': True}, 'already_at_target', True, False),
    ({**vpd_auto.default_plan(), 'enabled': True}, 'pending', True, False),
    ({**vpd_auto.default_plan(), 'enabled': True}, 'failed_retry_later', True, True),
    ({**vpd_auto.default_plan(), 'enabled': True}, 'error_timeout', True, True),
    (vpd_auto.default_plan(), 'failed_retry_later', False, False),
])
def test_vpd_auto_badge_status_is_minimal_and_tent_scoped(monkeypatch, plan, status, expected_enabled, expected_failed):
    seen = []
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, args): seen.append((sql, args))
        def fetchone(self): return (json.dumps(plan), status)
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def cursor(self): return Cursor()
    monkeypatch.setattr(store, 'get_conn', lambda: Connection())
    result = store.get_badge_status(7)
    assert result == {'tentId': 7, 'enabled': expected_enabled, 'lastSyncFailed': expected_failed}
    assert len(seen) == 1
    assert seen[0][1] == (7,)
    assert 's.tent_id = t.id' in seen[0][0]
    assert 'WHERE t.id = %s' in seen[0][0]
    assert 'vegetative' not in result and 'flowering' not in result


def test_vpd_auto_badge_missing_tent_is_not_replaced_by_other_tent(monkeypatch):
    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, *args): pass
        def fetchone(self): return None
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def cursor(self): return Cursor()
    monkeypatch.setattr(store, 'get_conn', lambda: Connection())
    with pytest.raises(HTTPException) as exc:
        store.get_badge_status(123)
    assert exc.value.status_code == 404

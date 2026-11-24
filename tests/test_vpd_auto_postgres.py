"""Optional PostgreSQL integration for durable, per-tent and multi-worker VPD claims.

Uses an isolated schema, never the production DB. GitHub CI supplies
IRRIGATION_TEST_DATABASE_URL; locally the tests are intentionally skipped.
"""
import os
import uuid

import pytest

URL = os.getenv('IRRIGATION_TEST_DATABASE_URL')
psycopg2 = pytest.importorskip('psycopg2')

from services import vpd_auto_store as store
from services.vpd_auto import default_plan


@pytest.fixture
def vpd_db(monkeypatch):
    if not URL:
        pytest.skip('No isolated PostgreSQL test database configured')
    schema = 'vpd_auto_' + uuid.uuid4().hex
    root = psycopg2.connect(URL)
    root.autocommit = True
    with root.cursor() as cur:
        cur.execute(f'CREATE SCHEMA "{schema}"')
    root.close()

    def connect():
        return psycopg2.connect(URL, options=f'-c search_path={schema}')

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute('''CREATE TABLE tents(
                id INTEGER PRIMARY KEY,
                vpd_auto_plan_json TEXT NOT NULL,
                backend_write_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                backend_controller_url TEXT DEFAULT 'http://esp:8080',
                backend_hmac_secret TEXT DEFAULT 'configured'
            )''')
            cur.execute('''CREATE TABLE tent_vpd_auto_state (
                tent_id INTEGER PRIMARY KEY REFERENCES tents(id) ON DELETE CASCADE,
                applied_phase INTEGER, applied_week INTEGER, applied_target DOUBLE PRECISION,
                applied_at TIMESTAMPTZ, attempt_phase INTEGER, attempt_week INTEGER,
                attempt_target DOUBLE PRECISION, attempt_at TIMESTAMPTZ, last_status TEXT
            )''')
            import json
            default = default_plan()
            for tid in (1, 2):
                cur.execute('INSERT INTO tents(id,vpd_auto_plan_json) VALUES (%s,%s)',
                            (tid, json.dumps(default)))
    monkeypatch.setattr(store, 'get_conn', connect)
    yield connect

    root = psycopg2.connect(URL)
    root.autocommit = True
    with root.cursor() as cur:
        cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
    root.close()


def test_real_postgres_weekly_claims_are_one_time_and_tent_scoped(vpd_db):
    config = default_plan(); config['enabled'] = True
    assert store.save_plan(1, config)['plan']['enabled']
    assert store.save_plan(2, config)['plan']['enabled']
    assert store._claim(1, 1, 1, .6)
    assert not store._claim(1, 1, 1, .6)  # second process must not write twice
    assert store._claim(2, 1, 1, .6)  # other tent is independent
    store._finish(1, 1, 1, .6, 'applied', True)
    assert not store._claim(1, 1, 1, .6)  # durable after new connections
    assert store._claim(1, 1, 2, .7)  # immediate on week transition
    assert store.get_plan(1)['lastApplied']['week'] == 1
    assert store.get_plan(2)['lastApplied'] is None
    store._finish(1, 1, 2, .7, 'applied', True)
    assert store.get_plan(1)['lastApplied']['targetVPD'] == .7
    # Turning off affects only that tent and prevents further claims.
    config['enabled'] = False
    store.save_plan(1, config)
    assert not store._claim(1, 1, 3, .9)
    assert store.get_plan(2)['plan']['enabled']


def test_real_postgres_reconfiguration_requires_fresh_weekly_application(vpd_db):
    config = default_plan(); config['enabled'] = True
    store.save_plan(1, config)
    assert store._claim(1, 2, 6, 1.4)
    store._finish(1, 2, 6, 1.4, 'applied', True)
    assert not store._claim(1, 2, 6, 1.4)
    config['flowering'][5] = 1.45
    store.save_plan(1, config)
    assert store.get_plan(1)['lastApplied'] is None
    assert store._claim(1, 2, 6, 1.45)


def test_real_postgres_extended_veg_does_not_claim_extra_week_or_cross_phase(vpd_db, monkeypatch):
    """After last Vegi plan week, an ESP week advance must not resend HMAC writes."""
    from services.vpd_auto import tracking_week, target_for
    from services.tent_service import TentService
    from types import SimpleNamespace

    plan = default_plan(); plan['enabled'] = True
    store.save_plan(1, plan)
    payload = lambda phase, week, target: {
        'settings.grow.currentPhase': phase,
        'settings.grow.currentPhaseWeek': week,
        'settings.grow.targetVPD': target,
    }
    writes = []
    monkeypatch.setattr(TentService, 'update_grow_profile',
                        lambda self, tid, patch, username:
                        writes.append((tid, patch.model_dump(exclude_unset=True), username)))
    store.reconcile(1, payload(1, 6, .7))
    assert store.get_plan(1)['lastApplied']['week'] == 6
    store.reconcile(1, payload(1, 7, .8))
    store.reconcile(1, payload(1, 8, .8))
    assert store.get_plan(1)['lastApplied']['phase'] == 1
    assert store.get_plan(1)['lastApplied']['week'] == 6
    assert writes == [(1, {'targetVPD': 1.15}, 'vpd-automation')]
    store.reconcile(1, payload(2, 1, 1.15))
    assert writes[-1] == (1, {'targetVPD': 1.0}, 'vpd-automation')
    assert store.get_plan(1)['lastApplied']['phase'] == 2


def test_real_postgres_extended_flowering_holds_last_target_until_actual_drying(vpd_db, monkeypatch):
    """A long blooming phase cannot implicitly switch to the drying target."""
    from services.tent_service import TentService

    plan = default_plan()
    plan['enabled'] = True
    plan['flowering'] = [1.10, 1.20, 1.30]
    store.save_plan(1, plan)
    writes = []
    monkeypatch.setattr(
        TentService, 'update_grow_profile',
        lambda self, tid, patch, username:
        writes.append((tid, patch.model_dump(exclude_unset=True), username)),
    )

    def state(phase, week, target):
        return {'settings.grow.currentPhase': phase,
                'settings.grow.currentPhaseWeek': week,
                'settings.grow.targetVPD': target}

    store.reconcile(1, state(2, 3, .90))
    assert store.get_plan(1)['lastApplied']['week'] == 3
    for extended_week in (4, 5, 12):
        store.reconcile(1, state(2, extended_week, .95))
        assert store.get_plan(1)['lastApplied']['phase'] == 2
        assert store.get_plan(1)['lastApplied']['week'] == 3

    assert writes == [(1, {'targetVPD': 1.30}, 'vpd-automation')]

    store.reconcile(1, state(3, None, 1.30))
    assert writes[-1] == (1, {'targetVPD': .90}, 'vpd-automation')
    assert store.get_plan(1)['lastApplied']['phase'] == 3

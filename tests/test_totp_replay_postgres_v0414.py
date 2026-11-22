"""Real PostgreSQL test: TOTP replay prevention must persist across connections.

CI provides IRRIGATION_TEST_DATABASE_URL; no production database is accessed.
"""
import os
import uuid
import pytest

import test_security_hardening  # import-only stubs for lightweight environments
import app

DB_URL = os.getenv('IRRIGATION_TEST_DATABASE_URL')


@pytest.mark.skipif(not DB_URL, reason='No isolated PostgreSQL CI database configured')
def test_postgres_totp_replay_guard_is_atomic_and_survives_new_connection():
    import psycopg2
    schema = 'totp_guard_' + uuid.uuid4().hex
    root = psycopg2.connect(DB_URL)
    root.autocommit = True
    try:
        with root.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{schema}"')
        with psycopg2.connect(DB_URL, options=f'-c search_path={schema}') as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE app_totp_replay (
                        account_key TEXT PRIMARY KEY,
                        secret_fingerprint TEXT NOT NULL,
                        last_step BIGINT NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                ''')
                assert app._record_totp_step(cur, account_key='admin:1', secret='secret1', step=42)
                assert not app._record_totp_step(cur, account_key='admin:1', secret='secret1', step=42)
        with psycopg2.connect(DB_URL, options=f'-c search_path={schema}') as conn:
            with conn.cursor() as cur:
                assert not app._record_totp_step(cur, account_key='admin:1', secret='secret1', step=41)
                assert not app._record_totp_step(cur, account_key='admin:1', secret='secret1', step=42)
                assert app._record_totp_step(cur, account_key='admin:1', secret='secret1', step=43)
                assert app._record_totp_step(cur, account_key='admin:2', secret='secret1', step=42)
                assert app._record_totp_step(cur, account_key='admin:1', secret='secret2', step=42)
    finally:
        with root.cursor() as cur:
            cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        root.close()

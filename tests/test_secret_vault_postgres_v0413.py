"""Migration smoke test in a disposable PostgreSQL schema, only in CI with test DB."""
import os
import uuid

import pytest
from cryptography.fernet import Fernet
from services import secret_vault as vault

URL = os.getenv('IRRIGATION_TEST_DATABASE_URL')


@pytest.mark.skipif(not URL, reason='requires isolated IRRIGATION_TEST_DATABASE_URL')
def test_encryption_migration_real_postgresql(monkeypatch):
    import psycopg2
    monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY', Fernet.generate_key().decode())
    schema = 'vault_' + uuid.uuid4().hex
    root=psycopg2.connect(URL)
    root.autocommit=True
    try:
        with root.cursor() as cur:
            cur.execute(f'CREATE SCHEMA "{schema}"')
        with psycopg2.connect(URL) as conn:
            with conn.cursor() as cur:
                cur.execute(f'SET search_path TO "{schema}"')
                cur.execute('CREATE TABLE app_auth_config(id INTEGER PRIMARY KEY, totp_secret TEXT, pushover_app_token TEXT, pushover_user_key TEXT, gromate_api_password TEXT)')
                cur.execute('CREATE TABLE app_admin_users(id INTEGER PRIMARY KEY, totp_secret TEXT)')
                cur.execute('CREATE TABLE tents(id INTEGER PRIMARY KEY, rtsp_url TEXT, shelly_main_password TEXT, backend_hmac_secret TEXT)')
                cur.execute('INSERT INTO app_auth_config VALUES(1,%s,%s,%s,%s)',('AAAA','BBB','CCC','DDD'))
                cur.execute('INSERT INTO app_admin_users VALUES(2,%s)',('SECRET2FA',))
                cur.execute('INSERT INTO tents VALUES(3,%s,%s,%s)',('rtsp://admin:pw@192.168.178.1/live','SHELLY','f'*64))
                assert vault.migrate_legacy_secrets(cur) == 8
                assert vault.migrate_legacy_secrets(cur) == 0
                cur.execute('SELECT rtsp_url,shelly_main_password,backend_hmac_secret FROM tents WHERE id=3')
                rtsp,shelly,hmac=cur.fetchone()
                assert all(value.startswith(vault.PREFIX) for value in (rtsp,shelly,hmac))
                assert vault.open_secret(rtsp)=='rtsp://admin:pw@192.168.178.1/live'
                assert vault.open_secret(hmac)=='f'*64
        monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY', Fernet.generate_key().decode())
        with pytest.raises(RuntimeError,match='decrypt'):
            with psycopg2.connect(URL) as conn:
                with conn.cursor() as cur:
                    cur.execute(f'SET search_path TO "{schema}"')
                    vault.migrate_legacy_secrets(cur)
    finally:
        try:
            with root.cursor() as cur:
                cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:root.close()

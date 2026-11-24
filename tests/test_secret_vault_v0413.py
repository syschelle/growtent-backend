"""v0.413 regression checks: no plaintext backups, safe migration, RTSP continuity."""
import json
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from services import secret_vault as vault


@pytest.fixture
def key(monkeypatch):
    value = Fernet.generate_key().decode()
    monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY', value)
    return value


def test_fails_closed_on_missing_key_and_invalid_key(monkeypatch):
    monkeypatch.delenv('GT_DATA_ENCRYPTION_KEY', raising=False)
    with pytest.raises(RuntimeError, match='required'):
        vault.require_key()
    with pytest.raises(RuntimeError, match='required'):
        vault.encrypt_backup({'secret': 'do not print'})
    monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY', 'not-a-valid-key')
    with pytest.raises(RuntimeError, match='Invalid'):
        vault.require_key()


def test_encryption_of_rtsp_hmac_shelly_totp_and_pushover(key, monkeypatch):
    for clear in ('rtsp://camera:secretpass@192.168.178.72:554/live', 'f' * 64,
                  'shelly-password', 'JBSWY3DPEHPK3PXP', 'pushover-token'):
        sealed = vault.seal_secret(clear)
        assert sealed.startswith(vault.PREFIX)
        assert clear not in sealed
        assert vault.open_secret(sealed) == clear
        # Re-encrypting is idempotent; no double encryption.
        assert vault.seal_secret(sealed) == sealed
        monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY', Fernet.generate_key().decode())
        with pytest.raises(RuntimeError, match='decrypt'):
            vault.open_secret(sealed)
        monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY', key)


def test_backup_is_encrypted_whole_and_restorable_using_same_key(key, monkeypatch):
    raw = {'kind':'canopyops-config-backup', 'schema_version':14,
           'data': {'admins': [{'totp_secret':'TOP_SECRET_2FA'}],
                    'tents':[{'backend_hmac_secret':'HMAC_TOP_SECRET',
                              'shelly_main_password':'SHELLY_TOP_SECRET',
                              'rtsp_url':'rtsp://user:password@192.168.178.88/stream'}],
                    'auth': {'pushover_app_token':'PUSH_TOP_SECRET',
                             'gromate_api_password':'GROMATE_TOP_SECRET'}}}
    envelope = vault.encrypt_backup(raw)
    serialized = json.dumps(envelope)
    for text in ('TOP_SECRET_2FA', 'HMAC_TOP_SECRET', 'SHELLY_TOP_SECRET',
                 'PUSH_TOP_SECRET', 'GROMATE_TOP_SECRET', 'rtsp://'):
        assert text not in serialized
    assert envelope['kind'] == vault.BACKUP_KIND
    assert vault.decrypt_backup(envelope) == raw
    monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY', Fernet.generate_key().decode())
    with pytest.raises(ValueError, match='wrong key'):
        vault.decrypt_backup(envelope)
    monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY', key)
    broken = dict(envelope, ciphertext=envelope['ciphertext'][:-12]+'tampered')
    with pytest.raises(ValueError, match='Backup decryption failed'):
        vault.decrypt_backup(broken)


def test_legacy_data_migration_is_idempotent_and_detects_wrong_key(key, monkeypatch):
    # Database cursor simulation for the exact 3 supported migration tables.
    rows = {
        'app_auth_config': [[1, 'BASE32-SEED', 'PUSH-TOKEN', 'PUSH-USER', 'GROMATE-PASS']],
        'app_admin_users': [[9, 'ADMIN-TOTP']],
        'tents': [[3, 'rtsp://admin:secret@192.168.178.80/live', 'SHELLY-PASS', '0'*64]],
    }
    class Cursor:
        def __init__(self): self.table=None
        def execute(self, sql, params=()):
            if sql.startswith('SELECT '):
                self.table=sql.split('FROM ')[1].split(' ')[0]
                return
            assert sql.startswith('UPDATE ')
            table=sql.split(' ')[1]
            assert table==self.table
            record=next(x for x in rows[table] if x[0]==params[-1])
            assignments=sql.split(' SET ')[1].split(' WHERE ')[0].split(', ')
            column_names = { 'app_auth_config':('totp_secret','pushover_app_token','pushover_user_key','gromate_api_password'),
                             'app_admin_users':('totp_secret',), 'tents':('rtsp_url','shelly_main_password','backend_hmac_secret')}[table]
            for assignment,value in zip(assignments, params[:-1]):
                name=assignment.split('=')[0]
                record[1+column_names.index(name)] = value
        def fetchall(self): return [tuple(row) for row in rows[self.table]]
    cur=Cursor()
    assert vault.migrate_legacy_secrets(cur)==8
    assert vault.migrate_legacy_secrets(cur)==0
    assert vault.open_secret(rows['tents'][0][1])=='rtsp://admin:secret@192.168.178.80/live'
    monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY', Fernet.generate_key().decode())
    with pytest.raises(RuntimeError, match='decrypt'):
        vault.migrate_legacy_secrets(cur)


def test_legacy_backup_import_does_not_require_encryption_decryption(key):
    # The legacy JSON import path is deliberately retained (see app.import_config_backup).
    from pathlib import Path
    source=(Path(__file__).parents[1]/'api'/'app.py').read_text()
    assert 'if payload.get("kind") == BACKUP_KIND:' in source
    assert 'payload = decrypt_backup(payload)' in source
    assert 'seal_secret(str(auth.get("totp_secret"))' in source


def test_modular_camera_still_decodes_encrypted_rtsp_url(key, monkeypatch):
    """Regression for the v0.411 camera 500: test the actual production router."""
    import time
    from io import BytesIO
    from PIL import Image
    from fastapi.testclient import TestClient
    import test_security_hardening  # Import-safe stubs for local lightweight runs.
    import app as legacy
    import main

    jpeg = BytesIO()
    Image.new('RGB', (320, 180), (70, 90, 110)).save(jpeg, format='JPEG')
    raw = jpeg.getvalue()
    camera='rtsp://admin:strongpass@192.168.178.77:554/live'
    encrypted=vault.seal_secret(camera)

    class DB:
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def cursor(self): return self
        def execute(self,query,values):
            assert 'SELECT rtsp_url FROM tents WHERE id=%s' in query
            assert values == (3,)
        def fetchone(self): return (encrypted,)

    requested=[]
    class FakeHTTP:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def get(self,url):
            requested.append(url)
            return SimpleNamespace(status_code=200, headers={'content-type':'image/jpeg'},content=raw)

    monkeypatch.setattr(legacy,'get_conn',DB)
    monkeypatch.setattr(legacy.httpx,'Client',FakeHTTP)
    monkeypatch.setattr(legacy,'load_auth_config', lambda:{'enabled':True})
    monkeypatch.setattr(legacy,'is_initial_install_available', lambda:False)
    legacy.SESSIONS['encrypted-camera-admin'] = {'authenticated':True,'role':'admin',
        'username':'admin','expires_at':time.time()+3600}
    try:
        # No lifespan startup: endpoint execution is tested against the real router.
        client=TestClient(main.app, cookies={'caop_session':'encrypted-camera-admin'})
        result=client.get('/tents/3/preview?w=1280&h=720&q=80')
        assert result.status_code == 200, result.text
        assert result.content == raw
        assert any('rtsp%3A' in url or 'rtsp%3a' in url for url in requested)
        assert not any(vault.PREFIX in url for url in requested)
    finally:
        legacy.SESSIONS.pop('encrypted-camera-admin',None)


def test_hmac_secret_is_decrypted_on_read_for_controller(key,monkeypatch):
    from db import crud
    secret='c'*64
    sealed=vault.seal_secret(secret)
    class DB:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def cursor(self):return self
        def execute(self,*args):pass
        def fetchone(self):return (2,'Tent 2','http://192.168.178.50/api/state',True,
                                   'http://192.168.178.50',sealed)
    monkeypatch.setattr(crud,'get_conn',DB)
    result=crud.get_tent_write_config_raw(2)
    assert result['_backend_hmac_secret']==secret
    assert vault.PREFIX not in result['_backend_hmac_secret']


def test_startup_requires_encryption_key(monkeypatch):
    import app as legacy
    monkeypatch.delenv('GT_DATA_ENCRYPTION_KEY', raising=False)
    monkeypatch.setattr(legacy,'init_db',lambda: pytest.fail('DB must not start without key'))
    with pytest.raises(RuntimeError,match='required'):
        legacy.startup_event()


def test_production_backup_export_is_ciphertext_not_cleartext(key, monkeypatch):
    import app as legacy

    raw_camera = 'rtsp://operator:cam-password@192.168.178.78:554/live'
    raw_hmac = 'd'*64
    row_tents = (3,'Tent Three','http://192.168.178.78/api/state',
                 vault.seal_secret(raw_camera),'admin',vault.seal_secret('shelly-secret'),
                 '{}', None, '{}', '[]', True, 'http://192.168.178.78',
                 vault.seal_secret(raw_hmac), False, 20.0, None, '{}', json.dumps({'enabled': False, 'vegetative': [0.6], 'flowering': [1.0]}))
    row_auth = (True,'sysadmin','$argon2id$hash',True,vault.seal_secret('JBSWY3DPEHPK3PXP'),
                '[]','device',vault.seal_secret('pushover-token'),vault.seal_secret('pushover-user'),
                vault.seal_secret('gromate-pass'),True,False,None,True,None)
    row_admin = (1,'sysadmin','$argon2id$hash',True,True,
                 vault.seal_secret('JBSWY3DPEHPK3PXP'),'[]',None,None)

    class DB:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def cursor(self):return self
        def execute(self,sql):
            if 'FROM tents' in sql: self.rows=[row_tents]
            elif 'FROM app_auth_config' in sql:self.rows=[row_auth]
            elif 'FROM app_admin_users' in sql:self.rows=[row_admin]
            elif 'FROM temperature_alert_config' in sql:self.rows=[(False,30,'C')]
            elif 'FROM flood_alert_config' in sql:self.rows=[(False,)]
            else:raise AssertionError(sql)
        def fetchall(self):return self.rows
        def fetchone(self):return self.rows[0]

    monkeypatch.setattr(legacy, 'get_conn', DB)
    monkeypatch.setattr(legacy, '_read_strains_db', lambda: [])
    response = legacy.export_config_backup()
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert '.encrypted.json' in response.headers['content-disposition']
    for leaked in ('cam-password', 'shelly-secret', 'pushover-token', 'pushover-user',
                   'gromate-pass', 'JBSWY3DPEHPK3PXP', raw_hmac):
        assert leaked.encode() not in response.body
    document=vault.decrypt_backup(json.loads(response.body))
    assert document['data']['tents'][0]['rtsp_url'] == raw_camera
    assert document['data']['tents'][0]['backend_hmac_secret'] == raw_hmac
    assert document['data']['auth']['totp_secret'] == 'JBSWY3DPEHPK3PXP'


def test_import_rejects_wrong_encrypted_backup_before_touching_database(key, monkeypatch):
    from fastapi import HTTPException
    import app as legacy
    envelope=vault.encrypt_backup({'kind':'canopyops-config-backup','data':{'tents':[]}})
    monkeypatch.setattr(legacy,'get_conn',lambda: pytest.fail('Database must not be touched'))
    monkeypatch.setenv('GT_DATA_ENCRYPTION_KEY',Fernet.generate_key().decode())
    with pytest.raises(HTTPException) as exc:
        legacy.import_config_backup(envelope)
    assert exc.value.status_code==400
    assert 'decryption failed' in exc.value.detail.lower()

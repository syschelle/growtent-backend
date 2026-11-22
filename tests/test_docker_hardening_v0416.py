"""v0.416: minimal Docker mount surface and optional source download safety."""

from pathlib import Path
import time
import zipfile

import pytest
import yaml
from fastapi import HTTPException

# Reuse the existing offline-only test import shim (never replaces a real DB
# driver) for environments that lack optional integration dependencies.
from test_security_hardening import app, _request

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('compose', ['docker-compose.yml', 'docker-compose.images.yml'])
def test_api_mounts_only_dedicated_data_by_default(compose):
    contents = (ROOT / compose).read_text(encoding='utf-8')
    services = yaml.safe_load(contents)['services']
    api = services['api']
    assert api['volumes'] == ['./data:/data']
    assert './:/project:ro' not in contents
    assert api['read_only'] is True
    assert api['cap_drop'] == ['ALL']
    assert 'no-new-privileges:true' in api['security_opt']
    assert '/tmp:rw,nosuid,nodev,size=128m' in api['tmpfs']
    assert api['pids_limit'] == 256
    assert api['user'] == '${GT_API_RUN_AS:-0:0}'
    assert api['environment']['GT_DATA_ENCRYPTION_KEY'].startswith('${GT_DATA_ENCRYPTION_KEY:?')
    assert api['environment']['PROJECT_DOWNLOAD_ENABLED'] == '${PROJECT_DOWNLOAD_ENABLED:-false}'
    assert api['environment']['PROJECT_ROOT'] == '/project'
    assert api['environment']['STRAINS_CSV_PATH'] == '/data/strains.csv'
    assert api['environment']['GO2RTC_BASE_URL'] == 'http://go2rtc:1984'
    assert '${GT_API_BIND_ADDRESS:-127.0.0.1}:8088:8080' in api['ports']
    # Other persistent services must not be migrated by an API-only hardening patch.
    assert 'db_data:/var/lib/postgresql/data' in services['db']['volumes']


def test_nonroot_image_can_read_bundled_code_without_shipping_secrets():
    dockerfile = (ROOT / 'api/Dockerfile').read_text(encoding='utf-8')
    dockerignore = (ROOT / 'api/.dockerignore').read_text(encoding='utf-8')
    assert 'RUN chmod -R a+rX /app' in dockerfile
    assert 'CMD ["uvicorn", "main:app"' in dockerfile
    for secret in ('.env', '.env.*', '*.key', '*.pem', '*.p12', '*.pfx'):
        assert secret in dockerignore.splitlines()
    assert (ROOT / 'api/CHANGELOG.md').is_file()
    assert '"/app/CHANGELOG.md"' in (ROOT / 'api/app.py').read_text(encoding='utf-8')


def _admin_cookie(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': True})
    token = 'docker-hardening-admin'
    app.SESSIONS[token] = {
        'authenticated': True, 'role': 'admin', 'admin_id': 1,
        'username': 'admin', 'expires_at': time.time() + 120
    }
    return token, f'caop_session={token}'


def test_project_download_requires_configured_source(monkeypatch, tmp_path):
    token, cookie = _admin_cookie(monkeypatch)
    try:
        monkeypatch.setattr(app, 'PROJECT_DOWNLOAD_ENABLED', True)
        monkeypatch.setattr(app, 'PROJECT_ROOT', str(tmp_path / 'unmounted'))
        with pytest.raises(HTTPException) as exc:
            app.download_project_zip(_request('/download/project.zip', cookie=cookie))
        assert exc.value.status_code == 503
        assert 'not mounted' in exc.value.detail
    finally:
        app.SESSIONS.pop(token, None)


def test_project_zip_excludes_symlinks_and_case_variant_secrets(monkeypatch, tmp_path):
    token, cookie = _admin_cookie(monkeypatch)
    try:
        monkeypatch.setattr(app, 'PROJECT_DOWNLOAD_ENABLED', True)
        monkeypatch.setattr(app, 'PROJECT_ROOT', str(tmp_path))
        (tmp_path / 'README.md').write_text('public project', encoding='utf-8')
        for filename in ['.env', '.ENV', '.ENV.Production', 'SERVER.KEY', 'SECRET.PEM', 'secrets.json']:
            (tmp_path / filename).write_text('private', encoding='utf-8')
        outside = tmp_path.parent / (tmp_path.name + '-external-secret')
        outside.write_text('TOP SECRET', encoding='utf-8')
        (tmp_path / 'linked-file.txt').symlink_to(outside)
        (tmp_path / 'linked-dir').symlink_to(tmp_path.parent, target_is_directory=True)
        (tmp_path / '.git').mkdir()
        (tmp_path / '.git' / 'config').write_text('secret', encoding='utf-8')
        resp = app.download_project_zip(_request('/download/project.zip', cookie=cookie))
        with zipfile.ZipFile(resp.path) as zf:
            names = set(zf.namelist())
            assert names == {'README.md'}
            assert zf.read('README.md') == b'public project'
        outside.unlink()
    finally:
        app.SESSIONS.pop(token, None)


def test_project_download_guest_still_denied(monkeypatch, tmp_path):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': True})
    monkeypatch.setattr(app, 'PROJECT_DOWNLOAD_ENABLED', True)
    monkeypatch.setattr(app, 'PROJECT_ROOT', str(tmp_path))
    token = 'docker-hardening-guest'
    app.SESSIONS[token] = {'authenticated': True, 'role': 'guest', 'expires_at': time.time() + 120}
    try:
        with pytest.raises(HTTPException) as exc:
            app.download_project_zip(_request('/download/project.zip', cookie=f'caop_session={token}'))
        assert exc.value.status_code == 403
    finally:
        app.SESSIONS.pop(token, None)

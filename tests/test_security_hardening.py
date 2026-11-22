import asyncio
import time
import zipfile
import sys
import types

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request
import fastapi.staticfiles

class _DummyStaticFiles:
    def __init__(self, *args, **kwargs):
        pass
    async def __call__(self, scope, receive, send):
        await send({'type': 'http.response.start', 'status': 404, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

fastapi.staticfiles.StaticFiles = _DummyStaticFiles

# Lightweight local test environments may omit PostgreSQL bindings. Only in that
# case provide the minimal import surface required for mocked security tests.
# GitHub Actions installs the real driver for the PostgreSQL integration suite.
try:
    import pyotp  # noqa: F401 - prefer the installed package in CI
except ModuleNotFoundError as exc:
    if exc.name != 'pyotp':
        raise
    pyotp_stub = types.ModuleType('pyotp')
    class _DummyTOTP:
        interval = 30
        def __init__(self, *args, **kwargs):
            pass
        def verify(self, *args, **kwargs):
            return False
        def at(self, *args, **kwargs):
            return '111111'
        def provisioning_uri(self, *args, **kwargs):
            return 'otpauth://dummy'
    pyotp_stub.TOTP = _DummyTOTP
    pyotp_stub.random_base32 = lambda: 'DUMMY'
    sys.modules['pyotp'] = pyotp_stub

try:
    import qrcode  # noqa: F401 - prefer the installed package in CI
except ModuleNotFoundError as exc:
    if exc.name != 'qrcode':
        raise
    qrcode_stub = types.ModuleType('qrcode')
    class _DummyQr:
        def save(self, buf, format=None):
            buf.write(b'dummy')
    qrcode_stub.make = lambda *a, **k: _DummyQr()
    sys.modules['qrcode'] = qrcode_stub

# Never shadow a real installed psycopg2 driver: PostgreSQL integration tests
# are collected in the same pytest process and need the real connect() function.
# A stub is only required for lightweight unit-test environments that genuinely
# do not have psycopg2 installed (those environments skip the DB integration suite).
try:
    import psycopg2  # noqa: F401
except ModuleNotFoundError as exc:
    if exc.name != 'psycopg2':
        raise
    psycopg2_stub = types.ModuleType('psycopg2')
    class _PsycopgError(Exception):
        pass
    psycopg2_stub.Error = _PsycopgError
    psycopg2_stub.connect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('DB access not expected in security unit tests'))
    sys.modules['psycopg2'] = psycopg2_stub

import app


def _request(path='/', method='GET', cookie=None, client=('127.0.0.1', 12345), accept='application/json'):
    headers = [(b'accept', accept.encode())]
    if cookie:
        headers.append((b'cookie', cookie.encode()))
    scope = {
        'type': 'http',
        'http_version': '1.1',
        'method': method,
        'scheme': 'https',
        'path': path,
        'raw_path': path.encode(),
        'query_string': b'',
        'headers': headers,
        'client': client,
        'server': ('testserver', 443),
    }
    return Request(scope)


def test_auth_disabled_login_still_requires_real_admin_credentials(monkeypatch):
    app.LOGIN_FAILURES.clear()
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(app, 'load_auth_config', lambda: {
        'enabled': False,
        'username': 'admin',
        'password_hash': 'stored',
        'guest_enabled': False,
        'guest_username': '',
        'guest_password_hash': '',
    })
    monkeypatch.setattr(app, '_get_admin_user_by_username', lambda *a, **k: None)
    monkeypatch.setattr(app, '_find_active_guest_user', lambda *a, **k: None)
    monkeypatch.setattr(app, '_verify_secret', lambda stored, value: stored == 'stored' and value == 'correct')

    with pytest.raises(HTTPException) as exc:
        app.auth_login(app.LoginPayload(username='attacker', password='wrong'), _request('/auth/login', 'POST'))
    assert exc.value.status_code == 401


def test_auth_disabled_valid_admin_login_sets_secure_cookie(monkeypatch):
    app.LOGIN_FAILURES.clear()
    app.SESSIONS.clear()
    monkeypatch.setattr(app, 'SESSION_COOKIE_SECURE', True)
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(app, 'load_auth_config', lambda: {
        'enabled': False,
        'username': 'admin',
        'password_hash': 'stored',
        'guest_enabled': False,
        'guest_username': '',
        'guest_password_hash': '',
        'twofa_enabled': False,
    })
    monkeypatch.setattr(app, '_get_admin_user_by_username', lambda username, include_disabled=True: {
        'id': 7, 'username': 'admin', 'password_hash': 'stored', 'enabled': True, 'twofa_enabled': False
    } if username == 'admin' else None)
    monkeypatch.setattr(app, '_find_active_guest_user', lambda *a, **k: None)
    monkeypatch.setattr(app, '_verify_secret', lambda stored, value: stored == 'stored' and value == 'correct')

    resp = app.auth_login(app.LoginPayload(username='admin', password='correct'), _request('/auth/login', 'POST'))
    cookie = resp.headers.get('set-cookie', '')
    assert 'caop_session=' in cookie
    assert 'HttpOnly' in cookie
    assert 'Secure' in cookie
    assert 'SameSite=lax' in cookie


def test_sensitive_config_get_is_admin_only_even_when_global_auth_disabled(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(app, 'get_session', lambda token: None)

    async def next_handler(_request):
        return JSONResponse({'ok': True})

    resp = asyncio.run(app.auth_middleware(_request('/config/auth', 'GET'), next_handler))
    assert resp.status_code == 403


def test_anonymous_write_remains_blocked_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(app, 'get_session', lambda token: None)

    async def next_handler(_request):
        return JSONResponse({'ok': True})

    resp = asyncio.run(app.auth_middleware(_request('/tents', 'POST'), next_handler))
    assert resp.status_code == 401


def test_project_zip_disabled_by_default(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    token = 'admin-token'
    app.SESSIONS[token] = {'authenticated': True, 'role': 'admin', 'admin_id': 1, 'username': 'admin', 'expires_at': time.time() + 60}
    monkeypatch.setattr(app, 'PROJECT_DOWNLOAD_ENABLED', False)
    with pytest.raises(HTTPException) as exc:
        app.download_project_zip(_request('/download/project.zip', cookie=f'caop_session={token}'))
    assert exc.value.status_code == 404
    app.SESSIONS.pop(token, None)


def test_project_zip_never_contains_env_or_private_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    (tmp_path / 'README.md').write_text('safe', encoding='utf-8')
    (tmp_path / '.env').write_text('SECRET=bad', encoding='utf-8')
    (tmp_path / '.env.production').write_text('SECRET=bad2', encoding='utf-8')
    (tmp_path / 'server.key').write_text('private', encoding='utf-8')
    token = 'admin-token'
    app.SESSIONS[token] = {'authenticated': True, 'role': 'admin', 'admin_id': 1, 'username': 'admin', 'expires_at': time.time() + 60}
    monkeypatch.setattr(app, 'PROJECT_ROOT', str(tmp_path))
    monkeypatch.setattr(app, 'PROJECT_DOWNLOAD_ENABLED', True)
    resp = app.download_project_zip(_request('/download/project.zip', cookie=f'caop_session={token}'))
    with zipfile.ZipFile(resp.path) as zf:
        names = set(zf.namelist())
    assert 'README.md' in names
    assert '.env' not in names
    assert '.env.production' not in names
    assert 'server.key' not in names
    app.SESSIONS.pop(token, None)


def test_history_api_disable_flag_is_enforced(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'history_api_enabled': False})
    resp = app.api_history_for_device('anything')
    assert resp.status_code == 403


def test_revoke_admin_sessions_removes_existing_sessions():
    app.SESSIONS.clear()
    now = time.time() + 60
    app.SESSIONS['a'] = {'authenticated': True, 'role': 'admin', 'admin_id': 5, 'username': 'alice', 'expires_at': now}
    app.SESSIONS['b'] = {'authenticated': True, 'role': 'admin', 'admin_id': 6, 'username': 'bob', 'expires_at': now}
    assert app._revoke_admin_sessions(5, 'alice') == 1
    assert 'a' not in app.SESSIONS
    assert 'b' in app.SESSIONS
    app.SESSIONS.clear()


def test_login_rate_limit_trips(monkeypatch):
    app.LOGIN_FAILURES.clear()
    monkeypatch.setattr(app, 'LOGIN_RATE_LIMIT_ATTEMPTS', 3)
    monkeypatch.setattr(app, 'LOGIN_RATE_LIMIT_WINDOW_SECONDS', 900)
    req = _request('/auth/login', 'POST', client=('192.0.2.10', 1234))
    for _ in range(3):
        app._record_login_failure('admin', req)
    with pytest.raises(HTTPException) as exc:
        app._check_login_rate_limit('admin', req)
    assert exc.value.status_code == 429
    app.LOGIN_FAILURES.clear()


def test_compose_binds_api_to_loopback_by_default():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for filename in ('docker-compose.yml', 'docker-compose.images.yml'):
        text = (root / filename).read_text(encoding='utf-8')
        assert '${GT_API_BIND_ADDRESS:-127.0.0.1}:8088:8080' in text


def test_twofa_preauth_is_revoked_after_too_many_failures(monkeypatch):
    app.SESSIONS.clear()
    monkeypatch.setattr(app, 'TWOFA_MAX_ATTEMPTS', 3)
    monkeypatch.setattr(app, '_get_admin_user_by_id', lambda *a, **k: None)
    monkeypatch.setattr(app, 'load_auth_config', lambda: {
        'twofa_enabled': True,
        'totp_secret': 'DUMMY',
        'recovery_codes_json': '[]',
    })
    token = 'preauth-test'
    app.SESSIONS[token] = {
        'preauth': True,
        'role': 'admin',
        'username': 'admin',
        'admin_id': None,
        'expires_at': time.time() + 300,
        'attempts': 0,
    }
    req = _request('/auth/login/2fa', 'POST')
    payload = app.Login2FAPayload(preauth_token=token, code='000000', recoveryCode='')
    for expected in (401, 401, 429):
        with pytest.raises(HTTPException) as exc:
            app.auth_login_2fa(payload, req)
        assert exc.value.status_code == expected
    assert token not in app.SESSIONS


def _request_with_query(path, query, *, method='GET', cookie=None, accept='application/json'):
    headers = [(b'accept', accept.encode())]
    if cookie:
        headers.append((b'cookie', cookie.encode()))
    scope = {
        'type': 'http',
        'http_version': '1.1',
        'method': method,
        'scheme': 'https',
        'path': path,
        'raw_path': path.encode(),
        'query_string': query.encode(),
        'headers': headers,
        'client': ('127.0.0.1', 12345),
        'server': ('testserver', 443),
    }
    return Request(scope)


def test_guest_dashboard_html_does_not_contain_adjust_button():
    app.SESSIONS.clear()
    now = time.time() + 60
    app.SESSIONS['guest-token'] = {'authenticated': True, 'role': 'guest', 'username': 'guest', 'expires_at': now}
    app.SESSIONS['admin-token'] = {'authenticated': True, 'role': 'admin', 'username': 'admin', 'expires_at': now}

    guest_html = app.dashboard_page(_request_with_query('/dashboard', 'embed=1', cookie='caop_session=guest-token', accept='text/html'))
    admin_html = app.dashboard_page(_request_with_query('/dashboard', 'embed=1', cookie='caop_session=admin-token', accept='text/html'))

    assert '<button id="openGrowProfileBtn"' not in guest_html
    assert '<button id="openGrowProfileBtn"' in admin_html
    app.SESSIONS.clear()


def test_guest_cannot_open_grow_profile_route_even_by_direct_call():
    app.SESSIONS.clear()
    app.SESSIONS['guest-token'] = {'authenticated': True, 'role': 'guest', 'username': 'guest', 'expires_at': time.time() + 60}
    request = _request_with_query('/grow-profile', 'embed=1&tent=1', cookie='caop_session=guest-token', accept='text/html')
    with pytest.raises(HTTPException) as exc:
        app.grow_profile_page(request)
    assert exc.value.status_code == 403
    assert exc.value.detail == 'admin required'
    app.SESSIONS.clear()


def test_guest_cannot_open_grow_profile_shell_query(monkeypatch):
    app.SESSIONS.clear()
    app.SESSIONS['guest-token'] = {'authenticated': True, 'role': 'guest', 'username': 'guest', 'expires_at': time.time() + 60}
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': True})
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)

    async def next_handler(_request):
        return JSONResponse({'ok': True})

    request = _request_with_query('/app', 'page=grow-profile&tent=1', cookie='caop_session=guest-token')
    resp = asyncio.run(app.auth_middleware(request, next_handler))
    assert resp.status_code == 403
    app.SESSIONS.clear()

@pytest.mark.parametrize('path,method', [
    ('/tents', 'GET'),
    ('/api/export/analysis', 'GET'),
    ('/api/export/analysis.zip', 'GET'),
    ('/tents', 'POST'),
    ('/setup', 'GET'),
])
def test_auth_configuration_failure_fails_closed_even_for_anonymous_read_only(monkeypatch, path, method):
    """A database outage must never be treated as an intentional auth-disabled mode."""
    monkeypatch.setattr(app, 'load_auth_config', lambda: (_ for _ in ()).throw(RuntimeError('DB offline')))
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    called = []

    async def next_handler(request):
        called.append(request.url.path)
        return JSONResponse({'ok': True})

    resp = asyncio.run(app.auth_middleware(_request(path, method), next_handler))
    assert resp.status_code == 503
    assert b'Authentication service unavailable' in resp.body
    assert resp.headers.get('cache-control') == 'no-store'
    assert not called


@pytest.mark.parametrize('config', [None, {}, {'enabled': None}, {'enabled': 'false'}])
def test_invalid_auth_configuration_fails_closed(monkeypatch, config):
    monkeypatch.setattr(app, 'load_auth_config', lambda: config)
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    async def next_handler(request):
        return JSONResponse({'ok': True})
    resp = asyncio.run(app.auth_middleware(_request('/tents'), next_handler))
    assert resp.status_code == 503


def test_admin_helper_denies_on_auth_db_error_even_with_valid_session(monkeypatch):
    token = 'admin-fail-closed'
    app.SESSIONS[token] = {'authenticated': True, 'role': 'admin', 'expires_at': time.time() + 60}
    monkeypatch.setattr(app, 'load_auth_config', lambda: (_ for _ in ()).throw(OSError('DB unavailable')))
    try:
        with pytest.raises(HTTPException) as exc:
            app.require_admin(_request('/config/auth', cookie=f'caop_session={token}'))
        assert exc.value.status_code == 503
    finally:
        app.SESSIONS.pop(token, None)


def test_legacy_auth_disabled_mode_no_longer_grants_anonymous_read(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    called = []
    async def next_handler(request):
        called.append(request.url.path)
        return JSONResponse({'ok': True})
    resp = asyncio.run(app.auth_middleware(_request('/tents'), next_handler))
    assert resp.status_code == 401
    assert resp.headers['cache-control'] == 'no-store'
    assert not called


def test_admin_helper_requires_session_even_in_auth_disabled_readonly_mode(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    with pytest.raises(HTTPException) as exc:
        app.require_admin(_request('/config/auth'))
    assert exc.value.status_code == 403



def test_missing_auth_configuration_record_is_not_auth_disabled(monkeypatch):
    class EmptyDatabase:
        def __enter__(self): return self
        def __exit__(self,*args): return None
        def cursor(self): return self
        def execute(self,*args): pass
        def fetchone(self): return None
    monkeypatch.setattr(app, 'get_conn', EmptyDatabase)
    with pytest.raises(RuntimeError,match='Authentication configuration row missing'):
        app.load_auth_config()


@pytest.mark.parametrize('path', ['/auth/login', '/auth/login/2fa', '/install', '/api/install', '/favicon.svg'])
def test_login_and_bootstrap_paths_remain_available_during_auth_outage(monkeypatch, path):
    monkeypatch.setattr(app, 'load_auth_config', lambda: (_ for _ in ()).throw(RuntimeError('DB offline')))
    async def next_handler(request):
        return JSONResponse({'public': True})
    resp = asyncio.run(app.auth_middleware(_request(path), next_handler))
    assert resp.status_code == 200


@pytest.mark.parametrize('path,method', [
    ('/', 'GET'), ('/health', 'GET'), ('/auth/whoami', 'GET'),
    ('/app', 'GET'), ('/setup', 'GET'), ('/dashboard', 'GET'),
    ('/grow-guide', 'GET'), ('/tents', 'GET'), ('/tents/2/latest', 'GET'),
    ('/tents/2/preview', 'GET'), ('/tents/2/camera-positions', 'GET'),
    ('/api/export/analysis', 'GET'), ('/api/export/analysis.zip', 'GET'),
    ('/static/grow-guide-de.html', 'GET'), ('/config/auth', 'GET'),
    ('/openapi.json', 'GET'), ('/docs', 'GET'),
    ('/tents/2/camera-positions', 'PUT'), ('/tents', 'POST'),
])
@pytest.mark.parametrize('stored_enabled', [True, False])
def test_every_app_route_denies_anonymous_even_legacy_auth_disabled(monkeypatch, path, method, stored_enabled):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': stored_enabled})
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    called = []
    async def next_handler(request):
        called.append(request.url.path)
        return JSONResponse({'secret': 'must not be served'})
    resp = asyncio.run(app.auth_middleware(_request(path, method), next_handler))
    assert resp.status_code in (401, 403), (path, method, stored_enabled)
    assert b'must not be served' not in resp.body
    assert not called


@pytest.mark.parametrize('path', ['/app', '/dashboard', '/grow-guide', '/tents/2/preview'])
def test_unauthenticated_html_redirects_only_to_login(monkeypatch, path):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    async def next_handler(request):
        raise AssertionError('protected page handler must not run')
    resp = asyncio.run(app.auth_middleware(_request(path, accept='text/html'), next_handler))
    assert resp.status_code == 302
    assert resp.headers['location'] == '/auth/login'
    assert resp.headers['cache-control'] == 'no-store'


def test_authenticated_admin_and_guest_still_can_read_dashboard(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    app.SESSIONS['mandatory-admin'] = {'authenticated': True, 'role': 'admin', 'expires_at': time.time()+100}
    app.SESSIONS['mandatory-guest'] = {'authenticated': True, 'role': 'guest', 'expires_at': time.time()+100}
    async def next_handler(request):
        return JSONResponse({'ok': True})
    try:
        for token in ('mandatory-admin', 'mandatory-guest'):
            resp = asyncio.run(app.auth_middleware(_request('/dashboard', cookie=f'caop_session={token}'), next_handler))
            assert resp.status_code == 200
        resp = asyncio.run(app.auth_middleware(_request('/setup', cookie='caop_session=mandatory-guest'), next_handler))
        assert resp.status_code == 403
        resp = asyncio.run(app.auth_middleware(_request('/tents', 'POST', cookie='caop_session=mandatory-guest'), next_handler))
        assert resp.status_code == 403
    finally:
        app.SESSIONS.pop('mandatory-admin', None)
        app.SESSIONS.pop('mandatory-guest', None)


def test_disabling_auth_via_api_is_rejected_before_database_access(monkeypatch):
    monkeypatch.setattr(app, 'get_conn', lambda: (_ for _ in ()).throw(AssertionError('DB must not be touched')))
    with pytest.raises(HTTPException) as exc:
        app.set_auth_config(app.AuthConfigPayload(enabled=False), _request('/config/auth', 'POST'))
    assert exc.value.status_code == 400
    assert 'cannot be disabled' in exc.value.detail


def test_setup_auth_toggle_is_not_interactive():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1]/'api/app.py').read_text(encoding='utf-8')
    assert 'checked disabled style=' in source
    assert "enabled: true," in source
    assert "enableAuth: 'Anmeldung immer erforderlich'" in source
    assert "enableAuth: 'Login always required'" in source
    assert 'persistedEnabled' not in source


def test_whoami_does_not_expose_anonymous_application_status():
    with pytest.raises(HTTPException) as exc:
        app.auth_whoami(_request('/auth/whoami'))
    assert exc.value.status_code == 401


def test_public_install_not_available_when_admin_exists_without_legacy_mirror(monkeypatch):
    queries = []
    class Db:
        def __enter__(self): return self
        def __exit__(self,*a): return None
        def cursor(self): return self
        def execute(self, sql, *args): queries.append(sql)
        def fetchone(self): return (None,) if len(queries) == 1 else (1,)
    monkeypatch.setattr(app, 'INSTALL_API_ENABLED', True)
    monkeypatch.setattr(app, 'get_conn', Db)
    assert app.is_initial_install_available() is False
    assert len(queries) == 2


def test_bootstrap_available_on_truly_empty_install(monkeypatch):
    queries = []
    class Db:
        def __enter__(self): return self
        def __exit__(self,*a): return None
        def cursor(self): return self
        def execute(self, sql, *args): queries.append(sql)
        def fetchone(self): return None
    monkeypatch.setattr(app, 'INSTALL_API_ENABLED', True)
    monkeypatch.setattr(app, 'get_conn', Db)
    assert app.is_initial_install_available() is True
    assert len(queries) == 2


def test_recovery_cli_rejects_disable_auth(monkeypatch):
    import argparse
    import manage_auth
    monkeypatch.setattr(manage_auth, '_connect', lambda: (_ for _ in ()).throw(AssertionError('no DB should be accessed')))
    args = argparse.Namespace(username=None, password=None, password_env=None, password_stdin=False,
                              prompt_password=False, enable_auth=False, disable_auth=True, disable_2fa=False)
    with pytest.raises(SystemExit, match='mandatory and cannot be disabled'):
        manage_auth.cmd_set_admin(args)


def test_security_suite_preserves_installed_postgresql_driver():
    """Security imports must not replace the live driver used by irrigation tests."""
    from importlib.metadata import PackageNotFoundError, version
    try:
        version('psycopg2-binary')
    except PackageNotFoundError:
        pytest.skip('psycopg2-binary is not installed in this lightweight test environment')
    import psycopg2
    assert hasattr(psycopg2, '__file__'), 'A test stub replaced the installed psycopg2 module'
    assert callable(psycopg2.connect)

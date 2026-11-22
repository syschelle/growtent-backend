"""v0.411: fresh admin verification on sensitive actions and safe 2FA QR enrollment."""
import asyncio
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

# Avoid requiring a real PostgreSQL instance for isolated access-control tests.
import test_security_hardening
import app
from test_security_hardening import _request


ADMIN = {
    'id': 11, 'username': 'chief', 'enabled': True,
    'password_hash': '$argon2id$unit-test-only', 'twofa_enabled': False,
    'totp_secret': None,
}


@pytest.fixture
def admin_session(monkeypatch):
    app.SESSIONS['step-session'] = {
        'authenticated': True, 'role': 'admin', 'username': 'chief',
        'admin_id': 11, 'expires_at': time.time() + 3600,
    }
    monkeypatch.setattr(app, '_get_admin_user_by_id', lambda id, include_disabled=True: dict(ADMIN))
    monkeypatch.setattr(app, '_verify_secret', lambda stored, password: stored == ADMIN['password_hash'] and password == 'good-password')
    yield app.SESSIONS['step-session']
    app.SESSIONS.pop('step-session', None)
    app.TWOFA_ENROLL.clear()


def _admin_request(path, method='GET'):
    return _request(path, method, cookie='caop_session=step-session')


def test_sensitive_paths_and_safe_unchanged_controls():
    sensitive = [('/config/admins','POST'),('/config/admins/11','PUT'),
                 ('/config/admins/11','DELETE'),('/config/admins/11/2fa','POST'),
                 ('/config/auth','POST'),('/config/auth/2fa','POST'),('/config/auth/2fa/verify','POST'),
                 ('/config/backup/export','GET'),('/config/backup/import','POST')]
    for path, method in sensitive:
        assert app._step_up_required_for(path, method)
    for path, method in [('/config/auth', 'GET'),('/config/admins','GET'),
                         ('/config/guests','POST'),('/tents/2/startWatering','POST'),
                         ('/tents/2/preview','GET')]:
        assert not app._step_up_required_for(path, method)


def test_step_up_password_and_expiry(admin_session):
    with pytest.raises(HTTPException) as exc:
        app.require_recent_admin_confirmation(_admin_request('/config/backup/export'))
    assert exc.value.status_code == 428
    bad = app.StepUpPayload(password='bad-password')
    with pytest.raises(HTTPException) as exc:
        app.auth_step_up(bad, _admin_request('/auth/step-up','POST'))
    assert exc.value.status_code == 401
    response = app.auth_step_up(app.StepUpPayload(password='good-password'), _admin_request('/auth/step-up','POST'))
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    app.require_recent_admin_confirmation(_admin_request('/config/backup/export'))
    admin_session['step_up_until'] = time.time()-1
    with pytest.raises(HTTPException) as exc:
        app.require_recent_admin_confirmation(_admin_request('/config/backup/export'))
    assert exc.value.status_code == 428


def test_step_up_proof_bound_to_admin_credentials(admin_session, monkeypatch):
    app.auth_step_up(app.StepUpPayload(password='good-password'), _admin_request('/auth/step-up','POST'))
    changed = {**ADMIN, 'password_hash': '$argon2id$new-password'}
    monkeypatch.setattr(app, '_get_admin_user_by_id', lambda *a, **k: changed)
    with pytest.raises(HTTPException) as exc:
        app.require_recent_admin_confirmation(_admin_request('/config/admins','POST'))
    assert exc.value.status_code == 428


def test_step_up_totp_required_when_active(admin_session, monkeypatch):
    changed = {**ADMIN, 'twofa_enabled':True, 'totp_secret':'ABCDEF'}
    monkeypatch.setattr(app, '_get_admin_user_by_id', lambda *a, **k: changed)
    monkeypatch.setattr(app, '_consume_totp_code', lambda **kwargs: kwargs.get('code') == '456789')
    with pytest.raises(HTTPException) as exc:
        app.auth_step_up(app.StepUpPayload(password='good-password'), _admin_request('/auth/step-up','POST'))
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc:
        app.auth_step_up(app.StepUpPayload(password='good-password',code='000000'), _admin_request('/auth/step-up','POST'))
    assert exc.value.status_code == 401
    app.auth_step_up(app.StepUpPayload(password='good-password',code='456789'), _admin_request('/auth/step-up','POST'))
    app.require_recent_admin_confirmation(_admin_request('/config/backup/export'))


def test_step_up_failed_attempt_limit(admin_session):
    for attempt in range(4):
        with pytest.raises(HTTPException) as exc:
            app.auth_step_up(app.StepUpPayload(password='bad'), _admin_request('/auth/step-up','POST'))
        assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc:
        app.auth_step_up(app.StepUpPayload(password='bad'), _admin_request('/auth/step-up','POST'))
    assert exc.value.status_code == 429
    with pytest.raises(HTTPException) as exc:
        app.auth_step_up(app.StepUpPayload(password='good-password'), _admin_request('/auth/step-up','POST'))
    assert exc.value.status_code == 429


def test_guest_cannot_confirm_even_if_password_known(admin_session):
    app.SESSIONS['step-guest'] = {'authenticated':True,'role':'guest','username':'guest','expires_at':time.time()+300}
    try:
        req = _request('/auth/step-up','POST', cookie='caop_session=step-guest')
        with pytest.raises(HTTPException) as exc:
            app.auth_step_up(app.StepUpPayload(password='good-password'),req)
        assert exc.value.status_code == 403
    finally:
        app.SESSIONS.pop('step-guest',None)


def test_qr_token_bound_to_enrollment_session(admin_session, monkeypatch):
    app.TWOFA_ENROLL['enrollment-token'] = {'secret':'ABC', 'username':'chief',
        'expires_at':time.time()+600, 'owner_session':'step-session'}
    class QR:
        def save(self, dest, format=None):dest.write(b'image-bytes')
    monkeypatch.setattr(app, 'pyotp', SimpleNamespace(TOTP=lambda secret: SimpleNamespace(provisioning_uri=lambda **_: 'otpauth://totp/name?secret='+secret)))
    monkeypatch.setattr(app, 'qrcode', SimpleNamespace(make=lambda uri:QR()))
    resp=app.auth_qr_png('enrollment-token',_admin_request('/auth/qr.png'))
    assert resp.status_code==200 and resp.body == b'image-bytes'
    assert resp.headers['cache-control'] == 'no-store'
    with pytest.raises(HTTPException) as exc:
        app.auth_qr_png('enrollment-token', _request('/auth/qr.png','GET',cookie='caop_session=stolen'))
    assert exc.value.status_code == 403
    app.SESSIONS['another-admin'] = {**app.SESSIONS['step-session']}
    try:
        with pytest.raises(HTTPException) as exc:
            app.auth_qr_png('enrollment-token', _request('/auth/qr.png', cookie='caop_session=another-admin'))
        assert exc.value.status_code == 404
    finally:
        app.SESSIONS.pop('another-admin',None)


def test_middleware_requires_confirmation_even_for_legacy_route(admin_session,monkeypatch):
    monkeypatch.setattr(app,'load_auth_config',lambda:{'enabled':True})
    monkeypatch.setattr(app,'is_initial_install_available',lambda:False)
    async def handler(req):return JSONResponse({'ok':True})
    req=_admin_request('/config/backup/export','GET')
    response=asyncio.run(app.auth_middleware(req,handler))
    assert response.status_code==428
    assert response.headers['x-step-up-required']=='1'
    app.auth_step_up(app.StepUpPayload(password='good-password'), _admin_request('/auth/step-up','POST'))
    response=asyncio.run(app.auth_middleware(req,handler))
    assert response.status_code==200


def test_get_auth_config_does_not_leak_existing_totp_seed(monkeypatch):
    monkeypatch.setattr(app,'load_auth_config',lambda:{'enabled':True,'username':'chief',
        'password_hash':'p','twofa_enabled':True,'totp_secret':'secret-stays-server-side'})
    data = app.get_auth_config()
    assert data['otpauth_url'] is None and data['qr_png_url'] is None
    assert 'secret-stays-server-side' not in str(data)


def test_modular_router_has_step_up_dependencies():
    from pathlib import Path
    from routes.auth import router as auth_router
    from routes.system import router as system_router
    for router in (auth_router,system_router):
        for route in router.routes:
            if app._step_up_required_for(route.path, list(route.methods)[0]):
                assert any(d.call is app.require_recent_admin_confirmation for d in route.dependant.dependencies), route.path


def test_modular_asgi_router_blocks_backup_until_fresh_step_up(admin_session,monkeypatch):
    """Exercise the production router, not just a directly called unit function."""
    import httpx
    import main
    monkeypatch.setattr(app,'load_auth_config',lambda:{'enabled':True})
    monkeypatch.setattr(app,'is_initial_install_available',lambda:False)
    monkeypatch.setattr(app,'export_config_backup',lambda: JSONResponse({'data':'backup-test-only'}))
    async def exercise():
        transport=httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport,base_url='https://canopyops.test',
                                     cookies={'caop_session':'step-session'}) as client:
            response=await client.get('/config/backup/export')
            assert response.status_code==428, (response.status_code,response.text)
            assert response.headers['x-step-up-required']=='1'
            wrong=await client.post('/auth/step-up',json={'password':'bad-password'})
            assert wrong.status_code==401
            correct=await client.post('/auth/step-up',json={'password':'good-password'})
            assert correct.status_code==200, correct.text
            response=await client.get('/config/backup/export')
            assert response.status_code==200 and response.json()=={'data':'backup-test-only'}
    asyncio.run(exercise())


def test_enrollment_returns_only_session_bound_opaque_qr_url(admin_session,monkeypatch):
    monkeypatch.setattr(app,'_hash_secret',lambda value:'hashed')
    monkeypatch.setattr(app,'pyotp',SimpleNamespace(random_base32=lambda:'NOT-IN-URL'))
    response = app.set_admin_2fa_config(11,app.AdminTwoFAConfigPayload(enabled=True),
                                       _admin_request('/config/admins/11/2fa','POST'))
    assert response['pending_2fa'] is True
    assert response['otpauth_url'] is None
    assert 'secret=' not in response['qr_png_url']
    assert 'NOT-IN-URL' not in str(response)
    token=response['verify_token']
    assert response['qr_png_url']==f'/auth/qr.png?token={token}'
    assert app.TWOFA_ENROLL[token]['owner_session']=='step-session'


def test_session_refresh_does_not_resurrect_revoked_admin_session(admin_session):
    admin_session['expires_at'] = time.time() + 100
    app.SESSIONS.pop('step-session', None)
    assert app._refresh_session_if_needed('step-session', admin_session) is None
    assert 'step-session' not in app.SESSIONS

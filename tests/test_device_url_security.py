"""Security regression tests: guest confidentiality and untrusted device URLs.

No live database, camera, controller or network traffic is used.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

import test_security_hardening  # Ensures lightweight DB/2FA stubs for app imports in isolated CI.
from services.tent_urls import validate_rtsp_url, validate_source_url


@pytest.mark.parametrize('value', [
    'exec:touch /tmp/malicious', 'ffmpeg:rtsp://192.168.1.5/feed',
    'http://192.168.1.5/stream', 'file:///etc/passwd',
    'rtsp://127.0.0.1/stream', 'rtsp://169.254.169.254/stream',
    'rtsp://go2rtc:8554/stream', 'rtsp://db/stream',
    'rtsp://10.1.2.3\\@evil/stream',
])
def test_bad_camera_sources_are_rejected(value):
    with pytest.raises(ValueError):
        validate_rtsp_url(value)


@pytest.mark.parametrize('value', [
    'file:///etc/passwd', 'ftp://192.168.1.2/file',
    'http://localhost:8080/secret', 'http://127.0.0.1/secret',
    'http://db:5432', 'http://go2rtc:1984/api/streams',
    'http://169.254.169.254/latest/meta-data',
    'http://user:password@192.168.1.5/api/state',
    'https://example.com@localhost/private',
    'http://192.168.1.5:bad-port/api/state',
])
def test_bad_controller_sources_are_rejected(value):
    with pytest.raises(ValueError):
        validate_source_url(value)


def test_real_private_device_urls_remain_accepted():
    assert validate_source_url('http://192.168.178.58:8080/api/state') == 'http://192.168.178.58:8080/api/state'
    assert validate_rtsp_url('rtsp://user:password@192.168.178.77:554/stream') == 'rtsp://user:password@192.168.178.77:554/stream'


def test_dns_resolution_must_stay_on_lan(monkeypatch):
    import services.tent_urls as urls
    monkeypatch.setattr(urls.socket, 'getaddrinfo', lambda *a: [(None, None, None, None, ('8.8.8.8', 80))])
    with pytest.raises(ValueError, match='unsafe IP'):
        urls.validate_source_url('http://camera.example.org/api/state', resolve=True)
    monkeypatch.setattr(urls.socket, 'getaddrinfo', lambda *a: [(None, None, None, None, ('192.168.178.77', 80))])
    assert urls.validate_rtsp_url('rtsp://camera.example.org/stream', resolve=True)


class FakeDB:
    def __init__(self, row):
        self.row = row
    @contextmanager
    def connection(self):
        yield self
    @contextmanager
    def cursor(self):
        yield self
    def execute(self, statement, params=None):
        pass
    def fetchone(self):
        return self.row


def test_latest_hides_rtsp_credentials_and_blocks_host_header_link(monkeypatch):
    import app
    db = FakeDB(('rtsp://sensitive:secret@192.168.178.77/live', '{}', datetime(2026, 11, 22, tzinfo=timezone.utc), {}))
    monkeypatch.setattr(app, 'get_conn', db.connection)
    monkeypatch.setattr(app, 'get_session', lambda token: {'role': 'guest'} if token == 'guest' else {'role': 'admin'} if token == 'admin' else None)
    request = lambda session: SimpleNamespace(cookies={'caop_session': session}, headers={'host': 'evil.invalid:9999'})
    monkeypatch.delenv('GO2RTC_PUBLIC_BASE_URL', raising=False)
    guest = app.latest_state(2, request('guest'))
    assert guest['rtsp_url'] is None and guest['player_url'] is None and guest['webrtc_url'] is None
    assert guest['preview_url'] == '/tents/2/preview'
    assert 'sensitive' not in str(guest) and 'evil.invalid' not in str(guest)
    admin = app.latest_state(2, request('admin'))
    assert admin['rtsp_url'].startswith('rtsp://sensitive:secret@')
    assert admin['player_url'] is None and admin['webrtc_url'] is None


def test_modular_tent_list_hides_rtsp_from_guest(monkeypatch):
    from db import crud
    class ManyDB(FakeDB):
        def fetchall(self):
            return [(2, 'Tent 2', 'http://192.168.178.58/api/state',
                     'rtsp://user:secret@192.168.178.77/stream',
                     '', None, '{}', None, '{}', '["", "", ""]', False, None, None, False, 20.0, datetime(2026,11,22,tzinfo=timezone.utc))]
    monkeypatch.setattr(crud, 'get_conn', ManyDB(None).connection)
    guest=crud.list_tents_raw()
    admin=crud.list_tents_raw(include_sensitive=True)
    assert guest[0]['rtsp_url'] is None
    assert guest[0]['source_url'] == ''
    assert guest[0]['backend_controller_url'] == ''
    assert 'user:secret@' not in str(guest)
    assert admin[0]['rtsp_url'] == 'rtsp://user:secret@192.168.178.77/stream'


def test_device_action_does_not_follow_redirect_or_echo_body(monkeypatch):
    import app
    monkeypatch.setattr(app, 'get_tent_by_id', lambda tent_id: {'source_url':'http://192.168.178.58/api/state'})
    requests=[]
    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs['follow_redirects'] is False
        def __enter__(self):return self
        def __exit__(self, *a):pass
        def post(self, url):
            requests.append(url)
            return httpx.Response(302, headers={'Location':'http://127.0.0.1/secret'}, content=b'{"private":"DO_NOT_ECHO"}', request=httpx.Request('POST', url))
    monkeypatch.setattr(app.httpx, 'Client', FakeClient)
    result=app.proxy_post_to_tent_action(2,'/relay/4/toggle')
    assert len(requests)==1 and requests[0]=='http://192.168.178.58/relay/4/toggle'
    assert result['status_code']==302 and not result['ok']
    assert 'DO_NOT_ECHO' not in str(result) and '127.0.0.1' not in str(result)
    assert 'target_url' not in result and 'response' not in result


def test_old_unsafe_rtsp_cannot_be_registered_in_go2rtc(monkeypatch):
    import app
    class NeverClient:
        def __init__(self, **kw):
            raise AssertionError('go2rtc should never receive unsafe stream sources')
    monkeypatch.setattr(app.httpx, 'Client', NeverClient)
    app.register_rtsp_stream(2, 'exec:some-command')

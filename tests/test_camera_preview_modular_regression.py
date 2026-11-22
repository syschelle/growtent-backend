"""v0.412: exercise real production router to catch missing preview imports and routes.

No PostgreSQL connection, camera or Shelly device is contacted.
"""
import time
from io import BytesIO

from PIL import Image
from fastapi.testclient import TestClient

import test_security_hardening  # Import-only stubs in lightweight local environments.
import app as legacy
import main


class FakeDB:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self

    def execute(self, query, values):
        assert 'SELECT rtsp_url FROM tents' in query
        assert values == (3,)

    def fetchone(self):
        return ('rtsp://192.168.178.77/stream',)


def test_actual_modular_preview_and_fullscreen_hdr(monkeypatch):
    # Old isolated AST tests injected quote_plus into their own globals and
    # therefore missed the missing import in real api/app.py in v0.411.
    assert callable(legacy.quote_plus)
    jpeg = BytesIO()
    Image.new('RGB', (320, 180), (60, 95, 105)).save(jpeg, format='JPEG')
    raw = jpeg.getvalue()
    sent = []

    class FakeHTTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url):
            sent.append(url)
            return type('FakeResponse', (), {
                'status_code': 200,
                'headers': {'content-type': 'image/jpeg'},
                'content': raw,
            })()

    monkeypatch.setattr(legacy, 'get_conn', FakeDB)
    monkeypatch.setattr(legacy.httpx, 'Client', FakeHTTP)
    monkeypatch.setattr(legacy, 'load_auth_config', lambda: {'enabled': True})
    monkeypatch.setattr(legacy, 'is_initial_install_available', lambda: False)
    legacy.SESSIONS['camera-test-admin'] = {
        'authenticated': True, 'role': 'admin', 'username': 'tester',
        'expires_at': time.time() + 3600,
    }
    try:
        client = TestClient(main.app, cookies={'caop_session': 'camera-test-admin'})
        original = client.get('/tents/3/preview?w=1280&h=720&q=80')
        assert original.status_code == 200, original.text
        assert original.content == raw
        assert original.headers['content-type'].startswith('image/jpeg')
        assert 'src=rtsp%3A%2F%2F192.168.178.77%2Fstream%23media%3Dvideo' in sent[0]
        assert 'width=1280&height=720&q=80' in sent[0]

        enhanced = client.get('/tents/3/preview?w=1280&h=720&q=80&hdr=1')
        assert enhanced.status_code == 200, enhanced.text
        assert enhanced.headers['content-type'].startswith('image/jpeg')
        with Image.open(BytesIO(enhanced.content)) as image:
            assert image.size == (320, 180)

        anonymous = TestClient(main.app).get('/tents/3/preview?w=1280&h=720&q=80')
        assert anonymous.status_code == 401
        assert len(sent) == 2
    finally:
        legacy.SESSIONS.pop('camera-test-admin', None)


def test_shelly_light_schedule_reachable_in_modular_router(monkeypatch):
    monkeypatch.setattr(legacy, 'load_auth_config', lambda: {'enabled': True})
    monkeypatch.setattr(legacy, 'is_initial_install_available', lambda: False)
    calls = []
    def fake_schedule(tent_id, key, force_refresh):
        calls.append((tent_id, key, force_refresh))
        return {'ok': True, 'tent_id': tent_id, 'light_on_time': '06:30'}

    monkeypatch.setattr(legacy, '_get_shelly_schedule_for_key', fake_schedule)
    legacy.SESSIONS['light-test-guest'] = {
        'authenticated': True, 'role': 'guest', 'username': 'guest',
        'expires_at': time.time() + 3600,
    }
    try:
        client = TestClient(main.app, cookies={'caop_session': 'light-test-guest'})
        response = client.get('/tents/3/shelly/light/schedule?refresh=true')
        assert response.status_code == 200, response.text
        assert response.json()['light_on_time'] == '06:30'
        assert calls == [(3, 'light', True)]
        assert TestClient(main.app).get('/tents/3/shelly/light/schedule').status_code == 401
    finally:
        legacy.SESSIONS.pop('light-test-guest', None)

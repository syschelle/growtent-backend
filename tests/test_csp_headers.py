"""CSP + security headers: trusted templates, no injected script permissions."""
import ast
import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.testclient import TestClient

from test_irrigation_ui_runtime import render, extract_scripts
from services.security_headers import CONTENT_SECURITY_POLICY, security_headers_middleware

ROOT = Path(__file__).resolve().parents[1]


def script_hash(code):
    return 'sha256-' + base64.b64encode(hashlib.sha256(code.encode('utf-8')).digest()).decode('ascii')


def _render_other(name, request=None, **entries):
    # Render from the trusted source function, never from a submitted HTML page.
    source = (ROOT / 'api/app.py').read_text(encoding='utf-8')
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.decorator_list = []
    ns = {'FAVICON_LINKS': '', 'APP_VERSION': 'v0.415', 'Request': Request,
          'HTMLResponse': HTMLResponse, 'require_admin': lambda r: None, **entries}
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'app.py', 'exec'), ns)
    rendered = ns[name](request) if request is not None else ns[name]()
    return rendered.body.decode('utf-8') if isinstance(rendered, HTMLResponse) else rendered


@pytest.mark.parametrize('page', [
    'setup_page', 'dashboard_page', 'app_shell_page',
    'strain_library_page', 'grow_profile_page',
])
def test_inline_scripts_on_existing_pages_are_whitelisted(page):
    html = _render_other(page) if page == 'app_shell_page' else render(page)
    scripts = [s for s in extract_scripts(html) if s.strip()]
    assert scripts, page
    for js in scripts:
        assert "'" + script_hash(js) + "'" in CONTENT_SECURITY_POLICY, (page, len(js))


def test_login_and_initial_install_scripts_are_whitelisted():
    login = _render_other('auth_login_page', is_initial_install_available=lambda: False)
    install = _render_other('install_page', is_initial_install_available=lambda: True)
    for page in (login, install):
        assert any(s.strip() for s in extract_scripts(page))
        for js in extract_scripts(page):
            if js.strip():
                assert "'" + script_hash(js) + "'" in CONTENT_SECURITY_POLICY



def test_poll_errors_filter_changes_do_not_change_trusted_script_hash():
    scripts = []
    for tent in ('3', '14', '<script>evil()</script>'):
        request = type('RequestStub', (), {'query_params': {'tent': tent}})()
        html = _render_other('poll_errors_page', request=request)
        scripts.append([s for s in extract_scripts(html) if s.strip()])
        assert html.count('data-tent-filter=') == 1
        assert '__TENT_FILTER__' not in html
    assert scripts[0] == scripts[1] == scripts[2]
    assert "'" + script_hash(scripts[0][0]) + "'" in CONTENT_SECURITY_POLICY

def test_grow_guide_static_template_scripts_are_whitelisted():
    html = (ROOT / 'api/static/grow-guide-page.html').read_text(encoding='utf-8')
    for js in extract_scripts(html):
        if js.strip():
            assert "'" + script_hash(js) + "'" in CONTENT_SECURITY_POLICY


def test_hash_manifest_matches_first_party_source():
    import importlib.util
    spec = importlib.util.spec_from_file_location('generate_csp_hashes', ROOT / 'scripts/generate_csp_hashes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.hashes() == json.loads((ROOT / 'api/services/csp_script_hashes.json').read_text())['hashes']


def test_script_policy_blocks_untrusted_inline_code_and_handler_attributes():
    assert "script-src 'self' 'sha256-" in CONTENT_SECURITY_POLICY
    assert "script-src-attr 'none'" in CONTENT_SECURITY_POLICY
    assert "script-src 'self' 'unsafe-inline'" not in CONTENT_SECURITY_POLICY
    assert "'" + script_hash('alert(document.cookie)') + "'" not in CONTENT_SECURITY_POLICY
    assert "object-src 'none'" in CONTENT_SECURITY_POLICY
    assert "frame-ancestors 'self'" in CONTENT_SECURITY_POLICY
    assert "frame-src 'self'" in CONTENT_SECURITY_POLICY
    # Intentionally no upgrade-insecure-requests; ESP LAN links may be HTTP-only.
    assert 'upgrade-insecure-requests' not in CONTENT_SECURITY_POLICY


def test_headers_cover_normal_api_error_redirect_and_login(monkeypatch):
    test_app = FastAPI()
    test_app.middleware('http')(security_headers_middleware)
    test_app.get('/login')(lambda: HTMLResponse('<h1>Login</h1>'))
    test_app.get('/error')(lambda: JSONResponse({'detail': 'auth required'}, status_code=401))
    test_app.get('/redirect')(lambda: RedirectResponse('/login'))
    monkeypatch.delenv('GT_HSTS_MAX_AGE', raising=False)
    with TestClient(test_app) as client:
        for path in ['/login','/error','/redirect']:
            response = client.get(path, follow_redirects=False)
            assert response.headers['content-security-policy'] == CONTENT_SECURITY_POLICY
            assert response.headers['x-content-type-options'] == 'nosniff'
            assert response.headers['x-frame-options'] == 'SAMEORIGIN'
            assert response.headers['referrer-policy'] == 'no-referrer'
            assert response.headers['cross-origin-resource-policy'] == 'same-origin'
            assert 'strict-transport-security' not in response.headers
        monkeypatch.setenv('GT_HSTS_MAX_AGE', '86400')
        response = client.get('/login')
        assert response.headers['strict-transport-security'] == 'max-age=86400'


def test_no_inline_event_handlers_in_server_rendered_setup():
    from html.parser import HTMLParser
    class Events(HTMLParser):
        handlers = []
        def handle_starttag(self, tag, attrs):
            self.handlers.extend((tag, attr) for attr, _ in attrs if attr.startswith('on'))
    parser = Events()
    parser.feed(render('setup_page'))
    assert not parser.handlers, parser.handlers

"""Chromium CSP smoke: trusted scripts execute, injected script is blocked.

This test inserts the exact production script policy into a CSP <meta> tag,
which Chromium enforces without network access. HTTP response headers (incl.
frame-ancestors) are tested separately in test_csp_headers.py.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from playwright.sync_api import sync_playwright
from test_irrigation_ui_runtime import render
from test_csp_headers import _render_other
from services.security_headers import CONTENT_SECURITY_POLICY


# frame-ancestors is only valid in the HTTP response header, not in <meta>.
META_CSP = CONTENT_SECURITY_POLICY.replace("frame-ancestors 'self'; ", '')


def with_policy(document: str) -> str:
    # The real app fetches these same-origin resources; remove them from this
    # standalone offline smoke to focus on inline script policy enforcement.
    document = re.sub(r'<script\b[^>]*\bsrc=[^>]*></script>', '', document, flags=re.I)
    document = re.sub(r'(<iframe\b[^>]*?)\bsrc="[^"]*"', r'\1', document, flags=re.I)
    csp_meta = '<meta http-equiv="Content-Security-Policy" content="' + html.escape(META_CSP, quote=True) + '">'
    return re.sub(r'<head\b[^>]*>', lambda m: m.group(0) + csp_meta, document, count=1, flags=re.I)


def check(browser):
    cases = [
        ('login', _render_other('auth_login_page', is_initial_install_available=lambda: False),
         'typeof document.getElementById("b1").onclick === "function"'),
        ('install', _render_other('install_page', is_initial_install_available=lambda: True),
         'typeof document.getElementById("b").onclick === "function"'),
        ('setup', render('setup_page'), 'typeof window.formatPotStrains === "function"'),
        ('dashboard', render('dashboard_page'), 'typeof window.chartRangeSettings === "function"'),
        ('shell', _render_other('app_shell_page'), 'typeof window.getLang === "function"'),
        ('poll-errors', _render_other('poll_errors_page', request=type('R', (), {'query_params': {'tent': '3'}})()), 'typeof window.tick === "function"'),
    ]
    for name, markup, predicate in cases:
        page = browser.new_page(viewport={'width': 800, 'height': 600})
        violations = []
        page.on('console', lambda m: violations.append(m.text) if 'Content Security Policy' in m.text else None)
        page.set_content(with_policy(markup), wait_until='domcontentloaded')
        page.wait_for_function(predicate, timeout=10000)
        assert not violations, (name, violations)
        page.close()

    attack = '<html><head></head><body><script>window.__evilExecuted=true</script>' \
             '<img src="data:,x" onerror="window.__evilExecuted=true"></body></html>'
    page = browser.new_page()
    violations = []
    page.on('console', lambda m: violations.append(m.text) if 'Content Security Policy' in m.text else None)
    page.set_content(with_policy(attack), wait_until='domcontentloaded')
    page.wait_for_timeout(200)
    assert page.evaluate('window.__evilExecuted') is None
    assert violations, 'Injected JavaScript must cause a CSP violation'
    page.close()


if __name__ == '__main__':
    with sync_playwright() as playwright:
        kwargs = {'headless': True, 'args': ['--no-sandbox']}
        if Path('/usr/bin/chromium').is_file():
            kwargs['executable_path'] = '/usr/bin/chromium'
        browser = playwright.chromium.launch(**kwargs)
        try:
            check(browser)
        finally:
            browser.close()
    print('CSP Chromium: trusted login/install/setup/dashboard/shell scripts run; injected JS blocked')

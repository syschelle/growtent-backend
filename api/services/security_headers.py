"""Browser-side defense in depth for both legacy and modular FastAPI apps.

Hash allowlist is generated only from trusted source code. Do not hash response
bodies or issue an unrestricted nonce to arbitrary rendered HTML: either
would inadvertently bless an injected <script> tag in a future XSS bug.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_MANIFEST = Path(__file__).with_name('csp_script_hashes.json')
_INLINE_HASHES = json.loads(_MANIFEST.read_text(encoding='utf-8'))['hashes']
if len(_INLINE_HASHES) < 10 or any(not value.startswith('sha256-') for value in _INLINE_HASHES):
    raise RuntimeError('Invalid CSP trusted-script manifest')

# All frontend scripts are bundled on the same origin; styles are still inline
# across the legacy UI and dynamic fullscreen camera pop-up (migration later).
CONTENT_SECURITY_POLICY = '; '.join([
    "default-src 'self'",
    "base-uri 'self'",
    "object-src 'none'",
    "frame-ancestors 'self'",  # embedded dashboards remain same-origin
    "form-action 'self'",
    "script-src 'self' " + ' '.join("'" + value + "'" for value in _INLINE_HASHES),
    "script-src-attr 'none'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",  # image zoom uses a canvas data URI
    "font-src 'self' data:",
    "connect-src 'self'",
    "media-src 'self' blob:",  # fullscreen's local thunderstorm audio
    "frame-src 'self'",  # dashboard embeds inside the app shell
    "worker-src 'self' blob:",
])


def hsts_max_age() -> int:
    """Off by default, to avoid HTTPS lock-in for direct LAN deployments.

    HSTS is only honored by browsers over HTTPS. Reverse proxies may set the
    header themselves. A configured value applies without trusting XFP.
    """
    try:
        return min(63072000, max(0, int(os.getenv('GT_HSTS_MAX_AGE', '0'))))
    except ValueError:
        return 0


async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    response.headers['Content-Security-Policy'] = CONTENT_SECURITY_POLICY
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'
    # No external browser origin is needed for API requests or embedded charts.
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    # Do not set Cross-Origin-Embedder-Policy: go2rtc/media flows may depend on it.
    max_age = hsts_max_age()
    if max_age:
        response.headers['Strict-Transport-Security'] = f'max-age={max_age}'
    return response

# GrowTent Backend v0.408 — Fail-closed authentication and XSS hardening

## Fixed: authentication configuration failure could allow anonymous reads (High)

- A failure while loading authentication settings no longer falls back to an `enabled=false` configuration.
- A missing, malformed or unavailable authentication configuration (including a missing database row) returns HTTP **503** (`Authentication service unavailable`) with `Cache-Control: no-store` before any protected endpoint runs. This includes historical analysis JSON and ZIP exports and tent data.
- `require_admin` fails closed on configuration errors and requires a real administrator session. **Mandatory login:** the anonymous read-only mode has been removed entirely, including for old installations that still store `enabled=false`.
- Dashboard, tents, cameras, GrowGuide, all data exports, static application resources, `/health`, and API data now require a valid session. Unauthenticated HTML users are redirected to `/auth/login`; anonymous API calls receive 401 (administrator-only endpoints may return 403). Only the login/favicon and initial token-protected installation entry points remain public.
- The Setup auth toggle is replaced by a bilingual mandatory-login label; `POST /config/auth` rejects `enabled=false`. The `manage_auth.py --disable-auth` recovery option is explicitly rejected. Imported backups cannot deactivate authentication and must include a usable admin account. Existing database configuration is normalized to `enabled=TRUE` during startup; no new tables or user/password changes are needed.
- `/auth/whoami` returns 401 without a session. The public install flow is offered only when no existing administrator password is present, including the separate admin table.

## Fixed: unescaped dynamic HTML in browser UIs (High)

- Escape user/controller-provided values at HTML text and attribute boundaries in the Setup tent list, tent details, guest accounts, setup and application-shell tent navigation, and dashboard Shelly tiles.
- Escape the controller-provided Shelly address, generation, schedule text, dynamic device name and device URL attributes. Preserve existing Shelly actions.
- Escape QR URL and recovery-code strings in the two 2FA enrollment/management displays. No inline script or rich HTML is accepted from dynamic values.
- Existing German/English strings, dashboard views, equipment control, data exports, HDR camera, markers, read-only guest permissions, irrigation and ESP interactions remain unchanged.

## Validation

- New explicit fail-closed unit tests cover auth database exceptions, malformed auth configuration, mandatory-login enforcement on 19 routes (legacy and current settings), anonymous GET/POST, export routes, administrator checks, authentication disable attempts and install bootstrap checks.
- New actual-Chromium XSS tests exercise malicious tent names, source/RTSP URLs, guest names, navigation labels, and Shelly addresses and schedule strings. No injected DOM nodes or event attributes were created.
- Updated existing test harnesses for escaped Shelly output and the actual v0.407 camera toolbar behavior.
- Local checks: Python non-PostgreSQL suite, all five Node `.mjs` tests, Chromium setup/HDR/camera regression and XSS security checks; CI runs the XSS browser check as well.
- Isolated PostgreSQL integration, Docker image build, real devices, dependency advisory scanning and external penetration testing are **not** covered by these local results.

# Security review and fixes — v0.408

Scope: Source-level review of the v0.407 FastAPI authentication middleware, sensitive-route helper, browser output handling for Setup, Shelly devices, tent navigation and 2FA. This is a targeted fix release, **not a complete penetration test**.

| Finding | Previous behavior | v0.408 remediation | Severity |
|---|---|---|---|
| AUTH-01 Fail-open authentication | A database/auth-config exception caused `enabled=false` fallback, allowing anonymous GETs to protected APIs. | Reject such requests with HTTP 503, including a missing auth config database row and no-store; reject malformed configurations and protect direct admin checks. | High |
| AUTH-02 Anonymous-read-only mode | `enabled=false` permitted anonymous dashboard/API reads. | Require a valid session for all application data regardless of legacy setting; disable changing setting via UI/API and migrate it to true on startup. | High |
| WEB-01 Unescaped browser output | Tent labels, source URLs, guest names, Shelly IP/schedule and device details could be injected into HTML templates. | Escape all dynamic text and HTML-attribute values at identified sinks; verify malicious payloads remain text in Chromium. | High |
| WEB-02 Dynamic 2FA HTML fields | QR URLs and recovery-code data were inserted into markup without full output encoding in some flows. | Apply HTML encoding to these fields. | Medium |

Protected GET/POST and admin paths are explicitly tested with `load_auth_config()` raising. The formerly supported `enabled=false` anonymous mode has been fully retired; no app resources are available to unauthenticated visitors. The setting cannot be disabled through the API, Setup or the recovery CLI, and legacy values are normalized on application startup. Backups with no usable administrator are rejected; restore always forces login enabled. First-time setup checks both the legacy and current administrator records. Browser tests use fake device/user data with an innocuous event-handler marker and verify no code execution or injected DOM attributes. All runtime tests are local and do not contact production services.

**Deployment checks still recommended:** GitHub CodeQL/dependency advisory scan, database-backed integration and migration, Docker build, HTTPS reverse-proxy security headers, session/CSRF/origin checks, and live controller/RTSP access verification. A 503 during a DB outage is now expected and safer than returning data anonymously.

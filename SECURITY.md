# Security — v0.418

## v0.415 – Browser CSP and container isolation

The outermost FastAPI middleware adds an enforced Content-Security-Policy to successful, redirected and denied requests in both the modular and legacy entrypoints. Inline JavaScript is authorized only by SHA-256 hashes of **trusted in-repository source literals**, not from user-controlled response bodies; unknown inline scripts and event handler attributes are blocked. Same-origin frames, audio and camera preview data/blob image sources are supported. Inline CSS is still permitted for legacy UI compatibility, and this does not replace XSS-safe DOM handling. A trusted-script manifest must be regenerated and reviewed whenever an inline script changes. The Polling Errors page no longer interpolates tent query values into executable JavaScript.

HSTS is opt-in (`GT_HSTS_MAX_AGE=0` by default) and should ordinarily be applied on a validated public HTTPS reverse proxy. No implicit X-Forwarded-For trust has been added. Docker Compose removes API Linux capabilities, sets no-new-privileges and read-only rootfs with a dedicated /tmp tmpfs; the existing /data mount stays writable. Root UID, full read-only project mount, go2rtc and PostgreSQL privilege profiles remain as explicit compatibility follow-ups. See `docs/security-deployment.md`.

## v0.414 – Proxy-aware login protection and TOTP replay prevention

Login throttling now uses a pair of normalized account name and client address rather than global username and source-IP buckets. This prevents an attacker on a different client address from blocking unrelated accounts or the legitimate account through a shared proxy-IP bucket. If multiple users appear behind the same source address, account-specific lockout remains possible; use Traefik/CrowdSec request-level defenses as an additional layer. The counter is still process-local and resets on API restart; v0.414 does not claim persistent rate limiting.

The API container uses Uvicorn `--no-proxy-headers` and only reads `X-Forwarded-For` from an immediate peer explicitly listed in `GT_TRUSTED_PROXY_CIDRS`. Configure **only exact known reverse-proxy IPs/CIDRs**, never `0.0.0.0/0` or your whole Docker network, and ensure Traefik sanitizes forwarded headers. If the allowlist is empty, forwarded headers are ignored and the TCP peer is used; with an internal proxy this cannot distinguish the real clients. Unknown-account login attempts run one dummy Argon2 check to reduce timing differences.

TOTP login, administrator step-up and enrollment consume a matched time step in `app_totp_replay` using an atomic PostgreSQL conflict update. A matched code cannot be reused even after a restart or by another API worker; the seed fingerprint permits new TOTP secrets to start their own counter. When entering a step-up confirmation immediately after a 2FA login, wait for the next 30-second authenticator code. Recovery codes remain single-use as before. Losing PostgreSQL access causes TOTP validation to fail closed with HTTP 503. The replay table is security state and must not be disabled for login availability.

## v0.413 – Field-level encryption and encrypted configuration backups

All production deployments require a unique external `GT_DATA_ENCRYPTION_KEY` (Fernet key) before the application starts. `app_auth_config` stores encrypted TOTP seeds and Pushover/Gromate credentials, `app_admin_users` stores encrypted TOTP seeds, and `tents` stores encrypted RTSP URLs and Shelly/HMAC device credentials. An idempotent PostgreSQL transaction migrates legacy values on startup and rejects wrong keys. Password hashes and recovery-code hashes remain Argon2; these are not reversible secrets. Treat encryption keys as highly sensitive and store them separately from the database and configuration backups. Existing historical database dumps/replicas may still contain pre-migration plaintext and require separate protection.

Configuration export is now a Fernet-encrypted JSON envelope; the server does not offer plaintext backup downloads. The same key is needed to import the encrypted backup into another deployment. Legacy plaintext backup imports remain temporarily supported after fresh admin confirmation, so treat legacy files as sensitive. The API decrypts values in memory for authenticated administrator Setup responses, RTSP camera streaming and device action clients; encryption at rest does not replace TLS, role controls, process isolation or outbound access restrictions. **Do not downgrade** to v0.412 with a migrated database; restore a pre-migration DB snapshot if a rollback is unavoidable. Losing the encryption key means losing those encrypted values irreversibly.

## v0.412 – Preview and schedule availability hotfix

This release restores a missing standard-library URL-encoding import in the authenticated camera preview path and adds the read-only light-schedule route to the modular production router. Existing login, admin step-up, guest read-only, source-URL validation and go2rtc isolation are unchanged. A router-level ASGI test guards both cases. No camera credentials are returned to guests and no additional write endpoint is added.

## v0.411 – Step-up protection

All administrator operations continue to require an active authenticated session. Sensitive auth/account/2FA and configuration-backup routes additionally require proof of the same administrator's current password and, if enabled, a valid TOTP. Proofs are stored in the in-memory session only, are capped at 300 seconds, and are bound to password/2FA state. The middleware and modular route dependencies both enforce this requirement. A 428 status indicates a required confirmation; the browser never sends passwords or TOTP in query strings. Five failed confirmations lock that session for 15 minutes. A session revoked during a password/2FA update is not recreated by the sliding-expiry refresh at the end of the request.

The TOTP QR endpoint accepts an opaque, short-lived enrollment token bound to the original admin session and builds the secret-bearing URI only on the server. Existing TOTP secrets are no longer returned in GET `/config/auth`. Pending enrollments expire after 10 minutes; completing setup requires the same session and a fresh step-up proof. Never expose the secret in URLs. This update does **not** encrypt secrets stored in PostgreSQL or config backups; those require a subsequent migration and key-management plan. HSTS/CSP and trusted-proxy login rate limiting also remain follow-ups.

The v0.410 change repairs **test isolation only**, ensuring GitHub Actions uses the installed PostgreSQL driver for the real irrigation integration tests. No application security policy changed; the open hardening findings from v0.409 remain.

Irrigation configuration and manual full-cycle requests use the existing per-tent backend HMAC configuration. The client signs exact serialized bytes and verifies response HMAC, timestamp, request nonce, method/path and HTTP status before trusting success. No unsigned legacy fallback exists. HMAC authenticates and protects integrity; the HTTP LAN channel is not encrypted.

Only authenticated administrator sessions may change plans or request manual cycles. Anonymous access is not allowed, and authenticated guest sessions remain read-only. A displayed expected revision fences stale plan edits. The ESP retains physical authority and validates clock, Drying, pump/volume settings, Flood, overlap, storage and event capacity.

Manual commands are persisted before transport. Retries retain command_id and expiry with fresh authentication nonces. After an authenticated acceptance, a failed status read is uncertain and cannot justify a replacement identity. Firmware durably claims IDs before execution, retains unexpired claims and rejects unknown expired commands. Backend PostgreSQL advisory locks serialize per-controller UI and poll operations across workers.

Events and notification intent commit atomically before ACK. Unique controller/stream/sequence keys deduplicate ingestion. The outbox retries provider failures independently after ACK. Provider delivery is at-least-once; a crash between provider acceptance and committing delivery can duplicate a push, but cannot trigger watering. Secrets/signatures are never included in event records, API views or new error logs.

Keep the ESP dashboard and PostgreSQL on trusted networks. Protect database backups, which retain the pre-existing HMAC configuration. Configuration-only exports do not preserve the event/notification journal. Firmware power-loss/interlock and real-device integration checks remain open; see TESTING.md.

## v0.356 diagnostics

Known unsigned controller rejection codes may be displayed only as explicitly unverified diagnostics. They never authenticate a success or authorize a legacy fallback. An ambiguous POST retains its command identity. Event/ACK errors do not revoke an independently signed plan confirmation; writes still require a fresh signed read and matching revision. Old or genuinely failed plan snapshots remain read-only.

## v0.358 target tile editors

New tile controls are rendered only for administrator sessions and use the existing protected Grow Profile page and PATCH endpoint. Existing source-IP/HMAC/time/nonce checks and confirmation logic remain authoritative. Editor sections are allowlisted; scope limits client payloads but is not a new authorization boundary. No controller secrets enter HTML or browser requests. Guest/offline/unconfigured visibility and scoped payload isolation are regression tested with synthetic fixtures.

## v0.359 labels

Only the visible target-button labels change; specific dialog names, permission/readiness gates, scoped payloads and authenticated write paths remain unchanged.

## v0.360 modal readiness

Dialog size/readiness messages still require the expected same origin and iframe source and now also match the active navigation view identifier. This identifier prevents stale UI updates and is not an authentication credential. Administrator and HMAC write enforcement are unchanged. Loading can be dismissed, and load failures do not authorize writes.

## v0.361 native target dialogs

Target forms use the same administrator-protected profile API and backend/HMAC write service. Cached numeric values are bound to a tent and taken only from its actual latest payload, not another tent’s fallback. Submission rechecks readiness/tent identity; stale responses cannot modify a new dialog. Only verified responses with the requested numeric value are displayed as successful. No secrets or arbitrary HTML are added to the dialog. Unknown values remain unknown until a protected read succeeds.

## v0.362 VPD precision

Client VPD editing uses hundredths within the existing allowed range. Formatting alone does not create a pending write, invalid third-decimal drafts are not silently submitted, and payloads remain numeric through the existing protected/HMAC path. No access boundaries or endpoints change.

## v0.363 native phase/date dialog

Moving Adjust into the Grow Phase tile and replacing its iframe does not change authorization. The native dialog is rendered only for administrator sessions and requires configured writes plus an online/OK controller. It sends only modified phase/date fields through the existing protected endpoint. Existing dates require explicit Delete; deletion sends JSON null. Success requires verified controller state matching every requested change. Failed reads, unverified responses and stale/tent-switched dialogs cannot enable or confirm writes. No HMAC secrets are sent to the browser.

## v0.364 ESP VPD channel integrity

Only the ESP current VPD channel supplies live/control/history VPD. Missing, nonfinite, boolean, negative and explicitly invalid/stale climate inputs cannot be replaced by a calculation, raw channel or cached prior VPD. Existing backend exhaust control performs no network action without a valid control VPD. New normalization copies payloads and preserves stored history; it does not establish cryptographic measurement provenance. No authentication/HMAC, firmware, target or hysteresis change is introduced.

## v0.365 chart presentation

Climate axis suggestions only affect presentation. Data, exports, control decisions and authentication are unchanged; larger excursions remain visible.

## v0.366 chart preferences

Chart ranges are non-sensitive browser-local presentation settings. Stored JSON is type/range validated, never inserted as HTML and cannot alter controller configuration or measured data. No new write API or authorization behavior is introduced.

## v0.367 history target fields

JSON history projections add only the recorded climate targets, normalized to finite numbers or null. No secrets, extra controller requests or new authorization paths are introduced. Stored measurements and settings are not modified.

## v0.368 analysis download

The new read-only analysis export follows existing dashboard history authentication. It accepts only fixed 1–48h ranges, uses bound SQL parameters, emits a fixed metric/target allowlist and never includes stored payloads, IPs, tokens or HMAC secrets. Attachment filenames use numeric tent IDs and a server timestamp. Responses are no-store and bounded to 1,000,000 bytes by adapting window sizes. No writes or ESP requests are performed.

## v0.369 export wording

Only the explanatory dialog text changes. The backend still downloads a file locally and does not send data to ChatGPT or any other AI service. Existing export access and file-content safeguards remain unchanged.

## v0.370 VPD reference view

The table is a read-only browser projection of existing authorized latest-state responses. It adds no data/write endpoint, network poll or control decision. Only numeric allowlisted fields are read; table content uses DOM textContent. Invalid/stale timestamps and climate flags remove the live marker. Calculated cells cannot overwrite the central ESP regulation VPD.

## v0.371 VPD tile layout

Only action placement changes. Existing read-only table behavior and administrator/readiness restrictions for target edits are unchanged.

## v0.372 phase-aware references

Phase/week references and stage split preferences are display-only. Phase data comes from the current authorized ESP snapshot; unknown/stale data selects no phase band. Per-tent localStorage values are integer/range validated and are not controller settings. No target writes, phase changes or new network endpoints are introduced.

## v0.373 table colours

Only reference-table colour classification changes. Controller readings, authorization, HMAC writes and physical control remain unchanged.

## v0.374 hint text

German display copy only; security and controller behaviour are unchanged.

## v0.375 VPD tile assessment

The tile reuses the read-only phase/week reference with compact inline DE/EN text. Stale data and drying do not claim an in-range value. ESP regulation and write security remain unchanged. Browser coverage checks closed-dialog updates and stale expiry.

## v0.376 guest VPD table

Guest table open/close and browser-local week mapping controls are exempt from guest pointer blocking, matching the existing JavaScript allowlist. Controller write restrictions remain unchanged. Browser regressions cover guest table access and blocked VPD target editing.

## v0.377 display-only VPD table

The current table labels the central measurement IST-VPD (Actual VPD), has no week-mapping controls or persistence, and ignores previous browser overrides. It retains phase/week reference highlighting with the default week-3 boundary and no extended-phase suffix. Guest access and ESP control remain unchanged. Earlier week-configuration sections describe historical versions only.

## v0.378

Dashboard VPD band coloring is display-only and adds no endpoints, writes or permissions.

## v0.379 dashboard VPD text color

Presentation-only correction; authentication, permissions and controller writes are unchanged.

## v0.380 night phase

Night assessment and humidity notice are browser-only displays. No writes, new endpoints, permissions or push notifications are introduced.

## v0.381 table range and Fahrenheit

Only reference table range and displayed temperature units change. ESP values, calculation units, permissions and controller writes are unchanged.

## v0.382 Fahrenheit temperature target dialog

Fahrenheit is converted to canonical Celsius before the existing protected PATCH. Existing administrator/readiness gates and verified Celsius response checks remain authoritative.

## v0.383 nighttime table heading

Only read-only reference heading presentation changes. No controller writes, access checks or measurement sources change.

## v0.384 backend PM1 live metrics

PM1 ON represents its permanently connected output. Heatmat remains monitoring-only and directly identified meters have no toggle UI. No source payload/history is rewritten.

## v0.385 analysis export device/context coverage

The read-only export projects only allowlisted stored ESP fields. It adds no live calls or controller writes, does not include IP-bearing device lines, credentials or tokens, and never backfills history from current settings/direct readings.

## v0.386 Shelly history gaps

Presentation-only correction. No history rows are rewritten, controller commands issued or permissions changed.

## v0.387 desktop Shelly layout

Presentation-only CSS and schedule markup change. Device data, authorization, control endpoints, guest restrictions, and controller logic remain unchanged.

## v0.388 humidity history average

Read-only dashboard calculation on the already displayed humidity series. No new endpoints, permissions, stored data, controller writes or sensor processing changes.

## v0.389 VPD dashboard tile status

Read-only label and CSS change. Existing reference limits, controller data, access checks and write endpoints remain unchanged. Night humidity information remains in the tooltip and reference table.

## v0.390 critical VPD status

Read-only dashboard text and CSS change using the existing outer reference band. No control requests, persisted data, permissions, alert delivery, or reference table changes.

## v0.391 strain flowering time

The optional category uses a fixed server-side allowlist (short/medium/long, or empty), canonicalized from supported German/English aliases. Existing admin write checks and parameterized SQL remain in place. CSV and configuration backup imports validate the category before writes. UI strings are rendered as text, and no controller commands or credentials are added. Configuration backups retain their existing sensitivity and restore semantics.

## v0.392 compact dashboard plant information

The read-only popover renders strain data using textContent, never HTML interpolation. Existing strain endpoint access and administrator write checks are unchanged. The guest button exception covers only the local close control. No schema, controller commands, credentials or import/export changes.

## v0.393 analysis export additions

The existing read-only authorized analysis endpoint queries the per-tent ESP journal with bound parameters and a bounded occurrence/receipt interval. Only allowlisted event fields, export-local run references, historical irrigation configuration and user-configured DS18B20 names/temperature aggregates are exported; controller URLs, stream IDs, command IDs, raw event payloads and credentials are not included. Sensor names are user-defined data. No control writes, live ESP calls or schema migrations are introduced. Unknown actual quantities or event times are not fabricated. If aggregation cannot fit the existing 1 MB limit, HTTP 413 prevents an endless retry loop or silent loss of journal events.

## v0.394 exhaust power analysis export

The existing authorized, read-only export accepts two additional allowlisted historical power keys and mirrors the exhaust aggregate in the climate metric set. No raw payloads, secrets, device addresses, live requests or writes are added. Existing freshness checks, selected-tent scope and size guard remain unchanged.

## v0.395 historical grow phase export

The read-only projection adds fixed phase codes, localized labels, validated integer weeks and fixed reference limits derived from the existing historical ESP settings. No new query, identifier, secret, user-supplied label, current status lookup or write operation is introduced. Mixed buckets retain counts without inventing phase assignments. Existing authentication, range validation and size limit are unchanged.

## v0.396 Setup layout

Only HTML grouping, presentation CSS, localization and opening the existing editor on Edit were changed; no authorization rules, persistence handlers, HMAC signatures, secret storage, backend routes or irrigation interlocks were altered. No credentials or tokens are sent to a new service. Tent details follow the existing administrator-only Setup access policy; a collapsed client-side panel is a visual affordance, not a security boundary. All interactions still require existing backend authorization checks.

## v0.397 compact Setup grid

CSS layout and existing semantic section wrappers only. No authentication, HMAC, backend API, backup, permissions, credential transport or ESP control paths change. All fields retain their identifiers and existing role checks.

## v0.398 cancel tentative tent edits

Cancel performs local form reset only, including passwords, HMAC secret text and the HMAC secret removal flag. It issues no network request, cannot disable HMAC on the backend and does not change stored configuration. Existing permissions and secured write APIs remain unchanged.


## v0.399 read-only bilingual Grow-Guide

The guide does not issue controller requests, ESP commands or backend writes. The original German Markdown and corresponding English source are pre-rendered to escaped, static HTML during development; no runtime Markdown engine or third-party script is loaded. External reference links use `rel="noopener noreferrer"`. Language and theme use existing local preferences only. The VPD values in the guide are documentation and cannot modify controller targets or historical data.

## v0.400 read-only GrowGuide wording

Documentation wording in the existing static guide only. No new inputs, network calls, permissions, stored settings or backend API behavior.

## v0.401 analysis ZIP with camera image

New read-only `/api/export/analysis.zip` uses the same session middleware and existing data read access as `/api/export/analysis`; it does not grant new write permissions. It fetches one JPEG from the configured internal go2rtc endpoint using the selected tent's existing RTSP reference, not an arbitrary client-supplied URL. Disable redirects, cap downloaded bytes at 32 MB, require JPEG content-type and byte markers, and use short timeouts. Camera failures never block the historical JSON download and cannot introduce a second streaming or authentication flow. Archive metadata excludes RTSP URLs, credentials and environment secrets. The ZIP can contain a real camera image of the grow tent: protect it like other private exports and check before sharing externally. Neither the image nor a copy of the archive is persisted to disk or the history database by this feature.

## v0.402 HDR-style camera export

The second JPEG is derived **only** from the already-authorized single live camera frame; there is no second RTSP call, user-controlled camera URL or external service. HDR processing is read-only, in-memory and bounded (16 MP for HDR processing; 20 MB for each JPEG); failures return the original image plus a bilingual note, without blocking historical JSON. Output remains a sensitive visual export requiring the same access controls as before. The camera fetch cap remains 32 MB, with a separate 20 MB cap for each saved JPEG.

## v0.402 fullscreen camera HDR option

The HDR preview is opt-in and read-only, using the same authorized per-tent JPEG and in-memory tone-mapping helper as the analysis ZIP. `hdr=1` is a boolean query flag, not an arbitrary URL; the response must be JPEG, is capped by the existing 32 MB input limit and limited to supported pixel dimensions. A processing failure returns 502 (never mislabeled as HDR) and leaves the normal JPEG preview unchanged. No new camera/RTSP credentials, data persistence, ESP control commands or public endpoints are introduced. The fullscreen HDR viewer requests a new frame no more frequently than every five seconds, and guards against stale responses when switching image modes.

## v0.403 adaptive camera enhancement

- The strengthened HDR appearance uses existing local frame bytes only; no new HTTP input surface, storage path, camera control or credential handling. Existing bounds on pixels, bytes, retries and image type remain in force.

## v0.404 per-tent strain export

The analysis export includes only the selected tent's public display name and its three saved strain-name labels, not the entire tent configuration. It remains covered by existing history export access restrictions. The SQL query uses the numeric bound tent ID; the export adds no input-controlled SQL, new endpoint or controller write. Credentials, controller URLs, HMAC secrets and all other tent settings are still excluded. The assignment reflects the current backend state and must not be mistaken for verified historical information.

## v0.405 camera marker persistence

- `GET /tents/{id}/camera-positions` returns only numbered positions and assigned strain names, not RTSP URLs, credentials, HMAC secrets, or private controller settings. Guest sessions can read the overlay, but `PUT` requires a real administrator session checked in both modular and legacy endpoints. Reject unknown pot keys, nonfinite values and out-of-range coordinates; the database update is restricted to `pot_positions_json` for a single tent ID.
- Saved data describes only **current** camera positions. Backups include positions so restoring or moving a tent retains the manual mapping; re-calibration is needed if camera placement changes. No camera photos, RTSP credentials or new recordings are stored in PostgreSQL.
- `camera-marked.jpg` is rendered in memory from the same bounded single RTSP frame used for `camera.jpg` and HDR. Only numbered circles 1–3 are drawn into this optional image; no strain names appear in the image. Assignments remain in the companion JSON. If annotation fails, the original and historic measurements remain available. The existing 1 MB JSON bound and camera JPEG/processing limits remain in force.

## v0.407 numeric-only camera markers

The camera viewer places position-edit controls in a separate row outside the image while retaining administrator-only backend authorization. Only pot numbers appear in `camera-marked.jpg`; names remain in the existing, authorized analysis JSON and are never rendered as pixels. The change adds no routes, credentials, database columns, device actions or RTSP requests.

## v0.408 — Fail-closed auth and XSS fixes

**Critical trust boundary:** PostgreSQL/auth configuration failure MUST NOT mean authentication is disabled. `load_auth_config` rejects a missing configuration row and `auth_middleware` returns HTTP 503 instead of falling back to anonymous read access; `require_admin` verifies that auth configuration was loaded and independently requires a valid admin session for sensitive operations. The former anonymous read-only setting is abolished: a valid session is required regardless of a legacy `enabled=false` database value. A DB outage can temporarily make the application unavailable; availability is intentionally sacrificed to protect confidentiality. All app routes, including `/health`, require an authenticated session. Only login/favicon and the first-installation bootstrap remain unauthenticated. Setup now reports login as mandatory and the configuration API rejects `enabled=false`. On startup legacy `enabled=false` rows migrate to TRUE without changing users/password hashes. The `manage_auth.py` recovery tool refuses `--disable-auth`; configuration backups cannot restore the anonymous mode, and a backup containing no usable admin is rejected. Public first-time installation is denied when an administrator exists in the separate admin-user table even if the legacy password mirror is empty.

**HTML/DOM boundary:** Never interpolate untrusted text or attribute values directly into `innerHTML`/template strings. Escape names, RTSP/controller URLs, Shelly IP addresses/schedule payloads, guest fields, dashboard navigation labels and 2FA QR/recovery values with the local contextual HTML escape helper. The only rich HTML in the affected templates is authored static markup. Use `textContent` when practical for future UI changes.

**Residual risk:** These targeted fixes are not a penetration-test certificate. Run authenticated network checks, dependency audits, browser security-header/CSP review, CSRF/origin checks on all write routes and PostgreSQL integration tests before declaring a comprehensive security sign-off. Existing SameSite cookies, admin write checks and ESP HMAC do not replace those checks.

## v0.409 device URL and guest data boundaries

Guest read-only access must not include stored RTSP usernames/passwords, raw go2rtc external links, or backend HMAC configuration. Admins may still edit camera configuration. Controller HTTP(S) and RTSP(S) URLs are checked against scheme and private-address restrictions when configured and before outbound use, including backup restores, but DNS answers can change after validation: production egress firewalling is still required. Proxy requests must not follow redirects or echo upstream responses/target URLs. Write routes in the modular tent API require explicit admin sessions.

This release is a targeted hardening pass, **not a comprehensive remediation**. Reauthentication, TOTP enrollment link handling and replay protection, encrypted backup/at-rest secrets, CSP/HSTS, abuse-resistant rate limiting, least privilege in Docker and exact dependency pins are still security follow-ups. Do not publish go2rtc ports directly. Prefer pinned image digests and restrict the API host network to authorized LAN devices.

## v0.416: minimal runtime mounts and optional non-root API

The standard API Docker Compose mounts only `./data:/data`, never the full host checkout or `.env`; application changelog is included in the image. The API still defaults to UID 0 with all Linux capabilities dropped, read-only root filesystem and `no-new-privileges`, to avoid changing permissions of existing host data. After confirming write access to `./data`, set `GT_API_RUN_AS=10001:10001` (or another dedicated UID:GID) for opt-in non-root execution. A deployment must inspect file permissions before enabling this mode; this release does **not** silently migrate filesystem ownership.

The optional project ZIP feature is disabled by default and needs a separately provisioned secret-free read-only `/project` mount to work; an absent mount gives 503 rather than an empty archive. The ZIP writer skips symlinks, private-key extensions, and case-variant `.env` filenames. This does not turn the source archive route into a general-purpose backup: never mount arbitrary host paths as the ZIP source.

## v0.418 drying VPD safety

Drying is a phase-scoped target (default 0.90 kPa), not a weekly growth target. The automation remains disabled until a given tent is enabled with a valid HMAC controller connection. Drying is triggered only from a valid current ESP phase value (3), even without a week, with a canonical internal week=1 to prevent repeated weekly writes. No changes are made to phase, irrigation or other ESP state. Extending a vegetative or flowering phase beyond its configured weeks does not switch phase or force another write of the final target; the ESP reports the phase and controls transitions. Existing plans without a drying field are normalized with a backwards-compatible default rather than discarded.

## v0.417 optional VPD automation writes

- Automation is **disabled by default per tent**. Only administrators can view or change schedules, and enabling requires a configured HMAC-protected controller write API.
- Poller uses the live ESP phase/week (never tent database ID, stale archive data or a guessed calendar). Drying or missing/invalid phase/week cannot cause writes.
- Only the `targetVPD` field is sent through the existing verified HMAC writer and audit log; no bypass of signature, nonce, permitted source IP or firmware validation.
- PostgreSQL stores last attempt and last successful phase/week/target to avoid repeated and cross-worker writes. Conflicting attempts have a 30-minute retry cooldown. Manual overrides remain effective during the same completed phase/week.
- All imported backup plans are validated before destructive restore. Encrypted configuration backups contain the per-tent schedules; secrets remain outside that configuration and are not exposed by these routes.

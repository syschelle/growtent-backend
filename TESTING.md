# Testing — v0.418

## v0.418 — Drying VPD 0.90 kPa on phase entry

- `PYTHONPATH=api:tests python -m pytest -q tests/test_vpd_auto.py tests/test_vpd_auto_drying_v0418.py`: check enabled/disabled plans, legacy v0.417 plan migration, drying without week, per-tent 0.90 kPa target, no automatic phase switching, prolonged vegetative/flowering phases capped to their own final week without redundant writes, invalid input rejection and signed targetVPD-only writes.
- `PYTHONPATH=api:tests python -m pytest -q tests/test_vpd_auto_postgres.py`: verify durable one-time claims and isolation on an isolated PostgreSQL schema when `IRRIGATION_TEST_DATABASE_URL` is set.
- `PYTHONPATH=api:tests python tests/check_vpd_auto_browser.py`: DE/EN and 320 px UI, drying target editing, persistence and tent switching.
- `python scripts/generate_csp_hashes.py --check`: verify CSP hashes match the updated first-party Setup script.
- Perform the full unit, JavaScript and browser regression suites, then live ESP/DB checks before enabling the automation on a production tent.

Run `PYTHONPATH=api python -m pytest -q` after installing `api/requirements.txt` and pytest. Node.js is required for rendered-script checks. Tests use no real controllers or push recipients.

The irrigation suite checks exact raw-byte request signing, response signature/status/path/nonce/time binding, unsigned/tampered rejection, stale revisions, durable application confirmation, preserved historical dates, firmware capability checks, manual identities across ambiguous timeouts, no legacy start fallback, idempotent event ingestion, commit-before-ACK ordering, stale offline state and delayed/aborted notifications. Existing application tests remain required.

## v0.415 – CSP, browser and container safeguards

- `python scripts/generate_csp_hashes.py --check`: require the committed static CSP hash allowlist to match the audited source literals before testing/building. **Never hash rendered HTML** to expand the CSP allowlist.
- `PYTHONPATH=api:tests python -m pytest -q tests/test_csp_headers.py`: verify trusted inline scripts, per-parameter immutable Polling Errors JavaScript, no dynamic handler attributes, unauthorized inline scripts blocked, and headers also on JSON errors and redirects; optional HSTS gating.
- `PYTHONPATH=api:tests python tests/check_csp_browser.py`: enforce the script policy in Chromium using a local CSP meta tag (frame-ancestors cannot be tested with meta); known page scripts must execute and an injected script plus onerror handler must be blocked. The HTTP header itself is verified separately in the Python suite.
- `PYTHONPATH=api:tests python -m pytest -q tests/test_csp_modular_v0415.py`: test the actual deployed FastAPI router with login, unauthorized API and authenticated shell responses.
- Existing setup, XSS, step-up, Original/HDR, pot markers, GrowGuide, analysis export and five Node suites must still pass. PostgreSQL integration requires the isolated CI database.
- Compose YAML parse check is local; **full image build and container runtime read-only mount testing require Docker**. Verify /data permissions, fullscreen preview, Shelly, ESP, login/2FA and production Traefik HTTPS/HSTS after deployment. The default container UID remains root for migration compatibility.

## v0.414 login and TOTP hardening

- `PYTHONPATH=api:tests python -m pytest -q tests/test_login_totp_hardening_v0414.py`: reject untrusted/spoofed forwarding headers; trust explicitly configured proxy hops; isolate login lockouts to account/client pairs; verify dummy Argon2 path and TOTP time-window/replay behavior.
- `PYTHONPATH=api:tests python -m pytest -q tests/test_totp_replay_postgres_v0414.py`: on CI's isolated PostgreSQL instance, verify atomic replay rejection and persistence across connections. Requires `IRRIGATION_TEST_DATABASE_URL`; skipped otherwise.
- Check normal username/password login, TOTP login, second-use rejection, step-up after waiting for the next code, recovery codes, DE/EN UI and no regression to the existing camera and device routes.
- Deployment: confirm the *actual* Traefik source IP before setting `GT_TRUSTED_PROXY_CIDRS`; never trust all source addresses. Configure optional network edge rate limiting separately. The local in-memory credential limit is not shared across multiple API workers.

## v0.413 encrypted secret storage and backup validation

- `PYTHONPATH=api:tests python -m pytest -q tests/test_secret_vault_v0413.py`: field-level encryption/decryption and key mismatch, confidential round-trip backup, actual encrypted export, legacy import guard, wrong-key preflight, HMAC retrieval and real modular camera preview with encrypted RTSP URL.
- `PYTHONPATH=api:tests python -m pytest -q tests/test_secret_vault_postgres_v0413.py`: runs only with `IRRIGATION_TEST_DATABASE_URL`; verifies transactional updates and idempotency against real PostgreSQL in an isolated schema (no production database).
- Startup without `GT_DATA_ENCRYPTION_KEY` must fail; Docker Compose must refuse an unset key before launch. Verify runtime migration with a real **pre-upgrade test database snapshot** and the same key across restarts. Check 2FA login, Pushover, Shelly, HMAC/ESP, RTSP original/HDR and encrypted backup export/import on a test deployment.
- Confirm the key is not in `git`, PostgreSQL dumps, config backup envelopes or access logs. Secure and separately back up the key. Wrong-key recovery requires the correct original key, never a silent fallback.
- Full `pytest`, five Node test suites and DE/EN Chromium browser checks are required.

## v0.412 camera preview and Shelly schedule hotfix

- `PYTHONPATH=api:tests python -m pytest -q tests/test_camera_preview_modular_regression.py` calls the actual `main.app` modular router without a real camera, database or Shelly. It verifies normal JPEG and HDR responses at `/tents/3/preview`, a valid percent-encoded RTSP URL sent to go2rtc, authorization of anonymous callers (401), and `/tents/3/shelly/light/schedule?refresh=true` as an authenticated guest.
- This integration test specifically catches an absent `quote_plus` global which the previous isolated AST preview unit tests masked with an injected fake symbol; and missing router registrations which otherwise surfaced as HTTP 404.
- Run the entire pytest suite with a PostgreSQL test service in CI and the existing Node/Chromium suites; perform a real camera/Shelly smoke test after deployment.

## v0.411 step-up and 2FA enrollment verification

- `PYTHONPATH=api:tests python -m pytest -q tests/test_step_up_security.py`: 13 tests for per-session password/TOTP proof, 428 guard, five-failure lockout, proof revocation after credential changes, guest denial, QR token ownership and production modular ASGI routing.
- `PYTHONPATH=api:tests python tests/check_step_up_browser.py`: Chromium bilingual security confirmation including wrong password and retry, required TOTP, challenge replay and 320 px mobile layout. This runs in GitHub Actions browser job.
- `PYTHONPATH=api:tests python tests/check_security_xss_browser.py`, `python tests/check_setup_layout_browser.py`, `python tests/check_preview_hdr_browser.py` and `python tests/check_camera_pot_markers_browser.py`: confirm no regressions in adjacent interfaces. Other Node and Python suites must also pass.
- No live PostgreSQL, RTSP/go2rtc or Docker integration was available locally. CI provides an isolated PostgreSQL 17 service. An actual HTTPS Traefik deployment must verify session persistence, login and 2FA on the deployed hostname.

The v0.410 CI regression test (`tests/test_security_hardening.py::test_security_suite_preserves_installed_postgresql_driver`) verifies that the security unit tests never replace an installed psycopg2 module with a stub. When psycopg2 is missing, that test skips and lightweight unit tests use a fake driver; this is *not* a substitute for the real PostgreSQL integration tests. Run the entire suite in one process to catch import-order interference.

Set `IRRIGATION_TEST_DATABASE_URL` to an isolated PostgreSQL test database for transaction tests. Each test creates and drops its own random schema. CI provides PostgreSQL 17 and runs these tests without skips. Coverage includes idempotent migrations, preserved legacy snapshots, atomic event/outbox commit and rollback, push retry state, cross-worker advisory locks, command persistence and expired/aborted reconciliation.

Firmware policy/editor/layout/parser tests and full board builds run in the companion GrowTent/GrowTent-S3 PRs for v0.5.10.

## Open hardware/integration validation

- Install matching firmware and backend in the test system; verify HMAC credentials/source IP, NTP and wrong-key/timestamp/nonce failures.
- Verify initial explicit plan transfer, direct ESP edits followed by backend conflicts, and failed/offline saves without false success.
- Run one controlled manual and one scheduled cycle; verify Drying, disabled pumps, overlap, Flood and start/end/aborted/missed messages.
- Interrupt ESP/backend power around command persistence, GPIO start, ingestion commit and ACK; verify no repeated start.
- Simulate backend/push-provider outages, delayed event timestamps, buffer pressure and failed notification retry.
- Verify deployment and explicit rollback order. No hardware or live Pushover test is implied by CI.

## v0.355 display

UI label tests exercise the production formatter with future, stale, expired, disabled, Drying and missing/older-firmware data. Service tests verify signed next-run metadata is passed through without recomputation. Live-device display/timing checks remain open.

## v0.356 sync regression coverage

Tests reproduce an event error after a successful plan read, verify that editing remains revision-fenced, distinguish recent busy snapshots from old/failed caches, test unsigned diagnostic failures without authenticating them, and convert UTC 16:21 to Berlin 17:21 in winter. PostgreSQL tests verify event-error persistence without changing the last plan confirmation time. Production network/HMAC verification remains open.

## v0.358 target tile editors

Render tests verify admin-only controls/routes and allowlisted scoped redirects. The target-editor browser CI job renders actual dashboard/editor HTML with isolated network fixtures and executes production modal/editor JavaScript. It checks offline/guest/unconfigured gates, responsive tile placement, DE/EN dialogs, temperature/VPD step validation, hidden-field isolation, exact partial PATCH payloads, failure retention, focus restoration and phase/date separation. No real ESP is contacted. Existing HMAC/security/irrigation and PostgreSQL tests remain required. Device write validation remains open.

## v0.359 target button labels

The existing browser test executes the production label assignments and verifies both buttons read ändern/change in DE/EN while each modal title retains its specific temperature/VPD name. Existing target-editor, HMAC, security and PostgreSQL coverage remains required.

The v0.359 browser checks also require target-only dialogs to stay within 280 px on desktop/mobile without iframe overflow, preserve 1.17 kPa in the current VPD display and retain the larger phase/date dialog.

## v0.360 stable modal opening

The browser fixture delays profile reads and checks that the dialog card stays hidden until ready, its first visible geometry remains stable, loading can be cancelled, stale/unready size messages are ignored, and failed reads reveal an error. Existing scoped editor, permission/HMAC/security and PostgreSQL tests remain required. Fixtures never contact live ESPs.

## v0.361 native target forms

The browser regression now tests native dialog opening with no target iframe navigation or opening loader, cached values without extra reads, a stable single-read fallback for missing values, exact one-field verified PATCH, step limits, failed/unverified writes, two-decimal VPD, focus, Escape/Cancel, stale reads and tent changes. The existing phase/date iframe remains covered separately. All fixtures are synthetic; existing HMAC/security/PostgreSQL tests remain required. Live-device validation remains open.

## v0.362 VPD input precision

Browser checks require 0.01 steps, accepted hundredth writes, two-decimal current/input values after read/save/reopen and blur formatting without losing draft values. Third-decimal edits remain invalid; merely formatting a loaded value does not enable a write. Existing backend/HMAC/security/database tests remain required.

## v0.363 native phase/date dialog

The Adjust control sits beside the current phase. Browser checks cover native modal opening without an iframe or opening resize, desktop/mobile layout, German/English labels, exact phase/date-only PATCH payloads, explicit delete/undo, blank-date rejection, verified saves, failed/unverified reads/writes, cancellation/focus and tent-change guards. Existing temperature/VPD and guest/admin checks remain required. Local pytest: 194 passed, 6 PostgreSQL-only skips; CI runs with PostgreSQL 17. Browser checks use synthetic responses and do not contact controllers.

## v0.364 authoritative ESP VPD

Run `PYTHONPATH=api python -m pytest -q tests/test_vpd_source.py` and `node tests/test_vpd_ui.mjs`. Pure channel tests cover conflicts with backend-smoothed/raw/legacy values, exact precision/zero, null/empty/bool/nonfinite/negative values and explicit climate validity. Production function bodies are exercised through ingestion, latest, filtered/unfiltered histories, device history API and JSON export using a fake database. Cases retain timestamped gaps, preserve original payloads/rows, reject previous-sample/formula fallback, keep JSON-safe incomplete climate points and prevent exhaust network I/O for invalid VPD. A 50-sample synthetic regression protects against selecting the formerly recalculated backend channel.

Production JS helpers and the real chart-builder body execute with a Chart/DOM stub: strict ESP selection, null-safe numeric formatting, exact VPD series, gaps, valid-only average/min/max, true zero and latest-point legend. Existing full backend/PostgreSQL/native-dialog/browser and CodeQL checks remain required. No real controller, production database, Shelly or provider is contacted. Hardware comparison of ESP state versus live tile/history/export remains open. Historical JSON is never migrated or overwritten; legacy synthesized current values cannot be reconstructed automatically.

## Climate chart range (v0.365)

Production JavaScript chart tests verify suggested temperature bounds of target ±5 °C / ±9 °F, raw/current midpoint fallback without a target, humidity midpoint ±5 percentage points, physical humidity boundary suggestions, null-only histories and unchanged samples. Suggestions do not clip excursions; paired axes use the existing synchronization.

## Configurable chart ranges (v0.366)

The production JS chart test covers browser preferences, defaults, corrupt/invalid storage, custom ranges, automatic mode, Fahrenheit conversion and unchanged samples. `render_chart_settings.py` plus `test_chart_settings_browser.cjs` exercise actual Setup HTML/handlers: save/reload, zero, empty/out-of-range input, corrupt storage, quota errors and DE/EN responsive layout. CI includes PostgreSQL and existing editor/browser/CodeQL checks. No ESP control or server settings are written by chart preferences.

## Historical target export (v0.367)

`tests/test_vpd_source.py` exercises the actual history function and both JSON projections with timestamp-specific target changes, missing targets, true zero, numeric strings, invalid/bool/nonfinite inputs and negative VPD targets. It verifies unchanged measurement values and database rows, SELECT-only access and JSON-safe nulls without latest/alias substitution. Existing Python/PostgreSQL/browser/CodeQL checks remain required. No firmware or database migration is involved.

## Compact analysis export (v0.368)

`test_analysis_export.py` exercises production aggregation and the download handler: 24h/8640 samples to 720 windows, extrema, valid counts, all ranges, empty windows, gaps, unknown/stale Shelly states, target changes, event-detail limits with full observed counts, nonfinite input, time boundaries, attachment headers, bounded SELECT-only SQL, unsupported periods and unknown tents. A busy-day fixture verifies the 1,000,000-byte guard and preserved sample counts/extrema. `render_analysis_export.py` and `test_analysis_export_browser.cjs` verify the actual button/dialog, default/48h selection, JSON attachment download, failed response recovery, cancel/Escape and DE/EN desktop/mobile layout. Existing Python/PostgreSQL/chart/browser/CodeQL checks remain required. No live controller calls are made.

## Export explanation (v0.369)

The existing production export browser test now checks the concise German AI/ChatGPT purpose hint after changing the period. Existing DE/EN dialog/download checks remain in place. Export aggregation, file bounds and backend recording are unchanged.

## Live VPD table (v0.370)

`node tests/test_vpd_table.mjs` verifies the production reference formula, independent expected value, leaf offset, central channel ownership, stale/null/freshness flags, range bounds and existing-poll hooks. `render_vpd_table.py` plus `test_vpd_table_browser.cjs` exercise actual production assets: 525 cells, exact ESP summary, offset-dependent reference without altering the control value, missing offset, stale expiration, tent races, out-of-range readings, initial marker centering, DE/EN, C/F, light/dark and desktop/mobile layouts, close/Escape and absence of additional polling/control requests. CI includes screenshots and existing Python/PostgreSQL/chart/editor/export/CodeQL checks. Physical plant-response validation is not required for this read-only reference view.

## Compact VPD actions (v0.371)

The production VPD browser test additionally verifies a shared action row at 1640/800/390px, compact button width, no overlap and a maximum 34px footer height. Existing table/dialog, target readiness and formula checks remain required.

## Phase-aware table (v0.372)

Production module tests cover the latest confirmed legend, default/custom early/late boundaries, extended phases without implicit phase transitions, phase-week-only selection, missing/invalid weeks, drying/stale values and validated per-tent browser settings. The production browser test exercises adaptive outlined cells and labels, extended vegetative week 7, actual flowering phase changes, missing weeks/drying, saved split changes, invalid input and zero extra network/control requests. Existing formula, current-marker, responsive, Python/PostgreSQL and CodeQL checks remain required.

## Current-only release notes

`python scripts/check_release_notes.py` requires exactly one root release-notes file matching the source version and title. Build/release CI invokes it; tag publishing also verifies tag/source agreement. This repository-only cleanup does not alter firmware or runtime behavior.

## v0.373 VPD colour boundaries

Run `node tests/test_vpd_table.mjs`. Regression coverage checks the reported 33 °C / 60% / −1.5 °C cell (displayed 1.60 kPa) and both sides of all rounded colour boundaries. Controller calculations remain unchanged.

## v0.374 hint text

Existing VPD table tests remain applicable; only the German explanatory sentence changes.

## v0.375 VPD tile assessment

The tile reuses the read-only phase/week reference with compact inline DE/EN text. Stale data and drying do not claim an in-range value. ESP regulation and write security remain unchanged. Browser coverage checks closed-dialog updates and stale expiry.

## v0.376 guest VPD table

Guest table open/close and browser-local week mapping controls are exempt from guest pointer blocking, matching the existing JavaScript allowlist. Controller write restrictions remain unchanged. Browser regressions cover guest table access and blocked VPD target editing.

## v0.377 display-only VPD table

The current table labels the central measurement IST-VPD (Actual VPD), has no week-mapping controls or persistence, and ignores previous browser overrides. It retains phase/week reference highlighting with the default week-3 boundary and no extended-phase suffix. Guest access and ESP control remain unchanged. Earlier week-configuration sections describe historical versions only.

## v0.378

Current VPD coloring reuses the reference table band function, including two-decimal boundaries and neutral missing/stale state.

## v0.379 dashboard VPD text color

Dashboard-specific CSS uses the shared band colors for text with a transparent background and original spacing. Reference table cell styling and band boundary tests remain applicable.

## v0.380 night phase

Node regressions cover switch-state priority, daily schedule fallback, midnight boundaries, invalid/stale schedules and five-minute humidity continuity/reset. VPD remains visible; nighttime table phase highlighting is suppressed.

Local v0.380 validation: VPD table/night-state/dashboard-render and VPD UI Node suites passed; release-notes check, Python syntax compilation and whitespace checks passed. Python pytest and browser fixture rendering could not run because pytest is not installed in this environment; visual browser validation remains open.

## v0.381 table range and Fahrenheit

Node regressions cover the 35 °C marker boundary and 68–95 °F conversion, including leaf-offset differences and null values. Browser assertions expect 16 rows/400 cells and converted Fahrenheit row headers/offset.

Local v0.381: VPD table and VPD UI Node suites, release-notes checker and whitespace checks passed. Browser assertions were updated but could not run because the Playwright Chromium executable is absent.

## v0.382 Fahrenheit temperature target dialog

Production JavaScript regression checks cover C/F specs, current/input conversion, supported target grid and canonical Celsius submission/confirmation. Browser validation remains open because Chromium is absent.

## v0.383 nighttime table heading

Chromium regressions verify DE/EN flowering week 6 reference headings remain visible at night, exactly one night label appears in the dialog, and daytime phase highlighting stays suppressed.

## v0.384 backend PM1 live metrics

Regression tests exercise Switch/PM1 parsing and the actual direct reader with mock HTTP, including 46.1 W / 40.7 Wh and real zero watts. Production dashboard rendering tests verify ON/green, live energy conversion and absent heatmat toggle.

## v0.385 analysis export device/context coverage

Run `PYTHONPATH=api python -m pytest -q tests/test_analysis_export.py tests/test_analysis_export_devices.py`. All 19 local cases passed: all seven Shelly roles, measured zero, stale/missing freshness, unknown state, gaps, transitions/detail caps, phase/schedule changes, privacy, source immutability and a full-day/all-devices 1 MB endpoint size regression. Existing export download browser tests remain required. See docs/analysis-export.md for the additive schema.

## v0.386 Shelly history gaps

The production history formatter is executed for all five power series with valid numbers, null/missing/empty/boolean readings and true zero. Production mappers must all use the null-safe helper. Existing full backend and browser suites remain required.

## v0.387 desktop Shelly layout

The browser regression uses actual dashboard CSS and Shelly rendering with synthetic devices. It checks one equal-width/equal-height desktop row at 1920, 1730, 1440, 1280 and 1100 px in German and English; grid-local scrolling only when required; 900 px tablet, 390 px mobile and forced mobile behavior; empty/dynamic device counts and preserved monitoring-only/controllable actions. Equivalent checks passed locally in Chromium via Python Playwright. The Node browser runner is wired into CI but was not executed locally (Node Playwright unavailable). No live controller or deployment test is implied.

## v0.388 humidity history average

The existing `node tests/test_vpd_ui.mjs` CI regression executes the production chart builder and legend generator for the humidity chart. It verifies the arithmetic mean of displayed smoothed samples (not raw readings), min/max, null/invalid gaps, true zero, all-missing samples, 100% humidity, one-decimal formatting, period rebuilds and the matching red/white dashed line. All five repository `.mjs` test suites passed locally. The 49 selected Python tests in `test_vpd_source.py`, `test_shelly_pm1.py` and `test_heatmat_shelly_integration.py` passed; Python compilation and release-note validation also passed. A real Chart.js browser render, full backend suite, Docker build and live deployment were not performed for this release.

## v0.389 VPD dashboard tile status

The production dashboard renderer regression checks German/English labels and state transitions for low, good (both inclusive phase limits), high, night, drying, unavailable and stale values; the sustained nighttime humidity notice remains in the tooltip. All five Node `.mjs` suites and 50 selected Python tests (`test_vpd_source.py`, `test_irrigation_ui_runtime.py`) passed locally. Python compilation and release-note validation passed. Local Chromium via Python Playwright with the rendered dashboard fixture verified both themes, DE/EN, desktop (1640 px) and mobile (390 px), computed text colors, no clipping, stale clearing and unchanged daytime/nighttime reference table assessment (400 cells). The equivalent color/status assertions were added to the existing CI Node browser test; that runner was not executed locally because Node Playwright is unavailable. Full backend suite, Docker build and live deployment remain open.

## v0.390 critical VPD dashboard status

The production renderer regression covers both outer pink bands across all four phase/week ranges, rounding boundaries, real zero, low/good/high transitions, German and English, night priority and neutral drying/unknown states. All five Node `.mjs` suites and 50 selected Python tests (`test_vpd_source.py`, `test_irrigation_ui_runtime.py`) passed locally; source compilation and release-note validation passed. Local Chromium via Python Playwright with static rendered dashboard fixtures verified both red text colors, both languages, 1640 px and 390 px, no clipping, night priority, stale clearing and the unchanged 400-cell reference table/pink color. The CI Node browser test was extended but not executed locally (Node Playwright unavailable). Full backend suite, Docker build and live deployment remain open.

## v0.391 strain flowering time

Regression tests cover optional category validation, canonical DE/EN aliases, invalid CSV and API values, legacy CSV compatibility, localized selector and dashboard labels, migration and update SQL presence. Local run: 262 Python tests passed excluding `tests/test_irrigation_postgres.py` (psycopg2 and a test database were not available); all five Node.js `.mjs` suites passed. Live PostgreSQL migration/backup restore, browser interaction, Docker build and live deployment are not verified by this run.

## v0.392 compact dashboard plant information

`python tests/check_strain_popover_browser.py --browser /usr/bin/chromium` exercises the production dashboard markup, styles and renderer with synthetic strain data. Local Chromium checks passed in German and English, light and dark themes, desktop (1600 px), mobile (390 and 320 px), and landscape (667 × 350 px). Checks cover viewport bounds, wrapping and scrolling, guest access, unchanged values and week ranges, missing category/strain, safe text rendering, refresh stability, Escape, outside click and close button. The browser runner is included in CI. Docker build and live deployment remain open.

Local regression: 262 Python tests passed (excluding PostgreSQL integration, unavailable dependency/test database), all five Node.js suites passed, Python compilation and release-note validation passed.

## v0.393 named temperatures and irrigation analysis export

`PYTHONPATH=api python -m pytest -q --ignore=tests/test_irrigation_postgres.py`: 267 passed (two existing FastAPI deprecation warnings). The five existing JavaScript `.mjs` suites passed. Added tests for renamed sensors, invalid/disconnected readings, local and original/delayed event times, per-tent range filtering, unknown timestamps, historical settings, missing/future/stale quantities and size-adapted journal preservation. A PostgreSQL integration test covers the actual journal query, but could not run locally (psycopg2 and test DB unavailable). Docker build, browser integration and live ESP validation were not run. No real irrigation was triggered.

## v0.394 exhaust power analysis export

The historical exhaust tests verify canonical and legacy field names, canonical precedence, genuine zero, stale/invalid freshness, nonfinite and boolean values, missing windows, alias equality and the attachment endpoint. The size-adaptation regression verifies that all exhaust sample counts and extrema remain available and both export paths agree. Local regression: 269 Python tests passed (`PYTHONPATH=api python -m pytest -q --ignore=tests/test_irrigation_postgres.py`, two existing FastAPI deprecation warnings); all five Node.js `.mjs` suites passed. Python compilation and the versioned release-note check passed. PostgreSQL integration, browser tests, Docker build and live deployment were not run.

## v0.395 historical grow phase in analysis export

The new tests compare the Python phase metadata with the production JavaScript `phaseRange` across phase/week boundaries and missing/invalid inputs, check both localized labels, mixed and empty windows, drying, latest observation timestamps and size-adapted counts. The 44 targeted analysis-export cases passed. Local regression: 287 Python tests passed (`PYTHONPATH=api python -m pytest -q --ignore=tests/test_irrigation_postgres.py`, two existing FastAPI deprecation warnings), all five Node.js `.mjs` suites passed, compilation and versioned release-note validation passed. PostgreSQL integration, browser tests, Docker build and live deployment were not run. No ESP commands were issued.

## v0.396 compact Setup UI

`python tests/check_setup_layout_browser.py --browser /usr/bin/chromium` renders the real Setup template in Chromium with synthetic HTTP/localStorage fixtures and no external requests. It validates the five sections and tent cards in DE/EN, light/dark themes and viewport widths from 320 to 1920 px, checks for horizontal overflow, verifies Edit opens the original form with the correct loaded values, checks unchanged PUT request fields, and checks that the irrigation modal remains accessible. `--screenshot-dir <path>` generates visual previews. The check is also included in the browser CI job. Existing Python and JavaScript regression tests continue to run; a live PostgreSQL, Docker and controller test is still required before production deployment.

Local v0.396 checks: 287 Python tests passed with PostgreSQL integration test module excluded (no isolated database in this environment); the five JavaScript suites passed. The compact Setup and existing plant popover browser checks passed using Chromium. The browser Setup test additionally verifies the expanded editor at 320 px and an unchanged mocked tent PUT payload. Source version/release-notes verification passed. Docker build, live controller operations and real PostgreSQL integration remain unverified.

## v0.397 responsive Setup columns

The Chromium Setup regression now asserts that Appearance/Access/Alerts occupy separate desktop columns at widths 1024–1920, that Backup sits underneath Appearance, tablet arrangement uses two columns, phones use one, and Tents remain below all overview columns. DE/EN and dark/light permutations continue to check overflow and remain read-only against mocked APIs. Original editing, irrigation plan modal and PUT payload checks are retained. Full backend and Docker live checks are not claimed until executed.

Local v0.397 checks: 287 Python tests passed (isolated PostgreSQL integration module excluded), all five JavaScript `.mjs` suites passed, Chromium Setup and existing plant popover browser checks passed; source version/release-notes validation passed. Live PostgreSQL, controller integration, Docker build and deployment have not been verified.

## v0.398 cancel tent editing

The Chromium Setup regression checks that Cancel/Abbrechen is translated, discards an unsaved edit (including URL, sensor IP, password, HMAC secret/clear flag, thresholds and toggles), closes the editor and restores Add tent mode without issuing any write request. Reopening the same tent loads the saved server mock, while the existing PUT/POST behavior and irrigation-plan controls remain available. It also checks canceling a new draft. Full backend tests, Docker build and real controller integration must be checked separately.


## v0.399 bilingual Grow-Guide

`python -m pytest -q tests/test_grow_guide_content.py` validates 20 chapters per language, required table and source links, local guide assets, the unchanged route, read-only behavior and existing language/theme storage keys.

`python tests/check_grow_guide_browser.py --browser /usr/bin/chromium` checks the actual static guide page with isolated browser fixtures in German and English, light/dark themes, 1440/768/390/320px widths, table scroll without page overflow, visible heading counts, language switching, chapter filtering, and collapsible navigation. It is added to the browser CI workflow. The browser makes no controller requests. The original German source was retained verbatim, with all 20 sections translated for English. Live Docker deployment remains unverified until executed.

## v0.400 autoflower note

Verify that the German and English Markdown sources and their pre-rendered HTML both show the concise age-based autoflower cutting note; keep all 20 chapters and ensure no controller/UI logic changes. Verify the current-only release notes tag.

## v0.401 camera snapshot analysis ZIP

`PYTHONPATH=api python -m pytest -q tests/test_analysis_archive.py tests/test_analysis_export.py` verifies the preserved legacy JSON endpoint, bounded native-resolution snapshot acquisition from go2rtc (JPEG-only, 32 MB input, 20 MB image, 9 s timeout), successful ZIP contents, safe missing-camera ZIP with DE/EN note, scrubbed metadata, unchanged historical climate records and read-only response headers. `python tests/render_analysis_export.py /tmp/analysis-export.json` plus `node tests/test_analysis_export_browser.cjs /tmp/analysis-export.json` checks the production download dialog and ZIP filename with a synthetic ZIP fixture; the optional Python Chromium smoke check is `PYTHONPATH=api:tests python tests/check_analysis_zip_browser.py --browser /usr/bin/chromium`. No actual camera/RTSP endpoint is contacted by these tests. Local result: 303 Python tests passed excluding the PostgreSQL-only integration test module, and Python Chromium smoke passed for DE/EN and mobile/desktop. The separate Node browser CI run, PostgreSQL integration, Docker build and live go2rtc validation remain open.

## v0.402 dual camera snapshot

`PYTHONPATH=api python -m pytest -q tests/test_analysis_archive.py` verifies the original JPEG stays byte-identical, a second HDR-style JPEG is generated from the same frame, the exported metadata records correct dimensions and the single-frame processing method, 4K quality and resolution, bounded resizing of oversized HDR frames, and the camera/HDR fallback cases. No new camera capture or RTSP service is used. Local results: 312 Python tests passed excluding `tests/test_irrigation_postgres.py`; five `.mjs` suites passed, and the Python Chromium ZIP export browser check passed for DE/EN on desktop/mobile. A separate Node browser check was blocked because the Node `playwright` package is not installed in the environment. Docker build, live camera and PostgreSQL integration remain outstanding.

## v0.402 fullscreen Original/HDR camera viewer

`PYTHONPATH=api pytest -q tests/test_preview_hdr.py` checks unchanged byte-for-byte normal preview, opt-in HDR output using the ZIP helper, invalid/failed image rejection, and real modular router/service propagation of `hdr=1` without importing a production database. `PYTHONPATH=api:tests python tests/check_preview_hdr_browser.py` uses Chromium with synthetic camera frames; it checks the Original/HDR controls (DE/EN), selected mode state, correct preview URL query parameters, switching at normal and 200% smart zoom, and visibility at 320 px. The test never contacts a real camera or controller. Local verification: 319 Python tests passed (excluding PostgreSQL-only integration), all five JavaScript suites passed, and export/fullscreen Chromium checks passed in DE/EN; run the normal regression suite and release-notes check as usual; Docker and live-camera operation remain to be verified.

## v0.403 adaptive camera HDR regression

- Test real exported frames for a visibly stronger result than v0.402 while ensuring an unchanged original image, bounded size, 4K retention, degenerate-frame resilience, and shared fullscreen/ZIP transformation.

## v0.404 pot strain metadata in analysis exports

Run `PYTHONPATH=api:tests python -m pytest -q tests/test_analysis_export.py tests/test_analysis_export_pot_strains.py tests/test_analysis_archive.py`. The tests confirm the selected tent's `pot_strains_json` is read with a bound tent ID, all three assigned names and blank slots are preserved in JSON and ZIP, historical points are not overwritten, and no unrelated config/credentials leak. The existing adaptive 1 MB JSON size guard is exercised. No live controller is queried.

## v0.405 camera pot markers

- `PYTHONPATH=api:tests pytest -q tests/test_camera_pot_positions.py` validates coordinate normalization, rejected out-of-bounds/NaN/extra fields, read scoping, administrator-only writes, same-frame annotated ZIP, unconfigured behavior and source backup/migration contracts.
- `PYTHONPATH=api:tests python tests/check_camera_pot_markers_browser.py` checks real Chromium drag, save/cancel, keyboard fine adjustment, mobile 320px, German/English, HDR switching, guest read-only rendering and no JS exceptions (with mocked cameras/API).
- `PYTHONPATH=api:tests python tests/check_preview_hdr_browser.py` confirms existing HDR/zoom compatibility.
- Existing Python and Node tests should also be run. PostgreSQL integration on a test schema, real RTSP cameras and Docker rebuild require deployment-specific verification.

## v0.407 compact, number-only camera pot markers

- `PYTHONPATH=api:tests pytest -q tests/test_camera_pot_positions.py tests/test_analysis_archive.py tests/test_analysis_export_pot_strains.py`: verify number-only annotated JPEG is invariant under strain-name changes, current names still exist in JSON, byte-identical original, preserved HDR, and no output for unplaced pots.
- `PYTHONPATH=api:tests python tests/check_camera_pot_markers_browser.py`: verify the only image-overlay control is Töpfe/Pots, the separate editor bar sits outside camera pixels, and drag, cancel, save, keyboard control, DE/EN, guest access, HDR and 320px remain operational.
- Run `PYTHONPATH=api python -m pytest -q --ignore=tests/test_irrigation_postgres.py` and all five `tests/*.mjs` suites; PostgreSQL test setup, Docker rebuild and real RTSP remain deployment checks.

## v0.408 security regressions

- `PYTHONPATH=api:tests pytest -q tests/test_security_hardening.py`: verify DB errors/malformed auth configuration fail closed (503), protected endpoints never execute and admin session enforcement remains effective. Legacy `enabled=false` now denies anonymous access, including GETs, camera frames, ZIP/JSON exports and `/health`. The API rejects attempts to disable auth; session-based guest/admin viewing still works.
- `PYTHONPATH=api:tests python tests/check_security_xss_browser.py`: actual Chromium with mocked API payloads tries to inject HTML/event handlers through Setup tent labels/details, guest accounts, navigation and dashboard Shelly IP/schedule/generation. No external devices, network requests, or live credentials are used. This check is now also part of the GitHub browser test job.
- `PYTHONPATH=api:tests python tests/check_setup_layout_browser.py`, `PYTHONPATH=api:tests python tests/check_camera_pot_markers_browser.py` and `PYTHONPATH=api:tests python tests/check_preview_hdr_browser.py`: verify Setup forms and responsive layout, marker editing and HDR/zoom after UI output escaping. The camera browser test was brought up to date with v0.407's unified toolbar and hover hint.
- `PYTHONPATH=api:tests pytest -q --ignore=tests/test_irrigation_postgres.py` and all five `node tests/*.mjs` suites: full regression coverage outside the optional PostgreSQL test database.
- `PYTHONPATH=api:tests python -m pytest -q --ignore=tests/test_db_integration.py --ignore=tests/test_irrigation_postgres.py`: regression run without PostgreSQL client/service; the mandatory-login tests cover 19 routes with legacy and current settings, HTML redirect, login/guest/admin distinctions, recovery-CLI denial, and bootstrap validation.
- Do not treat browser mocks as actual deployed authorization/traffic/RTSP testing; PostgreSQL integration and container rebuild still need verification.

## v0.409 security regression

- `PYTHONPATH=api:tests pytest -q --ignore=tests/test_irrigation_postgres.py`: legacy FastAPI/auth/VPD/ZIP/ESP tests and new device URL security tests, without real services.
- `PYTHONPATH=api:tests pytest -q tests/test_device_url_security.py`: verifies 25 guest confidentiality, scheme/IP/DNS restrictions, blocked dangerous go2rtc source registration, and safe upstream 302 handling.
- `PYTHONPATH=api:tests python tests/check_security_xss_browser.py`, `python tests/check_setup_layout_browser.py`, `PYTHONPATH=api:tests python tests/check_camera_pot_markers_browser.py`, `PYTHONPATH=api:tests python tests/check_preview_hdr_browser.py`: existing browser regressions.
- Network egress rules, go2rtc permissions, real LAN camera/ESP, PostgreSQL integration, and Traefik edge headers must be verified on a separate staging deployment. No live endpoints were contacted.

## v0.416: API Docker filesystem hardening

- `PYTHONPATH=api:tests python -m pytest -q tests/test_docker_hardening_v0416.py` verifies both Compose variants omit the full repo bind mount, keep `/data`, retain the hardening flags and expose an optional non-root user without changing defaults.
- The same tests check the image-bundled changelog fallback, enabled-project-download fail-closed behavior, symlink/secret filtering, and admin-only access.
- `docker compose -f docker-compose.images.yml config --quiet` and `docker compose -f docker-compose.yml config --quiet` should be run on the real Docker host with existing `.env`; here only YAML parsing and source-level tests are available when Docker is absent.
- Deployment smoke test: login and 2FA, camera/HDR/marked image, Shelly light schedule, backups, and writes to `./data`. Run `docker exec gt_api id` after explicit non-root opt-in and check filesystem ownership before changing `GT_API_RUN_AS`.

**v0.416 full regression (local):** 481 passed, 10 skipped due to no isolated PostgreSQL setup, four existing FastAPI deprecation warnings. All five Node suites and Chromium CSP, XSS, step-up, setup, HDR, pot markers, analysis ZIP and GrowGuide checks passed. Docker image build/non-root runtime not executed locally.

## v0.417 optional VPD automation by phase/week

- `PYTHONPATH=api:tests python -m pytest -q tests/test_vpd_auto.py` exercises validation, defaults, unknown/drying phases, weekly progressions, independent plans, retries and HMAC-only targetVPD writes.
- `PYTHONPATH=api:tests python -m pytest -q tests/test_vpd_auto_postgres.py` runs on the isolated PostgreSQL schema using `IRRIGATION_TEST_DATABASE_URL` in GitHub Actions: durable claim/success state, two independent tents, next-week transitions and reconfiguration. This is skipped when no test DB is available.
- `PYTHONPATH=api:tests python tests/check_vpd_auto_browser.py` checks real Chromium DE/EN, mobile at 320 px, editing, save/reopen and isolation between two tents without any real ESP requests.
- `python scripts/generate_csp_hashes.py --check` and `python scripts/check_release_notes.py --tag v0.417` validate script allowlist and release files. Existing browser and Python/Node regression suites remain required.
- No live ESP, HMAC network, PostgreSQL migration or Docker deployment has been exercised locally. Newly enabled plans should be reviewed for the actual plants before rollout.

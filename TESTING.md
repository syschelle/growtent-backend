# Testing — v0.397

Run `PYTHONPATH=api python -m pytest -q` after installing `api/requirements.txt` and pytest. Node.js is required for rendered-script checks. Tests use no real controllers or push recipients.

The irrigation suite checks exact raw-byte request signing, response signature/status/path/nonce/time binding, unsigned/tampered rejection, stale revisions, durable application confirmation, preserved historical dates, firmware capability checks, manual identities across ambiguous timeouts, no legacy start fallback, idempotent event ingestion, commit-before-ACK ordering, stale offline state and delayed/aborted notifications. Existing application tests remain required.

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

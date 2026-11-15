# Testing — v0.380

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

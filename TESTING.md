# Testing — v0.368

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

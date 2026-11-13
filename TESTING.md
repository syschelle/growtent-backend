# Testing — v0.355

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

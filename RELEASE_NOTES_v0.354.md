# v0.354 — ESP-owned irrigation with HMAC configuration and backend notifications

## Release summary

The ESP becomes the authoritative irrigation planner and executor. The backend remains the configuration UI, supports an explicitly requested manual full cycle, and sends notifications from signed, durable ESP events.

## Changes

- Disable backend automatic irrigation triggering and independent next-run forecasts. Never fall back to unsigned `/startWatering` when a controller is offline or incompatible.
- Read the ESP plan and history through HMAC, cache the last confirmed values, and show stale state when confirmation fails. Save using the displayed revision and confirm durable application before reporting success.
- Preserve the previous backend plan as a migration snapshot. Load it for review and explicitly save it to the ESP; never overwrite an ESP-owned plan just by opening a dialog. Review its historical date because older backend versions could seed it to today after edits.
- Keep the manual Start watering action with HMAC, expiring persistent command identities and ambiguous-retry handling. The same command cannot repeat a physical cycle.
- Persist ESP start/completed/aborted/missed events and notification intent atomically, deduplicate by controller/stream/sequence, then ACK only committed events.
- Deliver Pushover messages from a durable retrying outbox. Delayed events include the original ESP time and a retrospective label. Aborted runs are never announced as successful.
- Add a near-full ESP event-buffer warning. Event polling and cached UI reads are throttled to respect the firmware replay-window capacity.
- Add PostgreSQL transaction/locking tests, HMAC/timeout/revision tests and rendered-JavaScript checks.

## Upgrade sequence

1. Back up the existing database. Install GrowTent/GrowTent-S3 **v0.5.10** for the matching hardware first.
2. Confirm controller and backend use the same existing HMAC secret, allowed backend source IPv4 and valid clocks.
3. Update this backend to v0.354. Its independent irrigation scheduler is disabled immediately; it will not substitute for an unreachable ESP.
4. Open the irrigation-plan dialog. Review the ESP-owned settings. If the ESP has no versioned plan, load the previous backend snapshot, verify the last known date, and choose **Save plan**.
5. Verify confirmed plan/history, clock/Shelly status, a controlled manual cycle, event ingestion and Pushover start/end messages in the test system.

## Compatibility and limitations

Requires signed irrigation protocol v2 from firmware v0.5.10 or later. Existing database rows are migrated additively; HMAC credentials are retained and never returned. Date and pump/phase/flood interlocks remain ESP responsibilities. Local ESP edits win over stale backend forms through revision conflicts.

The ESP retains at most 64 unacknowledged events and blocks further managed cycles when full. The backend ACKs only after database commit, so push-provider downtime does not fill the ESP buffer once ingestion succeeds. External push delivery is at-least-once: a process crash after provider acceptance but before committing delivery can cause a duplicate notification; no exactly-once provider guarantee is claimed.

Hardware power interruption and real-device/backend/push integration remain to be verified. Application configuration exports do not include the complete event/notification journal; use a PostgreSQL backup for it. Rollback must explicitly disable the ESP plan and confirm it before any older backend scheduler is re-enabled.

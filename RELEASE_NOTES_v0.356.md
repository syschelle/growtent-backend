# v0.356 — correct irrigation sync status and local timestamps

## Changes

- Separate signed plan confirmation from event/ACK synchronization errors. A failed event transfer no longer falsely invalidates a freshly confirmed plan or disables its editor.
- Retain fresh revision-fenced snapshots during a busy background refresh. Actual signed reads and revision checks remain mandatory before writes.
- Retry disabled/unconfirmed plan dialogs safely; confirmed user edits are not overwritten by background refreshes.
- Show concrete error codes and event warnings. Known unsigned authentication rejections are explicitly labelled unverified diagnostics and never trusted as state or proof of POST failure.
- Render confirmation timestamps in Europe/Berlin instead of raw UTC ISO strings. In winter 16:21 UTC is 17:21 CET; no one-hour HMAC/clock correction is applied.
- Add an idempotent event_error_code database column while preserving existing plan/event data.

## Compatibility

Works with existing protocol-v2 firmware. Firmware v0.5.12 provides the signed next-run time; v0.5.13 additionally shows it locally on the ESP. Keys, pump behavior and the ESP's ownership of scheduling remain unchanged.

A genuinely unconfirmed/offline plan remains read-only until confirmation succeeds. Source-IP, key, clock and storage problems must still be corrected; the UI now exposes their diagnostics instead of masking them as a generic stale status. Production hardware and live HMAC/network validation remain open.

# GrowTent Backend v0.363

## Changes

- Move Adjust into the Grow Phase tile, directly beside the current phase.
- Open phase, flowering-start and drying-start editing in a compact native dashboard dialog, using the same pattern as temperature/VPD editing.
- Remove the previous iframe overlay, opening loader and height-message handling from the dashboard.
- Keep German/English labels, desktop/mobile layout, Escape/backdrop/Cancel dismissal and focus restoration.
- Preserve explicit date deletion/undo and phase/date-only partial writes. Show success only after verified controller confirmation.

## Compatibility

- Administrator, online/status and HMAC write requirements remain unchanged.
- Target-temperature/VPD dialogs and standalone Grow Profile links remain supported.
- No ESP firmware update or API change is required.

## Validation

Local backend tests: 194 passed, 6 PostgreSQL-only tests skipped. CI must pass the PostgreSQL suite, native-dialog browser regressions and CodeQL before merge. Browser checks cover stable sizing, phase-button placement, localization, partial writes, delete/undo, unverified/failing responses, cancellation and tent switching using synthetic responses only.

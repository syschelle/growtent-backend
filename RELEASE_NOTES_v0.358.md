# GrowTent Backend v0.358

## Changes

- Add administrator-only target-temperature and target-VPD buttons at the bottom right of their dashboard measurement tiles.
- Open a compact editor for the selected target only; keep grow phase and dates in the existing Adjust dialog.
- Reuse the authenticated Grow Profile API and existing HMAC write/confirmation path. Scoped editors send only fields belonging to their scope.
- Hide edit controls unless backend writes are configured and the ESP/status are available.
- Preserve single-save validation, failed-write feedback, focus restoration and dashboard/camera continuity.
- Support German/English labels and responsive desktop/mobile placement. Temperature editing retains the existing Celsius units and 0.5 °C steps; VPD retains 0.1 kPa steps.

## Compatibility

- No firmware update or new ESP endpoints are required.
- Existing unscoped Grow Profile deep links remain supported. Dashboard Adjust opens the phase/date editor explicitly.
- The target values continue to be read from the controller; no optimistic dashboard success is shown after an unconfirmed write.

## Validation

Render/access-control and existing Grow Profile regressions pass locally. Browser CI checks visibility/readiness, per-field PATCH isolation, validation, failed writes, focus and tile placement using synthetic controller responses. Existing HMAC/security/irrigation/PostgreSQL tests remain required. Real-device write validation remains open.

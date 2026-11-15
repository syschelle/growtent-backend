# GrowTent Backend v0.372

## Changes

- Highlight the current VPD reference range from the ESP grow phase and phase week.
- Use the confirmed classic legend: early vegetative 0.4–0.8 kPa; late vegetative / early flowering 0.8–1.2 kPa; late flowering 1.2–1.6 kPa.
- Default to early weeks 1–2 and late from week 3, with configurable per-tent boundaries stored in this browser.
- Longer phases retain their own range; no automatic phase transition occurs after five weeks.
- Show unavailable phase/week, stale data and drying without a selected reference range.

## Compatibility

Display only. Actual ESP phase and VPD targets, HMAC writes and controller regulation remain unchanged. Week boundaries are application settings, not week prescriptions from the source legend. No firmware update or database migration required. Automatic target adjustment is not included.

## Validation

Production module/browser checks cover boundaries, extended phases, phase switches, missing/drying/stale inputs, preference validation and no network/control writes. Existing backend/PostgreSQL/chart/table/CodeQL checks run in CI.

# GrowTent Backend v0.362

## Changes

- Use 0.01 kPa steps for VPD target editing, allowing values such as 1.17 and 1.18 directly.
- Keep two decimal places when opening, loading, committing or restoring the VPD input: 1.20 rather than 1.2.
- Format completed edits on blur/change without interfering with partial typing. Preserve invalid input for correction instead of silently rounding it into a valid value.
- Apply the same VPD precision to supported legacy Grow Profile links.
- Do not mark a display-formatting change as an unsaved controller change.

## Compatibility

- Keep the 0.50–3.50 kPa range, Celsius temperature behavior, exact one-field writes and administrator/HMAC safeguards.
- Payloads remain numeric JSON; trailing zeros are a UI formatting convention.
- No firmware update or API change is required.

## Validation

Browser checks cover 0.01 spinner steps, exact hundredth writes, two-decimal input/current display after save and reopen, blur formatting, rejected third-decimal edits and unchanged higher-precision snapshots. Existing backend, permission, cancellation, database and CodeQL checks remain required. No live controller is contacted by tests.

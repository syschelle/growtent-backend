# GrowTent Backend v0.352

## Narrower Grow Profile dialog

This maintenance release reduces the width of the Grow Profile dialog while keeping the compact desktop layout introduced in v0.351.

### UI

- Reduced the dialog's maximum desktop width from 720 px to 560 px (approximately 22% narrower).
- Kept labels/current values and inputs/actions next to one another on desktop. The embedded editor now switches to stacked rows only below 530 px, avoiding unintended desktop wrapping when the dialog is narrower.
- On phones, the dialog still uses the available viewport width and keeps the Send and Delete controls touch-friendly and accessible.
- Preserved responsive height, vertical scrolling, and all existing modal close behavior.

### Unchanged

- GrowTent HMAC-SHA256 integration, stored/runtime verification, administrator-only access, and five-field partial updates.
- Temperature steps of 0.5 °C, VPD steps of 0.1 kPa, and explicit JSON null for date deletion.
- No database or firmware changes required.

### Testing

- Regression tests for modal width, responsive breakpoint, and existing controls.
- Full automated backend test suite and rendered JavaScript syntax checks.

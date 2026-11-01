# GrowTent Backend v0.345

## Mobile hint viewport fix

This maintenance release fixes dashboard information popovers on narrow mobile screens.

### Changed

- Keeps the HMAC information hint fully inside the visible mobile viewport.
- Applies the same viewport-safe positioning to the shared Temperature, VPD and other dashboard information hints.
- Popovers are limited to the available screen width and wrap long text safely.
- When there is not enough room below the hint icon, the popover automatically opens above it.
- Desktop behavior remains unchanged.

### Tests

- Added a regression test for viewport-safe information popover positioning.
- Full automated test suite: **102 passed**.

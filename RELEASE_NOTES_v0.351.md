# GrowTent Backend v0.351

## Compact Grow Profile modal

This release reduces the height and spacing of the Grow Profile editor while keeping it integrated with the CanopyOps dashboard.

### UI improvements

- Replaced the large stacked modal cards with dense, aligned settings rows on desktop.
- Labels, current values, inputs and their individual **Send** buttons remain easy to identify.
- Reduced paddings, control heights, and gaps without changing the validation logic.
- On narrow screens, values remain readable beside labels; inputs and actions use touch-friendly rows. Date actions wrap to a second row on very narrow screens.
- The dialog now adapts to the measured content height instead of occupying a fixed near-full-screen height, with viewport-limited scrolling when space is tight.
- The standalone Grow Profile deep-link page retains its previous layout.

### Unchanged

- Administrator-only rendering and write authorization.
- HMAC request signing, partial PATCH, post-write verification, error feedback, 0.5 °C / 0.1 kPa steps, and explicit JSON `null` date deletion.
- No database schema or firmware changes.

### Validation

- Full automated test suite: **137 passed** (two pre-existing FastAPI deprecation warnings).
- Dashboard and Grow Profile JavaScript syntax checks: **passed**.
- Static desktop/mobile layout review completed; live hardware/browser testing remains pending.

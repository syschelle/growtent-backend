# GrowTent Backend v0.338

## Grow Profile editor in the tent dashboard

This release moves operational Grow Profile editing from Setup into the dashboard of the selected tent.

### Changed
- Added an administrator-only **Edit grow profile / Grow-Profil bearbeiten** action to the Grow Phase card.
- Added a responsive inline editor directly below the dashboard top cards.
- The editor supports the five authenticated firmware write fields: target temperature, target VPD, current phase, flowering start and drying start.
- Opening the editor reloads the controller state through the existing read endpoints before changes are made.
- The outgoing partial JSON is shown before it is sent.
- Date deletion stays explicit: the Delete control sends JSON `null`; simply clearing an existing date field is rejected.
- Successful writes still require the controller to confirm the requested values in both `stored` and `runtime` state.
- The technical Backend Write API configuration (enable/disable, controller address and HMAC secret) remains in Setup. Operational Grow Profile changes are no longer offered from the Setup tent list.

### Mobile UI
- The editor automatically switches to a single-column layout on small screens.
- Action buttons become full-width touch targets in mobile and forced-mobile view.
- The inline editor stays inside the selected tent dashboard instead of opening a separate modal.

### Security
- Grow Profile writes remain administrator-only.
- The existing HMAC-SHA256 signing, nonce/timestamp replay protection, source-IP enforcement and post-write controller verification are unchanged.
- The HMAC secret remains write-only and is not exposed in the dashboard.

### Tests
- Added regression coverage for dashboard placement, mobile layout, administrator gating, explicit JSON `null` date deletion and Celsius-only controller values.
- Full automated test suite: **88 passed**.

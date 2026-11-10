# GrowTent Backend v0.350

## Grow Profile editor integrated into the dashboard

This release changes how administrators open the authenticated GrowTent Grow Profile editor. **Adjust / Anpassen** now opens a modal dialog over the selected tent's dashboard, using the same interaction pattern as the existing Irrigation Plan dialog, instead of navigating to a separate CanopyOps page.

### Dashboard and mobile UI

- The **Adjust / Anpassen** action stays inside the status tile and is displayed only when the ESP is online with `Status: OK`, the user is an administrator, and the Backend Write API is fully configured.
- Opens a responsive, scrollable **Grow Profile** modal with a close button; tapping the backdrop or pressing Escape also closes it.
- Maintains the current CanopyOps navigation, dashboard context, camera stream, and selected tent while the modal is open. The dashboard data refreshes after closing.
- Reuses the existing minimal editor: **current value → edit → Send** for each of the five supported fields. The former standalone-page header/back navigation is hidden inside the modal.
- The dialog fits narrow mobile viewports while preserving touch-friendly controls. Light/dark theme and DE/EN labels follow existing application preferences.
- Existing direct deep links to `/app?page=grow-profile&tent=...` remain supported for compatibility; the regular dashboard Adjust action no longer navigates to them.

### Security and controller behavior

- The button and the new modal markup are emitted only for authenticated administrator sessions. Guests cannot load the modal and the editor route remains administrator-only (`403`).
- The current HMAC-SHA256 signing, controller IP allowlist, nonce/timestamp protection, five-field partial PATCH contract, date deletion with explicit JSON `null`, and `stored`/`runtime` verification are unchanged.
- Target temperature remains in 0.5 °C increments and target VPD in 0.1 kPa increments.
- No database migration or firmware changes are required.

### Tests

- Added source-level and rendered HTML regression tests for modal layout, preserved irrigation modal, administrator-only rendering and route protection, modal dismissal, and preservation of single-field writes.
- **135 passed** across the complete automated test suite.
- Dashboard and Grow Profile JavaScript syntax checks: **passed**.
- Two existing FastAPI `on_event` deprecation warnings remain; no new test failures.
- Controller hardware and mobile-browser interaction have not yet been exercised against a live deployment.

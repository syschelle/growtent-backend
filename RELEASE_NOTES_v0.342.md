# GrowTent Backend v0.342

## Grow Profile admin hardening and adjustment steps

This release tightens Grow Profile visibility for guest users and simplifies numeric adjustments.

### Security

- The **Anpassen / Adjust** button is now rendered by the server only for authenticated administrator sessions.
- Guest dashboard HTML does not contain the Grow Profile button element.
- The detached `/grow-profile` page is administrator-only.
- `/app?page=grow-profile&tent=...` is also treated as an administrator-only shell route.
- The Grow Profile page performs an additional real-admin session check as defense in depth.
- Existing `GET/PATCH /tents/{tent_id}/grow-profile` admin authorization remains unchanged, so write access is still protected independently from UI visibility.

### Dashboard placement

- **Anpassen / Adjust** is now displayed inside the existing status tile, immediately after `Status: OK`.
- The button remains completely absent from guest-rendered dashboard HTML and appears only for administrators when the controller connection is healthy and the Write API is ready.

### Adjustment increments

- Target temperature can be adjusted in **0.5 °C** steps.
- Target VPD can be adjusted in **0.1 kPa** steps.
- The page validates these increments before sending a write request.
- Firmware range validation, HMAC-SHA256 authentication and `stored`/`runtime` post-write verification remain unchanged.

### Tests

- Added regression tests proving that guest-rendered dashboard HTML has no Grow Profile button element.
- Added tests that guests cannot open the Grow Profile route directly or through the app shell query.
- Updated UI tests for the 0.5 °C and 0.1 kPa adjustment steps.
- Full automated test suite: **98 passed**.
- Dashboard JavaScript syntax check: **passed**.
- Grow Profile JavaScript syntax check: **passed**.

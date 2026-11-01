# GrowTent Backend v0.340

## Grow Profile page routing hotfix

This hotfix fixes the detached Grow Profile page introduced in v0.339.

### Fixed

- Registered the `/grow-profile` page in the modular FastAPI application started by the production container (`uvicorn main:app`).
- Fixes `{"detail":"Not Found"}` when opening **Grow Profile** from a tent dashboard.
- The simplified Grow Profile UI and authenticated controller write logic are unchanged.
- Added a regression test for the production system router.

### Tests

- Full automated test suite: **91 passed**.

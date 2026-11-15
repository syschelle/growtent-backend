# GrowTent Backend v0.367

## Changes

- Add `temperature_target` (°C) and `vpd_target` (kPa) to each point in the dashboard JSON history download and `/api/history`.
- Use the target recorded in the same historical ESP sample, preserving target changes over time.
- Missing or invalid targets remain `null`; current/latest values are never copied into old points.
- Existing measurements, timestamps and the 50-point export limit remain unchanged.

## Compatibility

Additive JSON fields only. No firmware update or database migration required. Historical rows are not rewritten; target values absent from stored samples cannot be reconstructed.

## Validation

Regression tests cover both JSON projections, changing/missing/invalid targets, precision, zero, numeric strings and unchanged database rows. Existing backend, PostgreSQL, browser and CodeQL checks run in CI.

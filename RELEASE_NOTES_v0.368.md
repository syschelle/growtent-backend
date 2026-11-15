# GrowTent Backend v0.368

## Changes

- JSON export now offers a period selector and direct `.json` file download, defaulting to 24 hours with 2-minute windows.
- Support 1, 6, 12, 24 and 48 hours; 48h uses 4-minute windows. At most 720 windows are exported.
- Retain control/raw climate averages, min/max and valid counts, historical targets/leaf offset, adaptive factors, humidifier power and observed state changes.
- Preserve empty windows, unknown states and explicit sampling gaps. No synthetic OFF states or target backfill.
- Keep files at or below 1,000,000 bytes by widening windows if needed; the actual interval is recorded in metadata.

## Compatibility

No firmware update or database migration required. Backend recording cadence is unchanged. The new `growtent.analysis.v1` file is aggregated data; legacy `/api/export` and `/api/history` remain available unchanged. Switch and target changes reflect backend observations; events between polls may be missed. Per-window detail lists are capped at 4 target changes and 8 switch transitions, with full observed counts and explicit omission metadata.

## Validation

Production aggregation/download tests cover windowing, extrema, gaps, unknown states, target changes, bounds, file size and immutable reads. Browser tests cover file download, range selection, translations, responsive layout and failure handling. Existing backend/PostgreSQL/chart/browser/CodeQL checks run in CI.

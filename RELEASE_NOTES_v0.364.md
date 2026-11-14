# GrowTent Backend v0.364

## Changes

- Use the ESP regulation value sensors.cur.vpdKpa for the dashboard VPD tile, camera-popup metric, VPD history curve, average/min/max and history exports.
- Remove backend VPD calculation and fallback to smoothed/raw/legacy or previous-sample values. Keep the existing smoothed VPD fields as compatibility aliases of the authoritative ESP value.
- Preserve unavailable samples as null and visible chart gaps. Missing values no longer turn into zero or an older "current" legend value and do not bias averages/min/max.
- Keep exact VPD data without backend spike/EMA filtering or chart-data rounding. Display formatting remains two decimals and the chart retains VPD, average and target lines.
- Do not issue backend exhaust-control requests for invalid/stale/unavailable VPD inputs.

## Compatibility

- No firmware update, ESP VPD algorithm, Adaptive Climate Smoothing, target, hysteresis or chart-label change.
- Stored historical JSON is not rewritten. Read projections select the stored ESP-current channel; past chart values can therefore differ from the formerly preferred backend-calculated field.
- Historical values already synthesized into the current channel by older backends cannot be identified or reconstructed automatically. No backfill is performed.
- Existing keys are retained; backend.vpd.source is additive and identifies the selected channel, not cryptographic provenance. Invalid VPD is null rather than a fabricated value.

## Validation

Channel and production-path tests cover ingestion, latest, filtered/unfiltered history, both history exports, exact ESP values, explicit gaps, invalid/absent samples, sensor validity, prior-sample rejection, unchanged historical rows and invalid-input exhaust denial. A 50-sample synthetic regression and production chart-builder checks cover strict source selection, null-safe formatting, exact values, statistics and latest legend. Full backend/PostgreSQL/native-dialog/browser and CodeQL CI remain required. No live controller/database/Shelly/push provider is contacted; physical-device comparison remains open.

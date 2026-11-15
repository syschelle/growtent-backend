# GrowTent Backend v0.370

## Changes

- Add a VPD table button to the VPD tile with a responsive read-only reference grid.
- Highlight the nearest current temperature/humidity cell and show exact ESP control VPD, target, leaf offset and a separately labeled reference calculation.
- Calculate reference cells using the configured leaf offset; keep the ESP regulation value unchanged.
- Explicitly handle missing offsets, stale/invalid readings, tent switches and out-of-range measurements.
- Support German/English, Celsius/Fahrenheit, light/dark, keyboard closing and automatic initial centering on the live marker.

## Compatibility

No firmware update, database migration, controller writes or additional ESP/Shelly polling. Numeric color bands are reference ranges and do not set targets or growing-phase policies. Grid references may differ from the ESP regulation value because the ESP uses smoothing; the nearest grid marker is rounded.

## Validation

Production module tests and browser checks cover formula/offset behavior, central-value ownership, stale/missing data, race guards, marker/grid behavior, responsive layout and no network/control side effects. Existing backend/PostgreSQL/chart/editor/export/CodeQL checks run in CI.

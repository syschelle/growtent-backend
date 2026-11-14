# GrowTent Backend v0.365

## Changes

- Temperature charts suggest a range of target ±5 °C (±9 °F), reducing visual exaggeration of small fluctuations.
- Without a target, temperature uses the midpoint of valid raw/current readings.
- Humidity charts suggest midpoint ±5 percentage points, bounded by 0–100% for these suggestions.
- Larger excursions remain visible through automatic axis expansion. Both sides retain synchronized scales.
- Measurements, smoothing, averages, exports and ESP control are unchanged. VPD chart scaling is unchanged.

## Validation

Production chart runtime tests cover Celsius/Fahrenheit, missing targets, raw readings, missing data and excursions. Full existing backend and browser checks run in CI. No firmware update required.

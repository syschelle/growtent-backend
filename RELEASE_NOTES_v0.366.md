# GrowTent Backend v0.366

## Changes

- Add Setup → Charts with configurable temperature half-span (°C), humidity minimum width (percentage points) and VPD minimum width (kPa).
- Zero selects automatic scaling. Defaults preserve v0.365: ±5 °C, 10 percentage points and automatic VPD.
- Settings persist in this browser for all tents and apply on the next chart refresh. Fahrenheit temperature spans convert automatically.
- Larger excursions remain visible. Measurements, smoothing, statistics, exports and ESP regulation remain unchanged.

## Compatibility

No firmware update or database migration required. These settings are browser-local, are not synchronized across devices and are not included in backend backups. Invalid stored preferences fall back to defaults.

## Validation

Production chart runtime tests and browser save/reload/layout/failure tests cover the new preferences. Existing backend, PostgreSQL, browser and CodeQL checks run in CI.

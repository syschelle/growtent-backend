# v0.355 — restore the next irrigation display from the ESP

## Changes

- Restore the Next irrigation line using next_run_at/next_run_status from the HMAC-verified ESP plan response.
- Support both classic eight-relay and ESP32-S3 six-relay controllers. The previous display path excluded the S3 layout.
- Show explicit disabled, Drying, clock, running, buffer, Flood, pump/configuration and schedule states instead of a generic dash.
- Mark stale backend state and stale Shelly schedules. Do not present an expired cached prediction as the next run.
- Keep the last-watering date visible. Do not calculate an independent backend forecast or trigger automatic watering.

## Compatibility

Install ESP firmware v0.5.12 for next-run metadata. Older protocol-v2 firmware remains usable for configuration/manual starts and displays an explicit update-required message for next-run prediction. No database migration or credential changes are required. The displayed time is the ESP's current plan projection; phase, schedule or interlock changes can change it.

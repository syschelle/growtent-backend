# GrowTent Backend v0.384

- Read pm1:0 in direct Shelly status queries so Plug PM Gen3 live power and energy no longer become false OFF/zero readings.
- Report valid PM1 meters as permanently ON, matching the ESP state API, including zero-load samples.
- Reject missing/invalid components instead of fabricating an OFF state; do not convert null metrics to zero.
- Keep heatmat monitoring-only and hide toggle controls for directly identified PM1 meters.

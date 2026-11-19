# GrowTent Backend v0.394

- Export exhaust-fan power in watts as `points[].metrics.exhaust_watt` (average, minimum, maximum and valid sample count), using the same historical windows as climate and humidifier power. Keep `points[].shelly.exhaust.power_w` identical when the role exists.
- Accept the historical `cur.shelly.exhaust.watt` and `shelly.exhaust.watt` aliases; prefer the canonical `cur.shelly.exhaust.Watt`. Explicit stale/invalid freshness excludes readings. Real zero remains zero; missing or invalid power stays null. No power is inferred from switch state or live data.
- Retain the v1 format, existing sensor/irrigation exports, selected period and 1 MB size guard. No schema, controller or UI changes.

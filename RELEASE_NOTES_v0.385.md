# GrowTent Backend v0.385

- Extend the historical JSON analysis export with state, power, energy and freshness for all seven Shelly roles, including light, heater, heatmat and exhaust.
- Include observed Grow phase/day/week and ESP-stored light ON/OFF schedule context with timestamped changes.
- Preserve unknown/stale values and real zero readings; do not infer switch state from power or backfill historical data from live dashboard reads.
- Retain aggregate extrema/counts and bounded event details when adapting export windows to the existing 1 MB download limit. Existing climate and humidifier fields remain available.

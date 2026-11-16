# GrowTent Backend v0.386

- Preserve missing Shelly power history as null gaps instead of converting it to 0 W.
- Apply this to main, light, humidifier, heatmat and exhaust plots; keep real measured zero watts unchanged.
- Do not treat null-only heatmat/exhaust history as available readings.
- Historical source records and controller logic remain unchanged. A zero-looking dip is not proof of physical switching.

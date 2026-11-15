# GrowTent Backend v0.380

- Show Night phase instead of the daytime VPD assessment when the light is off. Keep the actual VPD visible.
- Prefer reported light switch state; use fresh daily Shelly schedules as a fallback, including cycles across midnight (Europe/Berlin).
- Show a nighttime humidity notice after five minutes of continuously observed readings at or above 70%. Missing/stale data and tent changes reset observation.
- Display only: no controller changes or push notifications.

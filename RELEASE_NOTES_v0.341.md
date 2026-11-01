# GrowTent Backend v0.341

## Dashboard Grow Profile action placement

This release makes the Grow Profile entry point more compact and context-aware.

### Changed

- Moved the Grow Profile action out of the Grow Phase card.
- The action now appears directly to the left of the dashboard **Status: OK** display.
- Renamed the German action to **Anpassen** (`Adjust` in English).
- The button is hidden unless all required conditions are met:
  - the current user is an administrator,
  - the tent Backend Write API is fully configured,
  - the ESP connection is currently fresh/online, and
  - the dashboard status is currently **OK**.
- When the ESP becomes stale/offline or the dashboard enters a warning/error state, the button disappears automatically.
- The separate Grow Profile page, HMAC-SHA256 authentication, retries and `stored`/`runtime` verification remain unchanged.

### Tests

- Added regression tests for the new button position and visibility rules.
- Full automated test suite: **93 passed**.
- Dashboard JavaScript syntax check: **passed**.

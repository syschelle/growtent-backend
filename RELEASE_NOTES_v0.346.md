# GrowTent Backend v0.346

## Optional Growlight power-drop warning

This release adds an optional per-tent warning for sudden Growlight power loss, intended to detect partial light failures while the controller still reports the light as switched on.

### Setup

- Added **Growlight power warning** to each tent configuration.
- The warning can be enabled or disabled independently per tent.
- Added a configurable Watt-drop threshold.
- Default threshold: **20 W**.
- Allowed range: **1–1000 W**.

### Detection behavior

- Uses the existing `cur.shelly.light.isOn` and `cur.shelly.light.Watt` values already received from the GrowTent controller.
- No additional Shelly or controller polling is introduced.
- A rapid drop is evaluated between two consecutive successful backend polls (default poll interval: 10 seconds).
- The light must report **ON in both samples**. A normal switch-off therefore does not generate an alert.
- The drop must be **strictly greater** than the configured threshold. With a 20 W threshold, a 20.0 W drop does not alert; a 20.1 W drop does.
- Invalid/missing Watt samples and failed/offline polls break the comparison chain instead of producing false positives after reconnect.

### Notifications

- Alerts use the existing Pushover configuration.
- The notification includes the tent name, previous power, current power, detected drop, and configured threshold.
- Only one notification is sent per drop episode.
- The detector rearms after the light is switched off or the power recovers close to the pre-drop reference level.

### Database and backup

- Added per-tent `growlight_power_alert_enabled`.
- Added per-tent `growlight_power_drop_w`.
- Existing databases are extended automatically at startup.
- Configuration backup schema updated to **v13**.

### Tests

- Added tests for baseline establishment, strict threshold behavior, normal light-off suppression, alert rearming, invalid Watt handling, Pushover message content, Setup configuration, database/backup persistence, and offline-chain reset.
- Full automated test suite: **111 passed**.
- Setup JavaScript syntax check: **passed**.

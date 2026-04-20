# Changelog

Entries are maintained in project language (English/German as needed).

## v0.242

### Shelly “Last update” now prefers direct activity timestamps
- Dashboard Shelly cards now prefer a direct Shelly-derived activity timestamp for the `Update` line.
- Activity is tracked when direct poll reports `isOn=true` or `Watt > 0.5`.
- Fallback remains safe: if no direct activity timestamp is available, UI falls back to DB-derived `last_activity` / `last_switches`.
- This reduces stale-looking timestamps during short on/off cycles that are missed in `/api/state` snapshots.

## v0.241

### VPD parity: Live tile aligned with VPD history channel
- Dashboard live VPD tile now prefers `sensors.smoothed.vpdKpa` (with fallback to `sensors.cur.vpdKpa`) to match history semantics.
- History pipeline now avoids backend re-calculating VPD from temperature/humidity when VPD channel is missing.
- History fallback order is now explicit and channel-based: `vpd_smoothed -> vpd_cur -> vpd_raw`.
- Goal: prevent systematic offsets between `VPD` tile and last point in `VPD History`.

## v0.240

### Shelly cards: direct-read first with safe one-time fallback
- Dashboard Shelly cards now await direct Shelly device reads (`/tents/{tent_id}/shelly/direct-all`) before rendering values.
- This prevents Shelly card state/power display from being sourced primarily from stale controller `/api/state` payload values.
- Added a one-time fallback guard so UI can still show existing values once if direct Shelly read is temporarily unreachable.

## v0.239

### Guest UX follow-up adjustments
- Setup page in guest mode now shows only the `Appearance` tile; all other setup cards/sections are hidden for guests.
- Restored `Open fullscreen` availability for guest users in dashboard stream actions.
- Improved guest badge (`Gastmodus aktiv`) contrast for light theme.
- Unified action button typography so link-style action buttons (e.g. `Open fullscreen`) match regular button weight/style.

## v0.238

### Guest setup link visibility in app shell
- Restored `Setup` navigation link visibility for guest users in `/app` shell.
- Removed guest-only forced redirect from `setup` page to `dashboard` in shell routing.
- Guest write restrictions remain enforced server-side.

## v0.237

### Guest-only display mode + per-user persistence
- Display mode toggle (`mobile/desktop`) is now restricted to guest users only.
- Added backend endpoints for UI preferences:
  - `GET /ui/preferences`
  - `POST /ui/preferences`
- Display mode is now persisted per logged-in user (role+username key) in DB table `app_user_ui_prefs`.
- Shell and dashboard now load/store guest display mode via backend preferences instead of only browser-local state.

## v0.236

### Irrigation plan: editable last run date + robust run tracking
- Added editable `last_run_date` support to irrigation-plan updates (`PUT /tents/{tent_id}/irrigation-plan`).
- Added date input in both irrigation plan modals (Setup + Dashboard), prefilled with current last run date.
- Scheduler/plan start date can now be adjusted directly by selecting a date.
- Added automatic `irrigation_last_run_date` update when watering actually starts (`irrigation.runsLeft` transition `0 -> >0`).
- Kept existing manual start date updates and schedule-trigger updates in place.

## v0.235

### Shelly schedule visibility for all devices
- Dashboard now shows parsed `ON/OFF` schedule info for all Shelly cards (when a `settings.shelly.<device>.line` schedule exists), not only for `light`.

## v0.234

### Pushover online recovery notifications
- Added `tent online` Pushover notification when a tent recovers from a previously notified offline episode.
- Recovery message can include approximate offline duration.

## v0.233

### Keep offline status stable
- Prevented dashboard status flicker between `OK` and offline message while a tent is offline.
- History refresh no longer clears status to `OK` when tent is still considered offline.

## v0.232

### Offline status messaging alignment
- Aligned dashboard status messaging with the red offline dot threshold (`> 2 min` without fresh data).
- Updated delayed-source message to explicitly mention `/api/stats` data staleness.
- Shortened offline fallback status text to:
  - `Tent offline or /api/stats currently unreachable.`

## v0.231

### Legend stats on average lines
- Moved min/max range info to the `Average` legend entries (Temperature + VPD).
- Legend now shows: average current value first, then `(min ... / max ...)` for the selected timeframe.

## v0.230

### VPD legend ordering
- Reordered VPD legend text to show current value first, then min/max for selected timeframe.
- Example: `VPD kPa: 1.02 (min 0.82 / max 1.14)`.

## v0.229

### VPD legend stats
- Added min/max values for the selected timeframe directly into the VPD chart legend label.
- Keeps existing current-value display in legend while adding range context (`min ... / max ...`).

## v0.228

### History range selector
- Added `12h` option to dashboard history range selector.
- Allowed `720` minutes as a valid range value in frontend range switching logic.

## v0.227

### History average line in charts
- Added average lines to Temperature History and VPD History charts.
- Added i18n label for `Average` / `Durchschnitt`.
- Updated average line style to red/white dashed for better visibility.

## v0.223

### Pushover noise reduction
- Removed `/notify/status` push sender endpoint.
- Removed automatic "tent online" push notifications.
- Kept only offline-notification throttling behavior from `v0.222`.

## v0.222

### Offline notification throttling for tents
- Added delayed offline push notifications with configurable threshold (`OFFLINE_NOTIFY_DELAY_SECONDS`, default 300s).

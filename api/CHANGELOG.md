# Changelog

Entries are maintained in project language (English/German as needed).

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
- Sends at most one offline notification per offline episode (no repeated spam while still offline).
- Resets notification cycle after tent comes back online, so next outage can notify again.

## v0.221

### Setup: dedicated Pushover save action
- Added a dedicated `Save Pushover` button inside the Pushover status card in Setup.
- Kept existing access-save flow intact; button now gives direct save action for that card.
- Added DE/EN i18n labels for the new button text.

## v0.220

### History chart axis synchronization
- Synchronized right Y-axis min/max to match the left Y-axis for temperature, humidity, and VPD history charts.
- Keeps both sides in the same value range and avoids mismatched legend/axis interpretation.

## v0.219

### Guest access enforcement and legacy-delete fix
- Enforced guest read-only restrictions independently of global auth flag.
- Blocked anonymous write requests when global auth is disabled.
- Added legacy guest deletion handling (pseudo guest id) so old guest entries can be removed from setup.
- Synced app version to `v0.219`.

## v0.218

### Multi-guest setup and access hardening
- Added setup support for multiple guest users with list view (username, expiry, status) and create/delete actions.
- Added `/config/guests` CRUD endpoints and router wiring for modular runtime.
- Added browser-language default for setup language select when `gt_lang` is not set.
- Removed legacy single-guest setup card from UI and kept compatibility display via guest list API.
- Fixed guest creation default to `enabled=true` when no checkbox is present.
- Hardened guest access controls: guest sessions are always read-only and blocked from setup/config writes.
- Added anonymous write blocking when global auth is disabled to prevent control bypass.

## v0.217

### Grow-Guide + dashboard hint improvements
- Added a dedicated **Grow-Guide** page and linked it in sidebar navigation (above Setup).
- Added VPD explanation hints on current VPD and VPD history labels.
- Added humidity explanation/risk hints on current humidity and humidity history labels.
- Added temperature explanation hint with VPD interaction on current temperature and temperature history labels.
- Improved alpha hint readability with larger in-app popover display.
- Kept routing compatible with modular startup (`main.py` + `routes/system.py`) by exposing `/grow-guide` through system router.

## v0.216

### Stability fixes after backend min-VPD removal
- Fixed tents list/poller regressions caused by removed exhaust VPD columns.
- Kept API-stats min-VPD info button/modal active in dashboard.
- Synced displayed app version with release line.

## v0.214

### Removed backend min-VPD monitoring feature set
- Removed backend min-VPD control execution.
- Removed dashboard buttons/modals related to backend min-VPD monitoring.
- Removed backend API endpoints for exhaust VPD plan.
- Removed backend persistence usage for exhaust VPD plan fields.

## v0.208

### Exhaust VPD disable behavior
- Disabling minimum VPD monitoring no longer resets `exhaust_vpd_triggered`.
- This prevents automatic forced-off side effects when the VPD monitor is disabled.

## v0.207

### JSON export opens in browser tab
- Dashboard JSON export now opens in a new browser tab instead of replacing the current page.
- `/api/export` response is inline JSON (no attachment download header).

## v0.206

### Auth-scoped history API and JSON export
- `/api/history` is no longer public bypass; it follows normal auth/session rules.
- Removed API access setup card (no manual enable/disable toggle anymore).
- `/api/history` keeps metadata fields and now enforces a fixed `limit` of 50.
- Dashboard export action switched from CSV export to JSON export (button text and file format).

## v0.205

### `/api/history` query and metadata upgrade
- Added optional query parameters: `hours`, `limit`, `from`, `to`.
- Added root metadata fields: `from`, `to`, `count`, `limit` (with existing `deviceId`, `points`).
- Ensured `points` are chronologically ascending by `timestamp`.
- Added JSON error responses in stable format: `{ "error": "..." }`.

## v0.204

### API history metadata improvements
- `/api/history` now includes root metadata: `deviceId`, `from`, `to`, `count`, `limit`, `points`.
- `points` are returned in chronological ascending order.
- Empty results now return `from: null`, `to: null`, `count: 0`.

## v0.203

### API history response constraints
- `/api/history` now returns at most 50 rows (`limit: 50`).
- Removed `hours` usage from `/api/history`; endpoint now uses `deviceId` only.
- Updated setup examples to `/api/history?deviceId=<id>`.

## v0.202

### API history endpoint enable/disable in Setup
- Added toggle in API card to enable/disable `/api/history` endpoint.
- Added dedicated save button in API card.
- `/api/history` now returns `403` when API access is disabled.
- Stored flag in auth config (`history_api_enabled`) and included in backup export/import.

## v0.201

### API history password removed
- Removed API history password input from Setup.
- Renamed API card labels to requested wording (`API-Zugriff`, `Passwort` no longer shown).
- Updated all API history examples to omit password parameter.
- `/api/history` now uses only `deviceId` and optional `hours`.

## v0.200

### Setup API card labeling and save action
- Renamed `API-History-Zugriff` to `API-Zugriff`.
- Renamed password label to `Passwort`.
- Added dedicated `Save API access` button in the API card.

## v0.199

### Setup tents: per-tent API history example
- Added API history example URL into each tent row in Setup.
- Uses that tent's id directly (`deviceId=<tent_id>`) for easier handoff.
- Includes DE/EN translated helper label.

## v0.198

### API history example update
- Setup example call now uses tent id (`deviceId=1`) instead of a name string.

## v0.197

### Setup UX: API History Password card
- Renamed label to `API-History-Password`.
- Moved API history password out of Pushover card into a dedicated card.
- Added translated example call directly in that card.

## v0.196

### New secure JSON history endpoint
- Added `GET /api/history` with query params:
  - `deviceId` (required)
  - `hours` (optional, default `12`)
  - `password` (required)
- Added password validation via env var `GROMATE_API_PASSWORD`.
- Added device resolution by tent id / tent name / source_url fragment.
- Added structured UTC ISO8601 (`Z`) output mapping with raw/smoothed/alpha fields.
- Added API logging for access and errors.

## v0.194

### Default dashboard history range
- On page reload, history charts now default to `1h` instead of `24h`.
- Updated related range defaults used by dashboard load and export flow.

## v0.193

### About/Changelog fallback for API-only deployments
- Added resilient changelog loading from multiple locations.
- Added bundled `api/CHANGELOG.md` so About/Changelog is never empty in API-only builds.
- Keeps GitHub and ZIP links available in About.

## v0.192

### Hotfix
- Fixed broken About link markup in app shell sidebar (missing closing `>`), which could break navigation/page rendering.

## v0.191

### HoverHint convention + About page update
- Adopted `HoverHint` convention for UI explanation tooltips (`ℹ️`) with DE/EN translation behavior.
- Navigation label changed from `Changelog` to `About`.
- About page includes GitHub repository link opening in a new tab.

## v0.190

### Alpha history tooltip
- Added hover hint (`ℹ️`) to Alpha History label.
- Tooltip text follows selected UI language (DE/EN).
- Includes explanation of alpha behavior for temperature/humidity smoothing.

## v0.189

### Range control cleanup
- Removed history-range selector from Setup page.
- Dashboard range control is now the single source for history range changes.
- Dashboard initializes history range to 24h on page load.

## v0.188

### Dashboard range UX polish
- Range error feedback moved to the inline range control row (not top status).
- Error text shown only when needed, in red.
- Label text aligned and translated for DE/EN.

## v0.187

### Live range selector validation
- On dashboard range change, app validates selected window has history points.
- If no points exist, selector reverts to previous value and shows translated inline hint.

## v0.186

### Dashboard range control placement
- Moved live history range selector to a one-line control directly above first history chart.

## v0.185

### Live range selector on status page
- Added direct history-range selector on dashboard (no Setup save required).
- Presets: `1h`, `24h`, `48h`.
- Selection is stored in localStorage (`gt_range_minutes`).

## v0.184

### Setup range preset update
- Setup presets changed to `1h`, `24h`, `48h`.
- Removed `6h` and `7d` from Setup selector.
- CSV export forwards custom minute ranges correctly.

## v0.183

### UI color alignment
- Current value cards now match history line colors:
  - Temp `#22d3ee`
  - Humidity `#a78bfa`
  - VPD `#f59e0b`
  - External sensor `#10b981`

## v0.182

### Chart.js reliability fix
- Removed external CDN dependency for charts.
- Added local static asset: `api/static/chart.umd.js`.
- Mounted `/static` in FastAPI and load Chart.js from local path.

## v0.181

### Chart order tweak
- Moved DS18B20 history chart above Alpha history chart.

## v0.180

### Chart rendering
- Removed visual line smoothing for Alpha and Total Consumption charts (`tension: 0`).

## v0.179

### Deployment docs
- Added update guidance for GitHub/Compose flows.

## v0.178

### Warmup counter wording
- Added translated unit wording after warmup counter value.

## v0.177

### History warmup counter
- Warmup overlay includes remaining point count until charts are considered built.

## v0.176

### Warmup message placement
- Moved warmup message from top status area into each history chart center (red overlay).

## v0.175

### Startup responsiveness
- Dashboard first render no longer blocks on slow Shelly `direct-all` calls.

## v0.174

### Poll continuity / online-state resilience
- If controller temporarily returns null sensor channels, backend backfills from last known payload.
- Keeps `captured_at` fresh and avoids false offline impression.

## v0.173

### Raw/smoothed key alignment
- Aligned to controller semantics:
  - `sensors.cur.temperatureC` / `sensors.cur.humidityPct` => smoothed/current
  - `sensors.cur.temperatureRawC` / `sensors.cur.humidityRawPct` => raw
- Kept legacy `sensors.raw.*` fallback for compatibility.

## v0.172

### Climate channel semantics fix
- Removed raw<-cur implicit substitution in persistence/history/export.

## v0.171

### Climate pipeline simplification
- Removed backend re-smoothing in persistence/history/export paths.
- Trust controller-provided channels as source of truth.

## v0.170

### Rollback baseline
- Restored known stable behavior after UX/performance regressions.

# Changelog

Entries are maintained in project language (English/German as needed).

## v0.256

### Strain library
- Added a dedicated bilingual Strains / Sorten navigation tab.
- Added persistent strain records with name and effect.
- Added create, edit, delete and read-only guest workflows.
- Included the strain library in configuration backup and restore.

## v0.255

### Fullscreen ASMR volume control
- Added a 0-100% volume slider next to the fullscreen ASMR play/pause button.
- Set a moderate default volume of 50%.

## v0.254

### Fullscreen ASMR playback
- Added an ASMR play/pause button to the camera fullscreen preview.
- Added the bundled `thunderstorm.mp3` track with continuous loop playback after an explicit user click.
- Audio playback is stopped and released when the fullscreen preview window closes.

## v0.253

### Security hardening
- Removed hardcoded weak PostgreSQL credentials from both Compose files. Deployments now require a `.env` file with deployment-specific `POSTGRES_*`, `DATABASE_URL`, and `INSTALL_API_TOKEN` values.
- Removed weak fallback `DATABASE_URL` values from the API and Docker auth helper; placeholder or known weak default database URLs are rejected at runtime.
- Added first-run install token protection. `POST /api/install` now requires `INSTALL_API_TOKEN` by default via the install form, `X-Install-Token`, query parameter, or request body.
- Added `.env.example` with placeholder-only values and production replacement guidance.
- Replaced raw dictionary request bodies in tent create/update and irrigation-plan routes with strict Pydantic models that reject unexpected fields.
- Updated deployment docs to clearly mark secrets and connection strings as placeholders that must be replaced.

## v0.252

### Security hardening
- Redacted `shelly_main_password` from tent list/create/update API responses.
- Added `has_shelly_main_password` so clients can display whether Shelly credentials are configured without exposing the secret.
- Tent updates now keep the stored Shelly password when the password field is omitted or left empty; send `shelly_main_password_clear=true` to remove it explicitly.
- Redacted Shelly passwords from configuration backup exports.
- Replaced `alexxit/go2rtc:latest` with a pinned immutable go2rtc image reference in both Compose variants.

### Dashboard version sync
- Bumped the application version to `v0.252`.
- Ensured the dashboard/setup version display uses the current `APP_VERSION` value.
- Updated deployment documentation examples to reference the `v0.252` image tag.

## v0.251

### Authentication password hashing hardening
- Replaced admin and guest password storage with Argon2id hashes.
- Replaced 2FA recovery-code storage with Argon2id hashes.
- Removed legacy password-hash verification from login and recovery flows.
- Updated the Docker auth helper to write Argon2id hashes only.
- Added `argon2-cffi` to the API runtime dependencies.
- Legacy password hash formats are intentionally not migrated; reset admin access with `manage_auth.py` when upgrading an older database.

## v0.250

### Initial install API
- Added a first-start `/install` page for creating the initial admin username and password.
- Added `/api/install` bootstrap endpoints that are available only until the first admin password is stored.
- The install API enables authentication, stores the trimmed admin username, validates password confirmation, and creates an admin session after setup.
- Added `INSTALL_API_ENABLED=false` as an optional environment switch to disable the bootstrap endpoint entirely.
- Updated documentation for the first-start installation flow.

## v0.249

### English README refresh
- Restored the README to English.
- Kept the expanded deployment, networking, authentication, backup and troubleshooting documentation.
- Clarified that irrigation uses normal water pumps.
- Kept publication-specific GitHub push/tag/release instructions out of the README.

## v0.248

### Documentation update for water-pump based irrigation
- Updated the README to document normal water pumps as the supported irrigation hardware.
- Expanded deployment, networking, authentication, backup and troubleshooting documentation.
- Kept publication-specific GitHub push/tag/release instructions out of the README.

## v0.247

### Docker network exposure hardening
- Removed host-published `go2rtc` ports from both Docker Compose files.
- `go2rtc` now stays reachable only inside the Docker Compose network via `go2rtc:1984` / `go2rtc:8554`.
- The API remains the only host-published service port (`8088:8080`).
- Added deployment verification steps to confirm that DB and go2rtc do not expose host ports.

## v0.246

### Multi-arch image release workflow
- Added GitHub Actions workflow to build and push the API image for `linux/amd64` and `linux/arm64`.
- Release tags like `v0.246` now publish both the version tag and `latest` to GHCR.
- Added `docker-compose.images.yml` for production deployments that pull a prebuilt image instead of rebuilding on the target host.
- `docker-compose.images.yml` defaults to `ghcr.io/syschelle/growtent-backend-api:latest` and can be pinned with `GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.246`.

## v0.245

### Admin username handling for setup and Docker reset helper
- Setup UI now trims the admin username in-place before validation and saving, so accidental leading/trailing spaces are not persisted or shown after save.
- `api/manage_auth.py set-admin` now preserves the currently configured admin username when `--username` is omitted.
- Docker reset examples now distinguish between keeping the existing username and explicitly setting/changing it.

## v0.244

### Admin password setup hardening and Docker reset helper
- Setup now uses dedicated new-password fields instead of current-password autofill hints for the admin password.
- Added password confirmation before the admin password is changed from Setup.
- Added `api/manage_auth.py` for Docker-based auth status checks and admin password resets, including optional 2FA reset.

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

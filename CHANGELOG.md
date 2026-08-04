# Changelog

Entries are maintained in project language (English/German as needed).

## v0.284

### Balanced genetics option
- Added `50/50` as an allowed genetics value for cannabis strains.
- Added the `50/50` option to the strain editor genetics dropdown.
- Normalizes common balanced-hybrid inputs such as `50-50`, `50:50`, `balanced hybrid`, `Sativa/Indica` and `Indica/Sativa` to `50/50`.

## v0.283

### On-demand Shelly light schedule lookup
- Added an on-demand direct Shelly `Schedule.List` read for the light Shelly when an active irrigation plan cannot use the controller-provided light schedule line.
- Parsed the first enabled light ON schedule and used it to calculate the next irrigation run.
- Cached Shelly schedule reads so the backend does not permanently poll Shelly schedules.
- Added a dashboard distinction between a missing schedule source and no matching light ON schedule found.

## v0.282

### Irrigation plan next-run diagnostics
- Added a dashboard-side validation for active irrigation plans that cannot calculate the next run because the light ON schedule is missing or unreadable.
- The dashboard now shows `light schedule missing` / `Licht-Zeitplan fehlt` instead of only displaying an empty next-run value.
- Keeps the display localized in English and German.

## v0.281

### Release version bump and deployment metadata
- Bumped the application version to `v0.281`.
- Carries forward the direct Shelly toggle timeout hotfix from v0.280.
- Updated pinned image examples in the deployment documentation to `v0.281` while keeping Compose defaults on `latest`.

## v0.280

### Direct Shelly toggle hotfix
- Uses direct Shelly switching for configured light, humidifier, heater, fan and exhaust devices.
- Avoids controller action proxy timeouts when toggling Shelly devices from the web interface.
- Keeps the legacy controller proxy as fallback when a device has no Shelly IP configured in the latest controller state.

## v0.279

### Shelly toggle response normalization
- Normalized Shelly toggle responses for `main`, `light`, `humidifier`, `heater`, `fan` and `exhaust`.
- Proxied Shelly devices now expose controller response fields under `state`, including `state.isOn`.
- Backend `ok` now becomes `false` when the controller response reports `response.ok == false`.

## v0.278

### English About page summary
- Translated the About page summary section from German to English.
- Added the v0.278 summary item to keep the overview aligned with the current version.
- Keeps the full changelog below the summary section.

## v0.277

### About page release summary
- Added a compact About page summary of the main changes from v0.265 to the current version.
- Highlights strain library changes, pot assignments, dashboard stream updates, fullscreen metrics and exhaust history improvements.
- Keeps the full changelog below the new summary section.

## v0.276

### Conditional dashboard exhaust history
- Shows the exhaust history chart only when the exhaust Shelly is configured or exhaust history values exist.
- Keeps the dashboard cleaner for setups without an exhaust device.
- Preserves German and English labels for the exhaust history card.

## v0.275

### Dashboard exhaust history
- Added an exhaust power history chart to the dashboard.
- Uses the existing history range selector and displays values from `/tents/{tent_id}/history`.
- Added German and English UI labels for the new chart.

## v0.274

### Live climate metrics in fullscreen camera preview
- Added live temperature and VPD values to the fullscreen camera preview header.
- Keeps the climate values outside of the camera image so they do not cover the top-right area of the picture.
- Refreshes the fullscreen climate values continuously from `/tents/{tent_id}/latest`.

## v0.273

### Refine dashboard pot strain links
- Changed the dashboard pot strain display so only the strain name is clickable.
- Removed the underline styling from the strain link.
- Pot labels remain plain text, for example `Topf 1: Blue Dream`.

## v0.272

### Fix dashboard strain detail JavaScript escaping
- Fixed JavaScript string escaping in the dashboard strain detail popover.
- Resolves `Uncaught SyntaxError: Invalid or unexpected token` on the embedded dashboard page.

## v0.271

### Clickable dashboard pot strains
- Made pot strain names below the dashboard camera stream clickable.
- Opens a popover, matching the existing info hint style, with the selected strain's genetics, THC, CBD, effects and aroma values.
- Loads strain details from the database-backed strain library without translating the stored strain values.

## v0.270

### Fix stream pot strain placeholder
- Added the missing dashboard placeholder element below the camera stream preview.
- Ensures the compact pot strain list can render under the live image.

## v0.269

### Stream pot strain display cleanup
- Removed the leading `Pot strains` / `Topf-Sorten` prefix below the camera stream.
- The dashboard now displays only the compact pot list, for example `Topf 1: Blue Dream · Topf 2: Critical Kush · Topf 3: Lemon Haze`.

## v0.268

### Show pot strains below camera stream
- Added pot strain display below the live camera preview in the dashboard stream card.
- Included `pot_strains` in the `/tents/{tent_id}/latest` response.
- Localized the pot strain labels in the dashboard for German and English UI languages.

## v0.267

### Database-backed strain library
- Moved the strain library source of truth from `data/strains.csv` to PostgreSQL.
- Seeded the database from `data/strains.csv` only when the strain table is empty.
- Kept `/strains.csv` as a live export of the database-backed strain library.
- Included database-backed strains in configuration backup/restore.
- Kept three-pot strain assignments stored in PostgreSQL and fixed the modular tent update service path.

## v0.266

### Pot strain assignment and localized strain page
- Added three pot strain assignments per tent in setup, backed by `pot_strains_json`.
- Included pot strain assignments in tent API responses and configuration backup/restore.
- Restored German/English UI labels for the strain library page while keeping CSV values unchanged.
- Kept guest users read-only on the strain library page and write-protected through existing guest restrictions.

## v0.265

### English-only strain CSV
- Replaced the bilingual strain CSV columns with single English columns: `Name`, `Genetics`, `THC`, `CBD`, `Effects` and `Aroma`.
- Converted the bundled strain library to English content from the previous `Effects_EN` and `Aroma_EN` fields.
- Updated the API payload, web editor and backup import normalization for the simplified strain schema.
- Kept backward-compatible reading/import for existing bilingual CSV and backup data.

## v0.263

### Dominant hybrid classification
- Replaced the generic `Hybrid` value with `Sativa-hybrid` and `Indica-hybrid`.
- Reclassified the existing hybrid strains by their dominant genetics.
- Kept backward-compatible normalization for legacy hybrid values.

## v0.262

### Hybrid genetics option
- Added `Hybrid` as a third allowed genetics value.
- Added the option to the strain editor select field.
- Reclassified explicitly mixed strains while retaining dominant Sativa/Indica classifications.

## v0.261

### Simplified genetics classification
- Replaced the German and English genetics fields with one `Genetik` field.
- Restricted genetics values to `Sativa` or `Indica`.
- Added backward-compatible reading and backup import for the previous genetics fields.

## v0.260

### Simplified strain library
- Removed the source field from the strain CSV schema, API, web editor and strain cards.
- Existing CSV files with a legacy `Quelle` column remain readable.

## v0.259

### Expanded default strain library
- Expanded the default CSV library from 8 to 24 strains.
- Split genetics into German and English fields and added a source URL.
- Renamed the German effects column to `Wirkung_DE`.
- Added backward-compatible reading of the previous eight-column CSV schema.
- Extended the bilingual web editor and configuration backup format for the new fields.

## v0.258

### Default strain CSV
- Added `data/strains.csv` to the repository so new installations include the default strain library.
- Included the eight existing strain records as initial CSV data.

## v0.257

### CSV-backed strain library
- Moved strain records from PostgreSQL to the persistent `data/strains.csv` file.
- Expanded the library to Sorte, Genetik, THC, CBD, Effexts_DE, Effects_EN, Aroma_DE and Aroma_EN.
- Added bilingual web editing and direct CSV download.
- Added automatic migration of existing strain names and effects on first start.
- Updated configuration backup and restore for the expanded strain format.

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

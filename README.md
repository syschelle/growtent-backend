# GrowTent Backend (CanopyOps)

GrowTent Backend is a Docker-based backend and web UI for monitoring and operating one or more GrowTent controllers. It collects controller telemetry, stores history in PostgreSQL, provides dashboard charts and status cards, and offers control functions for compatible Shelly devices, relays, irrigation water pumps, and camera previews.

The project is intended for controller firmware/API versions compatible with the `syschelle/GrowTent` controller project. Basic functions such as Docker startup, login, setup, and configuration backup can work without a controller. Dashboard values, relay actions, Shelly data, camera previews, and irrigation actions depend on the endpoints and payload fields delivered by the connected controller.

<img width="1658" height="964" alt="image" src="https://github.com/user-attachments/assets/52dfa19d-45f6-48e4-a25a-2a151eecc01d" />

---

## Table of contents

- [What this backend provides](#what-this-backend-provides)
- [Architecture](#architecture)
- [Network and security model](#network-and-security-model)
- [Irrigation hardware: normal water pumps](#irrigation-hardware-normal-water-pumps)
- [Compose files](#compose-files)
- [Environment and secrets](#environment-and-secrets)
- [Run with prebuilt images](#run-with-prebuilt-images)
- [Run with a local build](#run-with-a-local-build)
- [Initial installation and first setup](#initial-installation-and-first-setup)
- [Authentication, guests, and 2FA](#authentication-guests-and-2fa)
- [Admin recovery from Docker](#admin-recovery-from-docker)
- [Controller configuration](#controller-configuration)
- [Expected controller capabilities](#expected-controller-capabilities)
- [Shelly integration](#shelly-integration)
- [Camera and go2rtc integration](#camera-and-go2rtc-integration)
- [Data storage, retention, backup, and restore](#data-storage-retention-backup-and-restore)
- [Useful URLs and API endpoints](#useful-urls-and-api-endpoints)
- [Operational checks](#operational-checks)
- [Troubleshooting](#troubleshooting)

---

## What this backend provides

GrowTent Backend is the central UI and API layer for a GrowTent installation.

Main features:

- dashboard for one or more tents/controllers
- live tiles for temperature, humidity, VPD, tank temperature, tank level, and device states
- historical storage of telemetry in PostgreSQL
- charts for temperature, humidity, VPD, alpha values, power usage, and system/storage metrics
- CSV/history access through backend API endpoints
- setup UI for tents, authentication, guests, appearance, language, units, and controller settings
- admin login and guest login modes
- optional two-factor authentication for admin access
- direct Shelly reads for fresher power and switch-state display
- relay and irrigation actions for compatible controllers
- water-pump test actions for configured pump channels
- camera preview support through internal go2rtc access
- database-backed strain library with CSV seed/export support, genetics, THC/CBD, effects and aroma fields
- three pot strain assignments per tent in setup, displayed below the dashboard camera stream with clickable strain detail popovers and live climate metrics in fullscreen preview
- configuration export/import
- Docker CLI helper for admin credential recovery
- first-start install page/API for creating the initial admin account

---

## Architecture

The default Docker stack contains three services.

| Service | Container | Purpose | Host exposure |
|---|---|---|---|
| API/UI | `gt_api` | FastAPI app, web UI, authentication, proxy/helper endpoints | yes, default `8088:8080` |
| PostgreSQL | `gt_db` | persistent configuration and history database | no |
| go2rtc | `gt_go2rtc` | internal camera/RTSP helper | no |

Normal browser access:

```text
http://<server-ip>:8088
```

Common pages:

```text
http://<server-ip>:8088/app?page=dashboard
http://<server-ip>:8088/setup
http://<server-ip>:8088/changelog
http://<server-ip>:8088/health
```

The API polls configured controllers, stores readings, serves the web UI, and forwards selected actions to the controller. PostgreSQL is used for persistent configuration and time-series history. go2rtc is used only as an internal helper for camera preview/stream handling.

---

## Network and security model

By default, only the API/web UI should be reachable from outside Docker.

| Component | Internal address | Published host port | Notes |
|---|---:|---:|---|
| API/UI | `api:8080` | `8088:8080` | the only service published to the host |
| PostgreSQL | `db:5432` | none | Docker-network only |
| go2rtc HTTP/API | `go2rtc:1984` | none | Docker-network only |
| go2rtc RTSP | `go2rtc:8554` | none | Docker-network only |

This means:

- browsers and external clients use `http://<server-ip>:8088`
- the API reaches PostgreSQL internally via `db:5432`
- the API reaches go2rtc internally via `http://go2rtc:1984`
- PostgreSQL is not intended to be reachable directly from the host or LAN
- go2rtc ports `1984` and `8554` are not intended to be reachable directly from the host or LAN

Verify published ports after startup:

```bash
docker port gt_api
docker port gt_go2rtc
docker port gt_db
ss -tulpn | grep -E ':8088|:1984|:8554|:5432' || true
```

Expected result for the default stack:

```text
8080/tcp -> 0.0.0.0:8088
8080/tcp -> [::]:8088
```

`docker port gt_go2rtc` and `docker port gt_db` should print no published ports. In `ss`, only `8088` should appear for this stack.

If `1984` or `8554` still appear, an old container may still exist or the active Compose file still contains old `ports:` entries for go2rtc. See [go2rtc ports are still visible](#go2rtc-ports-are-still-visible).

### Binding the API to localhost only

If the API should only be reachable from the Docker host itself, change the API port mapping to:

```yaml
ports:
  - "127.0.0.1:8088:8080"
```

For LAN access, keep:

```yaml
ports:
  - "8088:8080"
```

---

## Irrigation hardware: normal water pumps

The irrigation features are designed for **normal water pumps** switched by suitable relays, power supplies, and electrical protection.

Use normal water pumps for irrigation channels. Do not plan the system around dosing pump behavior. The backend and dashboard assume that a pump channel can reliably move water when the corresponding relay/action is active.

Hardware recommendations:

- use relay outputs only within their rated voltage and current limits
- use a pump power supply sized for startup current, not only nominal running current
- protect pumps from dry-running
- prevent backflow and siphoning through mechanical layout or check valves
- keep water and mains voltage strictly separated
- use proper fusing, strain relief, cable gauges, and enclosures
- test each pump manually only after the tank, tubing, and drainage path are safe
- use the 10-second pump test action only for short functional checks

In the UI/API, pump and irrigation channels refer to normal water pumps connected to the appropriate relay or controller output.

---

## Compose files

The repository contains two Compose files for different use cases.

### `docker-compose.images.yml`

Recommended for normal operation. The API service uses a prebuilt container image instead of building Python code on the target host.

Advantages:

- fast startup on Raspberry Pi and x86 servers
- no local Python build environment required
- one deployment file for ARM64 and AMD64 systems
- deterministic operation when a fixed image tag is used

Default API image:

```text
ghcr.io/syschelle/growtent-backend-api:latest
```

Pinned image example:

```text
ghcr.io/syschelle/growtent-backend-api:v0.289
```

The go2rtc helper image is pinned by default as well, instead of using a moving `latest` tag:

```text
alexxit/go2rtc:1.9.14@sha256:f0579db234b4f9e8630493777dbf8581630d5d942d27b884ac9186f3d688e7bf
```

Override it only deliberately, for example during controlled testing:

```bash
GO2RTC_IMAGE=alexxit/go2rtc:1.9.14@sha256:f0579db234b4f9e8630493777dbf8581630d5d942d27b884ac9186f3d688e7bf docker compose -f docker-compose.images.yml up -d --force-recreate go2rtc
```

### `docker-compose.yml`

Recommended for local development or testing from source. The API image is built from `./api`.

```bash
docker compose up -d --build
```

For production-style operation, prefer `docker-compose.images.yml`.

---

## Environment and secrets

Both Compose files require deployment-specific database credentials through a `.env` file. They intentionally do not contain usable default database passwords. This avoids accidentally copying weak example credentials into a real installation.

Create the file from the template:

```bash
cp .env.example .env
```

Then edit `.env` and replace every `REPLACE_WITH_*` value with a strong random secret. Do not commit `.env` and do not reuse the placeholder values.

Required values include:

```text
POSTGRES_DB=<database-name>
POSTGRES_USER=<database-user>
POSTGRES_PASSWORD=<strong-random-database-password>
DATABASE_URL=postgresql://<database-user>:<url-encoded-database-password>@db:5432/<database-name>
INSTALL_API_TOKEN=<strong-random-first-run-install-token>
```

Use different secrets for each deployment. If the database password contains special characters, URL-encode it in `DATABASE_URL`.

The application refuses to start with missing, placeholder, or known weak default database URLs.

Generate example random values on Linux:

```bash
openssl rand -base64 36
openssl rand -base64 48
```

---

## Run with prebuilt images

Create or enter the project directory on the target host:

```bash
cd /opt/growtent-backend
```

Create and edit the required `.env` file before starting the stack:

```bash
cp .env.example .env
nano .env
```

Pull images:

```bash
docker compose -f docker-compose.images.yml pull
```

Start the stack:

```bash
docker compose -f docker-compose.images.yml up -d --remove-orphans
```

The image-based Compose file defaults to the moving latest image. You can also pin a release explicitly:

```bash
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.289 docker compose -f docker-compose.images.yml pull
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.289 docker compose -f docker-compose.images.yml up -d --remove-orphans
```

Check status:

```bash
docker compose -f docker-compose.images.yml ps
curl -i http://127.0.0.1:8088/health
```

Open the UI:

```text
http://<server-ip>:8088/app?page=dashboard
```

Open setup:

```text
http://<server-ip>:8088/setup
```

### Private GHCR package access

If the container registry package is private, log in on the server before pulling images:

```bash
echo "$CR_PAT" | docker login ghcr.io -u syschelle --password-stdin
```

The token needs package read access.

---

## Run with a local build

For local development or a source-based install:

```bash
cd /opt/growtent-backend
docker compose up -d --build
```

Check the API:

```bash
curl -i http://127.0.0.1:8088/health
```

---

## Initial installation and first setup

On a fresh installation, before an admin password exists, open:

```text
http://<server-ip>:8088/install
```

The initial installation page creates the first administrator account. It asks for:

- admin username
- admin password
- password confirmation
- install token from `.env` (`INSTALL_API_TOKEN`)

After the first admin password is stored, the install page/API is no longer available. Requests to the install API then return `404`, so the bootstrap endpoint cannot be reused for later credential changes.

Initial install API endpoints:

```text
GET  /api/install      available only before the first admin password exists
POST /api/install      creates the initial admin account and enables authentication
```

The install API is protected by `INSTALL_API_TOKEN` by default. The token must be provided in the install form or as the `X-Install-Token` header for `POST /api/install`.

The install API can be disabled completely with the environment variable:

```text
INSTALL_API_ENABLED=false
```

For development-only environments, token enforcement can be disabled with:

```text
INSTALL_API_REQUIRE_TOKEN=false
```

After the initial admin account has been created, continue with the normal setup page:

```text
http://<server-ip>:8088/setup
```

Typical first setup tasks:

1. sign in with the admin account created during initial installation
2. optionally enable two-factor authentication
3. add one or more tent/controller entries
4. configure controller base URLs
5. configure display name, language, units, and appearance
6. configure optional guest accounts
7. configure Shelly/controller features if available
8. verify the dashboard receives live data

The setup page includes authentication settings, tent configuration, guest configuration, appearance options, backup/import tools, and operational helper links.

---

## Authentication, guests, and 2FA

The backend supports:

- admin login
- optional admin 2FA with TOTP
- guest accounts
- guest-specific UI restrictions
- per-user UI preferences for selected display options

Important admin-password behavior:

- on a fresh database, admin login is blocked until the initial install page creates the first admin account
- after the first admin password exists, `/install` and `/api/install` return `404`
- leaving the password field empty keeps the current password unchanged
- entering a new password changes the admin password
- password confirmation must match before a password change is saved
- the setup UI trims the admin username before validation and saving
- the password itself is not trimmed; leading/trailing spaces are treated as part of the password
- admin passwords, guest passwords, and 2FA recovery codes are stored as Argon2id hashes
- legacy password hash formats are intentionally not accepted or migrated; reset the admin password with `manage_auth.py` if an older database no longer accepts the previous password

Guest mode is intended for restricted dashboard access. Server-side restrictions still apply even if UI elements are hidden.

---

## Admin recovery from Docker

The API image includes `manage_auth.py` for recovery and inspection from inside the API container.

Show auth status:

```bash
docker exec -it gt_api python /app/manage_auth.py status
```

Reset the password while preserving the currently configured admin username:

```bash
printf '%s' '<new-admin-password>' | docker exec -i gt_api python /app/manage_auth.py set-admin --password-stdin --disable-2fa
```

Set username and password explicitly:

```bash
printf '%s' '<new-admin-password>' | docker exec -i gt_api python /app/manage_auth.py set-admin --username 'admin' --password-stdin --disable-2fa
```

With Compose:

```bash
printf '%s' '<new-admin-password>' | docker compose -f docker-compose.images.yml exec -T api python manage_auth.py set-admin --password-stdin --disable-2fa
```

Use `--disable-2fa` when you are locked out because the previous TOTP secret is unavailable.

---

## Controller configuration

Each tent/controller entry typically needs:

- display name
- base URL of the controller
- optional camera/stream settings
- optional Shelly configuration
- optional irrigation plan
- optional exhaust/VPD plan

The backend expects the controller to expose compatible endpoints for state, stats, relay actions, Shelly data, and irrigation actions. If an endpoint is missing or returns a different payload structure, the dashboard may show partial data or mark the tent as delayed/offline.

Controller availability is monitored by polling. The polling interval can be configured with:

```text
POLL_INTERVAL_SECONDS=10
```

History retention can be configured with:

```text
RETENTION_DAYS=7
```

---

## Expected controller capabilities

The UI and API are most useful when the controller provides telemetry such as:

- current temperature
- current relative humidity
- VPD values
- tank temperature
- tank fill/level information
- relay states
- irrigation state
- pump/watering run status
- system/storage metrics
- Shelly state/power information, if Shelly integration is used

Common backend endpoints that depend on controller data:

```text
GET  /tents/{tent_id}/latest
GET  /tents/{tent_id}/history
GET  /tents/{tent_id}/preview
POST /tents/{tent_id}/actions/relay/{relay_idx}/toggle
POST /tents/{tent_id}/actions/startWatering
POST /tents/{tent_id}/actions/pump/{pump_idx}/trigger10s
POST /tents/{tent_id}/actions/pingTank
```

For irrigation pump actions, `pump_idx` is the physical relay index used by the controller. Legacy 8-relay controllers use relays 6/7/8 for pumps 1/2/3, while ESP32-S3-Relay-6Ch controllers use relays 1/2/3. The `irrigation.pump1.enabled` through `irrigation.pump3.enabled` state flags always refer to the logical pump number and are independent of the physical relay number.

If a controller is unreachable, the dashboard should continue to serve the UI but may display stale/offline status for the affected tent.

---

## Shelly integration

Shelly support is used for switch state, power readings, energy readings, and schedule visibility where compatible data is available.

The dashboard can read Shelly data directly through backend helper endpoints, which helps avoid stale controller snapshots. Typical endpoints include:

```text
GET  /tents/{tent_id}/shelly/main/direct
GET  /tents/{tent_id}/shelly/exhaust/direct
GET  /tents/{tent_id}/shelly/direct-all
POST /tents/{tent_id}/actions/shelly/{device}/toggle
POST /tents/{tent_id}/actions/shelly/reset-energy
```

Shelly data quality depends on the configured Shelly addresses, controller settings, and network reachability from the backend/controller environment.

Shelly credential handling:

- `shelly_main_password` may be submitted when creating or updating a tent.
- Tent list/create/update responses do not return the stored plaintext password.
- Responses expose only `has_shelly_main_password` so clients can show whether a password is configured.
- When editing a tent, leave the Shelly password field empty to keep the existing stored password.
- Send `shelly_main_password_clear: true` in an update payload only if the stored Shelly password should be removed.

---

## Camera and go2rtc integration

The stack includes go2rtc as an internal camera helper.

Default internal URL used by the API:

```text
GO2RTC_BASE_URL=http://go2rtc:1984
```

go2rtc is intentionally not published to the host by default. The browser should access camera previews through the API/UI path, not by directly opening `:1984` or `:8554` on the host.

The Compose files pin go2rtc to an immutable image reference by default:

```text
alexxit/go2rtc:1.9.14@sha256:f0579db234b4f9e8630493777dbf8581630d5d942d27b884ac9186f3d688e7bf
```

This avoids silently pulling a newer upstream `latest` image with changed behavior or newly introduced vulnerabilities.

Related endpoint:

```text
GET /tents/{tent_id}/preview
```

If camera preview is unavailable:

- verify the controller/camera stream configuration
- verify `gt_go2rtc` is running
- verify `GO2RTC_BASE_URL` points to `http://go2rtc:1984`
- verify the API can reach go2rtc inside the Docker network

---

## Data storage, retention, backup, and restore

PostgreSQL stores application configuration, history, pot strain assignments, and the strain library. The bundled `data/strains.csv` is used as an initial seed only when the database strain table is empty.

The CSV header is:

```csv
Name,Genetics,THC,CBD,Effects,Aroma
```

Admins can edit these records in the Strains tab. Guest users can view the strain library but cannot edit it. The Strains page localizes UI labels according to the selected UI language, while strain values are displayed unchanged. `GET /strains.csv` downloads a live CSV export generated from the database. Existing CSV data is imported into PostgreSQL on startup only when the database strain table is empty.

Setup stores optional per-tent assignments for three pots as `pot_strains_json` in PostgreSQL. These assignments reference strain names from the database-backed strain library and are included in configuration backup/restore.

The included Compose files use a named Docker volume:

```yaml
volumes:
  db_data:
```

If you customize the Compose file to use a bind mount such as `./data/postgres:/var/lib/postgresql/data`, remember that PostgreSQL initialization variables only apply when the data directory is empty.

### Configuration backup through the UI/API

Export configuration:

```text
GET /config/backup/export
```

Import configuration:

```text
POST /config/backup/import
```

The setup page also provides backup/import controls.

Security note: configuration backup exports do not include plaintext Shelly passwords. They include `has_shelly_main_password` metadata only. After importing a configuration backup, re-enter Shelly device passwords in Setup if those credentials are required. Database-level backups created with `pg_dump` still contain the complete database content and should be protected accordingly.

### Database backup with pg_dump

Create a PostgreSQL dump:

```bash
docker exec -t gt_db pg_dump -U growtent -d growtent > growtent-backup.sql
```

Restore a dump:

```bash
cat growtent-backup.sql | docker exec -i gt_db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

### Named volume backup

For full-volume backup, stop the stack first or ensure a consistent snapshot mechanism. Database-level backups with `pg_dump` are usually easier and safer for normal operations.

---

## Useful URLs and API endpoints

Browser pages:

```text
/                         redirect/helper entry
/install                  initial admin account bootstrap page; first start only
/app?page=dashboard       main app shell/dashboard
/setup                    setup UI
/changelog                changelog page
/grow-guide               grow guide page
/poll-errors              poll error page
/health                   health endpoint
```

Authentication/config:

```text
GET  /api/install       initial install status; first start only
POST /api/install       create initial admin account; first start only
GET  /auth/whoami
POST /auth/login
POST /auth/login/2fa
POST /auth/logout
GET  /config/auth
POST /config/auth
POST /config/auth/2fa
POST /config/auth/2fa/verify
GET  /config/guests
POST /config/guests
PUT  /config/guests/{guest_id}
DELETE /config/guests/{guest_id}
```

Tent data and actions:

```text
GET  /tents
POST /tents
PUT  /tents/{tent_id}
GET  /tents/{tent_id}/latest
GET  /tents/{tent_id}/history
GET  /tents/{tent_id}/preview
GET  /tents/{tent_id}/irrigation-plan
PUT  /tents/{tent_id}/irrigation-plan
GET  /tents/{tent_id}/exhaust-vpd-plan
PUT  /tents/{tent_id}/exhaust-vpd-plan
POST /tents/{tent_id}/actions/relay/{relay_idx}/toggle
POST /tents/{tent_id}/actions/startWatering
POST /tents/{tent_id}/actions/pump/{pump_idx}/trigger10s
POST /tents/{tent_id}/actions/pingTank
```

Shelly helpers:

```text
GET  /tents/{tent_id}/shelly/last-switches
GET  /tents/{tent_id}/shelly/main/direct
GET  /tents/{tent_id}/shelly/exhaust/direct
GET  /tents/{tent_id}/shelly/direct-all
POST /tents/{tent_id}/actions/shelly/{device}/toggle
POST /tents/{tent_id}/actions/shelly/reset-energy
```

---

## Operational checks

After startup:

```bash
docker compose -f docker-compose.images.yml ps
curl -i http://127.0.0.1:8088/health
```

Check logs:

```bash
docker logs --tail=100 gt_api
docker logs --tail=100 gt_db
docker logs --tail=100 gt_go2rtc
```

Check published ports:

```bash
docker port gt_api
docker port gt_go2rtc
docker port gt_db
ss -tulpn | grep -E ':8088|:1984|:8554|:5432' || true
```

Inspect the active Compose configuration:

```bash
docker compose -f docker-compose.images.yml config
```

Inspect the Compose file and port bindings used for a running container:

```bash
docker inspect gt_go2rtc --format 'Project={{index .Config.Labels "com.docker.compose.project"}} Files={{index .Config.Labels "com.docker.compose.project.config_files"}} Service={{index .Config.Labels "com.docker.compose.service"}} PortBindings={{json .HostConfig.PortBindings}}'
```

---

## Troubleshooting

### API port 8088 is not visible

Check whether the API container is running:

```bash
docker compose -f docker-compose.images.yml ps
docker logs --tail=100 gt_api
```

Check whether the Compose config contains the API port mapping:

```bash
docker compose -f docker-compose.images.yml config | grep -A30 "api:"
```

Expected API mapping:

```yaml
ports:
  - mode: ingress
    target: 8080
    published: "8088"
```

If an old container exists, recreate it:

```bash
docker compose -f docker-compose.images.yml rm -sf api
docker compose -f docker-compose.images.yml up -d api
```

or:

```bash
docker rm -f gt_api
docker compose -f docker-compose.images.yml up -d --force-recreate api
```

### go2rtc ports are still visible

If `docker port gt_go2rtc` still shows `1984` or `8554`, the container was created from an old Compose configuration or another Compose file is still publishing the ports.

Search for old port mappings:

```bash
grep -Rni --include='*.yml' --include='*.yaml' -E '1984|8554|go2rtc|ports:' .
```

The `go2rtc` service should not contain `ports:`. It may contain only `expose:` or no port declaration at all:

```yaml
go2rtc:
  restart: unless-stopped
  image: "${GO2RTC_IMAGE:-alexxit/go2rtc:1.9.14@sha256:f0579db234b4f9e8630493777dbf8581630d5d942d27b884ac9186f3d688e7bf}"
  container_name: gt_go2rtc
  expose:
    - "1984"
    - "8554"
```

Recreate the stack:

```bash
docker compose -f docker-compose.images.yml down --remove-orphans
docker rm -f gt_go2rtc gt_api gt_db 2>/dev/null || true
docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Verify again:

```bash
docker port gt_go2rtc
ss -tulpn | grep -E ':1984|:8554' || true
```

### GHCR pull returns `denied`

Typical causes:

- the image package is private
- the server is not logged in to GHCR
- the image name is wrong
- the requested tag does not exist

Login example for private packages:

```bash
echo "$CR_PAT" | docker login ghcr.io -u syschelle --password-stdin
```

Then retry:

```bash
docker compose -f docker-compose.images.yml pull
```

### GHCR pull returns `manifest unknown`

The requested tag does not exist in the registry or has not been published yet.

Check which image is requested:

```bash
docker compose -f docker-compose.images.yml config | grep image:
```

Use a tag that actually exists, preferably a pinned release tag:

```bash
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.289 docker compose -f docker-compose.images.yml pull
```

### Initial install page is not available

The `/install` page and `/api/install` endpoint are available only before the first admin password has been stored. This is expected after installation is complete.

Check auth status from inside the API container:

```bash
docker exec -it gt_api python /app/manage_auth.py status
```

If an admin password already exists, use the normal login page or the Docker recovery helper.

If this is a fresh test system and no data needs to be kept, recreate the database volume and start again:

```bash
docker compose -f docker-compose.images.yml down -v
docker compose -f docker-compose.images.yml up -d
```

Warning: `down -v` deletes the database volume for this stack.

If the install API should be disabled even on fresh systems, set:

```text
INSTALL_API_ENABLED=false
```

### PostgreSQL says `role "growtent" does not exist`

This usually means the database volume was initialized previously with different credentials or roles.

For a fresh installation where no data needs to be kept, recreate the database volume:

```bash
docker compose -f docker-compose.images.yml down -v
docker compose -f docker-compose.images.yml up -d
```

Warning: `down -v` removes named volumes and deletes the database data for this stack.

For an existing installation where data must be kept, inspect the available roles first:

```bash
docker exec -it gt_db sh -lc 'psql -d postgres -c "\du"'
```

Then repair the database role with the correct superuser for that database.

### PostgreSQL password changes do not take effect

`POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` are used by the PostgreSQL image only when the database directory is initialized for the first time. They do not rewrite an existing database volume.

If you change credentials in Compose after the database has already been initialized, update the database role itself or recreate the database volume.

### API startup fails with database connection errors

Check API logs:

```bash
docker logs --tail=100 gt_api
```

Check database health:

```bash
docker compose -f docker-compose.images.yml ps db
docker logs --tail=100 gt_db
```

Check the API database URL:

```bash
docker inspect gt_api --format '{{range .Config.Env}}{{println .}}{{end}}' | grep DATABASE_URL
```

There is no safe default database URL. The value must come from your deployment-specific `.env` file and should match your `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` settings.

### Admin login no longer works

Reset the admin password from Docker:

```bash
printf '%s' '<new-admin-password>' | docker exec -i gt_api python /app/manage_auth.py set-admin --password-stdin --disable-2fa
```

Check the configured username:

```bash
docker exec -it gt_api python /app/manage_auth.py status
```

If the username was changed, either log in with that username or set it explicitly:

```bash
printf '%s' '<new-admin-password>' | docker exec -i gt_api python /app/manage_auth.py set-admin --username 'admin' --password-stdin --disable-2fa
```

### Controller shows offline or stale data

Check:

- controller base URL in setup
- network route from API container to the controller
- controller `/api/state` and `/api/stats` availability
- polling errors page at `/poll-errors`
- API logs for request timeouts or payload parsing errors

Useful checks:

```bash
docker logs --tail=100 gt_api
curl -i http://127.0.0.1:8088/poll-errors
```

### Camera preview does not work

Check:

- `gt_go2rtc` is running
- API has `GO2RTC_BASE_URL=http://go2rtc:1984`
- camera stream source is configured correctly
- go2rtc does not need to be published to the host for internal API access

```bash
docker compose -f docker-compose.images.yml ps go2rtc
docker logs --tail=100 gt_go2rtc
```

### Pump or irrigation action does nothing

Check:

- the controller supports the requested pump/irrigation action endpoint
- the pump relay/channel index matches the actual wiring
- the pump power supply is active and correctly rated
- water tubing is primed and not blocked
- dry-run protection or external safety logic is not preventing operation
- the controller logs show the action request

Use pump test actions only after the water path is physically safe.

---

## Safety notes

Grow environments combine water, electricity, pumps, heaters, lights, and automation. Treat all relay and pump controls as potentially hazardous.

- use proper electrical enclosures
- keep mains voltage away from water paths
- use suitable fuses and residual-current protection where applicable
- never rely only on software for critical safety shutoffs
- test manually before enabling unattended operation
- verify fail-safe behavior for pumps, lights, fans, and heaters

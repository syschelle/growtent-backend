# GrowTent Backend (CanopyOps)

A Dockerized backend + web app to monitor and control one or more GrowTent controllers from a single interface.

This project only works with controller firmware/API compatible with the `syschelle/GrowTent` repository: https://github.com/syschelle/GrowTent

## What this project is for

This project is designed to make day-to-day grow operations reliable and fast:

- **One dashboard for multiple tents**
- **Live environmental monitoring** (temperature, humidity, VPD)
- **History and trend analysis** (raw + smoothed series)
- **Direct Shelly integration** for power/state visibility and control
- **Irrigation and VPD planning tools** (including 8x-specific workflows)
- **Simple setup and secure access control** (admin/guest roles, optional 2FA)

In short: it is the operational backend/UI layer between your GrowTent devices and your daily decisions.

---

## What it can do

### Monitoring
- Live tent status from controller `/api/state`
- Historical charts for temperature, humidity, VPD, external temp, alpha, and power
- CSV export endpoint (`/api/export`)
- Relative and explicit timestamps to evaluate data freshness
- Warmup overlays in history charts while initial points are still building

### Shelly integration
- Direct Shelly reads for configured devices (`state`, `W`, `Wh`)
- Device toggles and last-switch information
- Energy and cost display in dashboard cards
- Support for Shelly Gen1 and Gen2 patterns

### Camera preview
- Tent preview endpoint via API proxy:
  - `GET /tents/{tent_id}/preview`
- Works on same app domain (no direct external go2rtc exposure required)

### Setup & access
- Setup UI for tents, auth, language/theme/unit preferences
- Admin and guest mode separation (guest is read-only)
- Backup/export + restore/import of configuration

### Operations
- Docker Compose deployment
- Health endpoint: `GET /health`
- Changelog and versioned release workflow
- Startup resilience: last known values are preserved when controller payloads are temporarily incomplete/null

---

## Scope and baseline requirements

The original project scope includes:

- Multi-tent management with clear identity per tent (name, source, status)
- Persistent measurement/status storage in a relational database
- Historical retrieval (latest state and time-series history)
- No InfluxDB and no Grafana (API + relational DB + custom UI stack)
- Docker-first operation (`docker compose up -d --build`)
- Lightweight architecture with a modern usable web UI
- Initial polling source for the first tent: `http://192.168.178.32/api/state`

Status note:
- The current stack includes API + PostgreSQL + go2rtc.
- MQTT broker support is part of the broader target scope and should be treated as a planned/optional expansion unless explicitly enabled in deployment.

---

## Architecture (current)

The codebase is in incremental migration from a monolithic app file to modular FastAPI components:

- `api/main.py` - app bootstrap
- `api/routes/*` - HTTP route groups
- `api/services/*` - business logic
- `api/db/*` - DB layer
- `api/core/*`, `api/models/*` - shared infrastructure and schemas

Persistence is PostgreSQL; service stack runs via Docker Compose.

---

## Quick start

```bash
cd growtent-backend-poc
docker compose up -d --build
```

## Updating from GitHub (production)

If your production folder is already connected to this repository:

```bash
git pull origin main
docker compose up -d --build api
```

If your folder exists but is not connected to Git yet (one-time setup):

```bash
cd /path/to/growtent-backend
git init
git remote add origin git@github.com:syschelle/growtent-backend.git
git fetch origin
git reset --hard origin/main
```

Verify:

```bash
curl http://localhost:8088/health
```

Expected:

```json
{"ok":true}
```

Open:
- App shell: `http://<server-ip>:8088/app?page=dashboard`
- Setup: `http://<server-ip>:8088/setup`
- Changelog: `http://<server-ip>:8088/changelog`

---

## Requirements

- Docker Engine + Docker Compose
- Reachability from API container to:
  - GrowTent controllers (`/api/state`)
  - Shelly devices
  - RTSP source(s), if preview is used

System prerequisite:
- This backend requires the controller firmware/API from:
  https://github.com/syschelle/GrowTent
- Without that repository/firmware baseline, core features (state polling, relay actions, planning integration) are not guaranteed to work correctly.

---

## Project status

Actively developed with versioned incremental changes.
Primary goals are:

1. Keep existing behavior stable
2. Improve reliability and UX iteratively
3. Continue modularization without breaking API compatibility

See `CHANGELOG.md` for detailed version history and feature evolution.

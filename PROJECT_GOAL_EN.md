# CanopyOps — Permanent System Description (EN)

## Project Goal
CanopyOps is a Dockerized multi-tent backend for GrowTent controllers, focused on stable operation, clear usability, and fast diagnostics.

The platform consolidates multiple tents into one interface and combines live status, history, direct Shelly control, camera previews, setup flow, and authentication.

### Current focus
- direct Shelly integration for **all relevant device values** (state/Watt/Wh) instead of delayed state-only reads
- reliable energy history, including spike filtering for charts and exports
- multilingual, mobile-friendly UI (DE/EN)
- 2FA-capable access with clean setup/login flows
- tent-specific irrigation planning + min. VPD monitoring (8x-specific)

## Technical Implementation
- FastAPI app with modularized structure:
  - `api/main.py` (app bootstrap)
  - `api/routes/*` (endpoint groups)
  - `api/services/*` (business logic)
  - `api/db/*` (database access and queries)
  - `api/models/*`, `api/core/*`
- PostgreSQL persistence for tent metadata, historical states, and planning data
- Controller polling via `/api/state` (UI uses no-cache strategy)
- Direct Shelly access (Gen1/Gen2) with auth candidate strategy (Basic/Digest/fallback)
- RTSP preview integration via go2rtc
- Deployment via Docker Compose
- DE/EN UI with theme support, responsive layout, and app-shell navigation

## Core Features
- Multi-tent dashboard with live values, history charts, and relative update times
- Shelly device cards with toggles, ON/OFF schedule display, and energy/cost values
- Direct aggregate Shelly read (`direct-all`) for UI freshness
- Total-consumption history based on Shelly main data (instead of ESP32 fallback)
- CSV export endpoint (`/api/export`) with raw + smoothed sensor columns
- Camera preview per active tent (bandwidth-friendly)
- Setup flow for tents, auth/2FA, language/theme/units
- 8x-specific features (tank, pump/relays, irrigation plan, min. VPD monitoring)

## System Requirements
### Runtime
- Docker Engine + Docker Compose plugin
- Network reachability from API container to:
  - ESP32 controller APIs (`/api/state`, action endpoints)
  - Shelly devices (HTTP/RPC, Gen1/Gen2)
  - RTSP source(s) for go2rtc

### Firmware Prerequisite (ESP32 Relay Boards)
- The backend expects compatibility with:
  - `https://github.com/syschelle/GrowTent`
- Required API structures/keys include status/settings payloads, Shelly mappings, and action endpoints.
- Without compatible firmware from that repository, parts of dashboard logic (especially relay/Shelly/planning) may be limited.

### Default Ports
- `8088/tcp` → CanopyOps API/UI (`gt_api`)
- `1984/tcp` → go2rtc Web/API (`gt_go2rtc`)
- `8554/tcp` → RTSP (`gt_go2rtc`)
- PostgreSQL internal via Compose network (`gt_db`)

### Software Stack
- Python 3.12 (container base)
- FastAPI + Uvicorn
- PostgreSQL
- go2rtc

### Persistence & Operations
- History retention defaults to `RETENTION_DAYS=7`
- UI time display uses relative labels (“ago”) plus explicit status timestamps
- Version/changelog maintenance is part of ongoing operations

## Running Services
- `gt_api` (FastAPI) on port `8088`
- `gt_db` (PostgreSQL)
- `gt_go2rtc` on ports `1984` and `8554`

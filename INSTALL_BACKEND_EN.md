# GrowTent Backend PoC - Installation Guide (English)

This guide explains how to install and run the dockerized GrowTent backend.

## 1) Requirements

- Docker Engine (24+ recommended)
- Docker Compose plugin
- Network access to your ESP32 devices (`/api/state` endpoint)

## 2) Project layout

Main components:

- `api/` → FastAPI backend + UI
- `docker-compose.yml` → stack orchestration
- `CHANGELOG.md` → project description + version history

## 3) Start the stack

```bash
cd growtent-backend-poc
docker compose up -d --build
```

## 4) Verify services

```bash
docker compose ps
curl http://localhost:8088/health
```

Expected health response:

```json
{"ok": true}
```

## 5) Open UI

- Dashboard: `http://<server-ip>:8088/dashboard`
- Setup: `http://<server-ip>:8088/setup`
- Changelog: `http://<server-ip>:8088/changelog`

## 6) Configure tents

Open **Setup** and add one or more tents with:

- Tent name
- Source URL (ESP32): `http://<esp-ip>/api/state`
- Optional RTSP URL

## 7) Common operations

Restart backend:

```bash
docker compose up -d --build api
```

Full restart:

```bash
docker compose down
docker compose up -d --build
```

## 8) Download full project package

Use:

- `http://<server-ip>:8088/download/project.zip`

The ZIP includes project files and this installation guide.

## 9) Notes

- If UI changes are not visible, hard-refresh the browser (`Ctrl+F5`).
- If ESP32 is offline, the backend still runs but polling logs connection errors.

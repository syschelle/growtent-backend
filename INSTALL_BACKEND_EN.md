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
# Anonymous HTTP health requests are blocked by mandatory login since v0.408.
# Check container readiness and logs instead:
docker compose ps
docker logs --tail 50 gt_api
```

Application content and the health API require an authenticated session. Do not treat an anonymous HTTP 401 as a container crash.

## 5) Open UI

- Initial install: `http://<server-ip>:8088/install` (fresh database only)
- Dashboard: `http://<server-ip>:8088/app?page=dashboard`
- Setup: `http://<server-ip>:8088/setup`
- Changelog: `http://<server-ip>:8088/changelog`

## 6) Initial admin account and tent configuration

On a fresh installation, open **Initial install** first and create the first admin username and password. After that, `/install` and `/api/install` are no longer available. Admin passwords are stored as Argon2id hashes.

Then open **Setup** and add one or more tents with:

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

- `http://<server-ip>:8088/download/project.zip` (disabled by default; requires a sanitized optional `/project` mount)

The ZIP includes project files and this installation guide.

## 9) Notes

- If UI changes are not visible, hard-refresh the browser (`Ctrl+F5`).
- If ESP32 is offline, the backend still runs but polling logs connection errors.


## Production secrets

Before starting Docker Compose, create a `.env` file from `.env.example` and replace all placeholder values. The initial install page requires the `INSTALL_API_TOKEN` value by default. **v0.413 also requires `GT_DATA_ENCRYPTION_KEY`**; generate a Fernet key and keep it separately from DB/backups. Existing plaintext secrets migrate transactionally on first start. Retain a pre-upgrade DB backup and never lose/change the key (see `README.md`).

## v0.414 reverse-proxy and login protection

For HTTPS deployments behind Traefik, keep the API port private and set `GT_TRUSTED_PROXY_CIDRS` in `.env` **only** to the verified immediate proxy IP(s), such as an exact `/32` address. Never use a wildcard or the whole Docker network. The API processes `X-Forwarded-For` itself and ignores it when the immediate peer is untrusted; Uvicorn runs with `--no-proxy-headers`. The new TOTP replay table is created automatically during normal database startup. A 2FA code already used during login cannot be reused in a subsequent step-up dialog; use the next 30-second code.

## v0.415 browser and container hardening

The API now serves an enforced Content Security Policy for audited application
scripts and headers on both successful and denied responses. `GT_HSTS_MAX_AGE=0`
is the default; enable HSTS on a verified HTTPS-only Traefik router (or set a
backend max-age) after checking the public hostname. API Compose adds a
read-only root filesystem, /tmp tmpfs, capability dropping and no-new-privileges
without changing existing `./data` owners or automatically switching UID.
`GT_TRUSTED_PROXY_CIDRS` remains optional and must reflect the real immediate
proxy hop, wherever the reverse proxy runs. See `docs/security-deployment.md`.

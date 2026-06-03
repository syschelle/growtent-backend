# GrowTent Backend (CanopyOps)

A Dockerized backend and web app to monitor and control one or more GrowTent controllers from a single interface.

This project is designed for controller firmware/API compatible with the `syschelle/GrowTent` repository:

- https://github.com/syschelle/GrowTent

<img width="1851" height="1038" alt="GrowTent dashboard screenshot" src="https://github.com/user-attachments/assets/8fc28274-daa2-48d6-93c0-1ed54d989c6e" />

---

## What this project is for

GrowTent Backend is the operational backend/UI layer between your GrowTent devices and your daily decisions.

It provides:

- one dashboard for multiple tents
- live environmental monitoring
- historical charts and CSV export
- Shelly power/state integration
- camera preview through an API proxy
- setup UI for tents, auth and preferences
- admin/guest access separation
- optional two-factor authentication
- Docker-first deployment for small servers, Raspberry Pi and x86 hosts

The current production stack consists of:

- **API/UI**: FastAPI app, exposed on host port `8088`
- **PostgreSQL**: internal database service
- **go2rtc**: internal camera/stream helper service

---

## Features

### Monitoring

- live tent status from controller `/api/state`
- historical charts for temperature, humidity, VPD, external temperature, alpha and power values
- raw and smoothed history series
- CSV export endpoint: `/api/export`
- relative and explicit timestamps to evaluate data freshness
- warmup overlays while initial history points are still building
- startup resilience when controller payloads are temporarily incomplete or contain `null` values

### Shelly integration

- direct Shelly reads for configured devices
- support for common Gen1 and Gen2 Shelly response patterns
- device state, current power and energy values
- last-switch information
- dashboard cards for power and cost visibility

### Camera preview

Camera preview is handled through the backend API.

The API talks to go2rtc internally via:

```text
http://go2rtc:1984
```

The browser does **not** need direct access to go2rtc. This allows go2rtc to stay internal to the Docker network.

Preview endpoint:

```text
GET /tents/{tent_id}/preview
```

### Setup and access control

- setup UI for tents, authentication, language/theme/unit preferences
- admin and guest mode separation
- guest mode is read-only
- optional 2FA
- backup/export and restore/import of configuration
- Docker command for recovering or changing admin credentials if you lock yourself out

---

## Network and security model

By default, only the API is published to the host.

| Service | Internal address | Published to host | Purpose |
|---|---:|---:|---|
| API/UI | `api:8080` | `8088:8080` | Web UI and API |
| PostgreSQL | `db:5432` | no | internal database |
| go2rtc | `go2rtc:1984`, `go2rtc:8554` | no | internal camera/stream helper |

Expected external access:

```text
http://<server-ip>:8088
```

Expected internal Docker access:

```text
http://api:8080
http://go2rtc:1984
postgresql://growtent:growtent@db:5432/growtent
```

`go2rtc` and PostgreSQL should not be reachable directly from outside Docker.

To verify this after deployment:

```bash
docker port gt_api
docker port gt_go2rtc
docker port gt_db
ss -tulpn | grep -E ':8088|:1984|:8554|:5432' || true
```

Expected result:

- `gt_api` publishes `8080/tcp -> 0.0.0.0:8088` and usually also `[::]:8088`
- `gt_go2rtc` prints no published ports
- `gt_db` prints no published ports
- `ss` shows only `8088` for this stack

If `1984` or `8554` still appears, see [Troubleshooting: go2rtc ports are still exposed](#go2rtc-ports-are-still-exposed).

---

## Deployment modes

There are two supported Docker Compose modes.

### 1. Production: use prebuilt images

Use this mode for normal deployments and releases.

File:

```text
docker-compose.images.yml
```

The API image is pulled from GHCR instead of being built on the target host.

Default image:

```text
ghcr.io/syschelle/growtent-backend-api:latest
```

Recommended pinned image for deterministic deployments:

```text
ghcr.io/syschelle/growtent-backend-api:v0.247
```

The image is built as a multi-arch manifest for:

- `linux/amd64`
- `linux/arm64`

This means the same image tag works on x86 servers and ARM devices such as Raspberry Pi.

### 2. Development: build locally

Use this when you are actively developing or testing local source changes.

File:

```text
docker-compose.yml
```

Start with local build:

```bash
docker compose up -d --build
```

For production hosts, prefer `docker-compose.images.yml` so the server does not rebuild the API container.

---

## Production quick start with prebuilt images

Clone or update the repository on your server:

```bash
cd /opt
git clone https://github.com/syschelle/growtent-backend.git
cd /opt/growtent-backend
```

Start the stack using the published image:

```bash
docker compose -f docker-compose.images.yml pull
docker compose -f docker-compose.images.yml up -d --remove-orphans
```

Open:

```text
http://<server-ip>:8088/app?page=dashboard
```

Setup page:

```text
http://<server-ip>:8088/setup
```

Health check:

```bash
curl -i http://127.0.0.1:8088/health
```

Expected:

```text
HTTP/1.1 200 OK
```

---

## Deploy a pinned release image

For production, a pinned release is safer than `latest` because you know exactly which version is running.

Example for `v0.247`:

```bash
cd /opt/growtent-backend

GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.247 \
  docker compose -f docker-compose.images.yml pull

GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.247 \
  docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Verify:

```bash
docker compose -f docker-compose.images.yml ps
docker port gt_api
curl -i http://127.0.0.1:8088/health
```

---

## Update an existing image-based installation

Using `latest`:

```bash
cd /opt/growtent-backend
git pull origin main
docker compose -f docker-compose.images.yml pull
docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Using a pinned release:

```bash
cd /opt/growtent-backend
git pull origin main

GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.247 \
  docker compose -f docker-compose.images.yml pull

GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.247 \
  docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Why `--force-recreate` matters:

Docker does not remove old port mappings from an existing container. If an older container exposed go2rtc on `1984` and `8554`, it must be recreated before those host ports disappear.

---

## GHCR access

If the GHCR package is public, Docker can pull it without authentication.

If the package is private, log in on the server first with a GitHub classic Personal Access Token that has at least `read:packages`:

```bash
echo "$CR_PAT" | docker login ghcr.io -u syschelle --password-stdin
```

Then pull again:

```bash
docker compose -f docker-compose.images.yml pull
```

Common GHCR errors:

| Error | Meaning | Fix |
|---|---|---|
| `denied` | package is private or login is missing | make package public or run `docker login ghcr.io` |
| `manifest unknown` | tag does not exist | wait for GitHub Actions or use an existing tag |
| `unauthorized` | token/login is invalid | recreate PAT with `read:packages` |

---

## Release workflow

The repository contains a GitHub Actions workflow:

```text
.github/workflows/docker-api.yml
```

On a version tag like `v0.247`, it builds and pushes:

```text
ghcr.io/syschelle/growtent-backend-api:v0.247
ghcr.io/syschelle/growtent-backend-api:latest
```

for:

```text
linux/amd64
linux/arm64
```

Release steps:

```bash
git status
git add .
git commit -m "fix(compose): keep go2rtc internal"
git push origin main

git tag -a v0.247 -m "Release v0.247"
git push origin v0.247
```

Then check:

```text
GitHub → Repository → Actions → Build API Docker image
```

After the workflow succeeds, the image tags should be available under:

```text
GitHub → Packages → growtent-backend-api
```

---

## Local development quick start

Use the local-build Compose file:

```bash
cd growtent-backend
docker compose up -d --build
```

Open:

```text
http://localhost:8088/app?page=dashboard
```

Stop:

```bash
docker compose down
```

View logs:

```bash
docker logs -f gt_api
docker logs -f gt_db
docker logs -f gt_go2rtc
```

---

## Configuration

Main environment variables used by the API service:

| Variable | Default/example | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql://growtent:growtent@db:5432/growtent` | PostgreSQL connection string |
| `POLL_INTERVAL_SECONDS` | `10` | polling interval for controller state reads |
| `RETENTION_DAYS` | `7` | history retention window |
| `GO2RTC_BASE_URL` | `http://go2rtc:1984` | internal go2rtc base URL |
| `PROJECT_ROOT` | `/project` | mounted project path used by app tooling |
| `GT_API_IMAGE` | `ghcr.io/syschelle/growtent-backend-api:latest` | optional image override for `docker-compose.images.yml` |

---

## Data persistence

The Compose files use a Docker named volume for PostgreSQL:

```yaml
volumes:
  db_data:
```

The database data lives inside Docker's managed volume storage. Do not remove this volume unless you intentionally want to reset the database.

Check volumes:

```bash
docker volume ls | grep growtent
```

Backup example:

```bash
docker exec gt_db pg_dump -U growtent -d growtent > growtent-backup.sql
```

Restore example into an existing database:

```bash
cat growtent-backup.sql | docker exec -i gt_db psql -U growtent -d growtent
```

Reset everything, including database data:

```bash
docker compose -f docker-compose.images.yml down -v
```

Be careful: `down -v` removes named volumes and therefore deletes the PostgreSQL database for this stack.

---

## Admin password reset / Docker command

If you lock yourself out, you can inspect or reset the admin login from inside the API container.

Check current auth status without exposing password hashes:

```bash
docker compose -f docker-compose.images.yml exec api python manage_auth.py status
```

Reset the password for the currently configured admin username and disable 2FA recovery state:

```bash
printf '%s' 'DeinNeuesPasswort' | \
  docker compose -f docker-compose.images.yml exec -T api \
  python manage_auth.py set-admin --password-stdin --disable-2fa
```

Reset password and set/change the admin username at the same time:

```bash
printf '%s' 'DeinNeuesPasswort' | \
  docker compose -f docker-compose.images.yml exec -T api \
  python manage_auth.py set-admin --username 'MeinAdminName' --password-stdin --disable-2fa
```

Alternatively, use the fixed container name:

```bash
printf '%s' 'DeinNeuesPasswort' | \
  docker exec -i gt_api \
  python /app/manage_auth.py set-admin --username 'MeinAdminName' --password-stdin --disable-2fa
```

For an interactive prompt while keeping the currently configured username:

```bash
docker compose -f docker-compose.images.yml exec api \
  python manage_auth.py set-admin --prompt-password --disable-2fa
```

---

## Verify deployment

Use this checklist after a deployment or release update:

```bash
cd /opt/growtent-backend

docker compose -f docker-compose.images.yml ps
docker logs --tail=80 gt_api
docker logs --tail=80 gt_db
docker logs --tail=80 gt_go2rtc
curl -i http://127.0.0.1:8088/health
```

Verify published ports:

```bash
docker port gt_api
docker port gt_go2rtc
docker port gt_db
ss -tulpn | grep -E ':8088|:1984|:8554|:5432' || true
```

Expected:

```text
8080/tcp -> 0.0.0.0:8088
8080/tcp -> [::]:8088
```

No published ports should be printed for `gt_go2rtc` or `gt_db`.

---

## Troubleshooting

### API does not start: database login failed

Symptoms in `docker logs gt_api`:

```text
psycopg2.OperationalError: password authentication failed for user "growtent"
```

or in `docker logs gt_db`:

```text
FATAL: role "growtent" does not exist
```

Most common cause: an old PostgreSQL data volume or data directory was initialized with different credentials. `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` are only applied when PostgreSQL initializes an empty data directory for the first time.

For a fresh install where data can be deleted:

```bash
docker compose -f docker-compose.images.yml down -v
docker compose -f docker-compose.images.yml up -d
```

For an existing install with data that should be kept, inspect roles first:

```bash
docker exec -it gt_db sh -lc 'psql -d postgres -c "\\du"'
```

If a known superuser exists, use it to create or fix the `growtent` role and database.

### go2rtc ports are still exposed

Symptoms:

```bash
docker port gt_go2rtc
```

prints:

```text
1984/tcp -> 0.0.0.0:1984
8554/tcp -> 0.0.0.0:8554
```

This means Docker is still running a container created from an older Compose configuration, or your active Compose file still contains `ports:` for `go2rtc`.

Check the effective Compose config:

```bash
docker compose -f docker-compose.images.yml config | grep -A25 "go2rtc:"
```

There must be no `ports:` section under `go2rtc`.

Search all Compose files for old port mappings:

```bash
grep -Rni --include='*.yml' --include='*.yaml' -E '1984|8554|go2rtc|ports:' .
```

Then remove old containers and recreate:

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

Expected: no output.

### API port `8088` is not visible

Check that the effective Compose config contains the API port mapping:

```bash
docker compose -f docker-compose.images.yml config | grep -A30 "api:"
```

Expected:

```yaml
ports:
  - mode: ingress
    target: 8080
    published: "8088"
```

Recreate the API container:

```bash
docker compose -f docker-compose.images.yml rm -sf api
docker compose -f docker-compose.images.yml up -d api
```

Then verify:

```bash
docker port gt_api
curl -i http://127.0.0.1:8088/health
```

### GHCR pull fails

If you see:

```text
denied
```

then the package is probably private or the server is not logged in.

Fix:

```bash
echo "$CR_PAT" | docker login ghcr.io -u syschelle --password-stdin
```

If you see:

```text
manifest unknown
```

then the tag does not exist yet. Check GitHub Actions and Packages. Make sure the release tag was pushed after the workflow file existed.

### Show container origin and port bindings

This helps identify which Compose file created a container:

```bash
docker inspect gt_go2rtc --format 'Project={{index .Config.Labels "com.docker.compose.project"}} Files={{index .Config.Labels "com.docker.compose.project.config_files"}} Service={{index .Config.Labels "com.docker.compose.service"}} PortBindings={{json .HostConfig.PortBindings}}'
```

---

## Important URLs

Health:

```text
http://<server-ip>:8088/health
```

Dashboard:

```text
http://<server-ip>:8088/app?page=dashboard
```

Setup:

```text
http://<server-ip>:8088/setup
```

Changelog:

```text
http://<server-ip>:8088/changelog
```

---

## Project scope and baseline requirements

The original project scope includes:

- multi-tent management with clear identity per tent
- persistent measurement/status storage in a relational database
- historical retrieval for latest state and time-series history
- API + relational DB + custom UI stack
- no InfluxDB and no Grafana requirement
- Docker-first operation
- lightweight architecture with a modern usable web UI
- initial polling source for the first tent: `http://192.168.178.32/api/state`

Status note:

- The current stack includes API + PostgreSQL + go2rtc.
- MQTT broker support is part of the broader target scope and should be treated as planned or optional unless explicitly enabled in deployment.

---

## Architecture

The codebase is being incrementally migrated from a monolithic app file to modular FastAPI components:

```text
api/main.py           app bootstrap
api/app.py            legacy/main application module
api/routes/*          HTTP route groups
api/services/*        business logic helpers
api/db/*              database layer
api/core/*            shared infrastructure
api/models/*          schemas
api/static/*          bundled static assets
api/manage_auth.py    admin credential recovery helper
```

Persistence is PostgreSQL. The service stack runs via Docker Compose.

---

## License

See `LICENSE`.

# Deploying GrowTent Backend with prebuilt images

This deployment mode pulls a prebuilt API image from GHCR instead of building the API on the target host. It is intended for Raspberry Pi / ARM systems as well as x86 servers.

## Security model

Only the API is published to the host by default:

- API/UI: `8088:8080`

The following services stay internal to the Docker Compose network:

- PostgreSQL: `db:5432`, no host port
- go2rtc: `go2rtc:1984` / `go2rtc:8554`, no host port

The Compose files do not ship usable default database credentials. You must provide a deployment-specific `.env` file before starting the stack.

## Required `.env` file

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` and replace every `REPLACE_WITH_*` value. Use long random secrets. Do not reuse the examples in production.

Generate example values:

```bash
openssl rand -base64 36
openssl rand -base64 48
```

Required variables:

```text
POSTGRES_DB=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
DATABASE_URL=postgresql://<db-user>:<url-encoded-db-password>@db:5432/<db-name>
INSTALL_API_TOKEN=<long-random-first-run-token>
```

Important: if the database password contains special characters, URL-encode it in `DATABASE_URL`.

## Image tags

The image-based Compose file defaults to the moving latest API image:

```text
ghcr.io/syschelle/growtent-backend-api:v0.298
```

For deterministic deployments, pin a specific version with `GT_API_IMAGE`, for example:

```text
ghcr.io/syschelle/growtent-backend-api:v0.298
```

go2rtc is pinned in the Compose files as an immutable reference instead of `latest`:

```text
alexxit/go2rtc:1.9.14@sha256:f0579db234b4f9e8630493777dbf8581630d5d942d27b884ac9186f3d688e7bf
```

Override `GO2RTC_IMAGE` only deliberately for controlled upgrades.

## Server deployment

Use the current release image explicitly:

```bash
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.298 docker compose -f docker-compose.images.yml pull
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.298 docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Or use the image configured in `.env` / Compose:

```bash
docker compose -f docker-compose.images.yml pull
docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

If GHCR is private, log in on the server first:

```bash
echo "$CR_PAT" | docker login ghcr.io -u syschelle --password-stdin
```

The token needs `read:packages`.

## First browser access

On a fresh database volume, open the initial install page first:

```text
http://<server-ip>:8088/install
```

Create the first admin username and password there. The install form asks for the first-run install token from `.env` (`INSTALL_API_TOKEN`). After this step, `/install` and `/api/install` are no longer available and normal access continues through `/auth/login`, `/app`, and `/setup`.

Admin passwords, guest passwords, and 2FA recovery codes are stored as Argon2id hashes. Legacy password hash formats are intentionally not accepted or migrated; use `manage_auth.py set-admin` to reset access after upgrading an older database.

## Verify

```bash
docker compose -f docker-compose.images.yml ps
docker port gt_api
docker port gt_go2rtc
docker port gt_db
curl -i http://127.0.0.1:8088/health
ss -tulpn | grep -E ':8088|:1984|:8554|:5432' || true
```

Expected:

- `gt_api` shows `8080/tcp -> 0.0.0.0:8088` and/or `[::]:8088`
- `gt_go2rtc` prints no published ports
- `gt_db` prints no published ports
- `/health` returns HTTP 200
- for this stack, only `8088` is listening on the host

## If go2rtc ports are still visible

Docker does not remove port mappings from an already-created container. Recreate the stack:

```bash
docker compose -f docker-compose.images.yml down --remove-orphans
docker rm -f gt_go2rtc gt_api gt_db 2>/dev/null || true
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.298 docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Then verify again with `docker port` and `ss`.

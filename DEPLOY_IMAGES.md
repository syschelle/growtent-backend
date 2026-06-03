# Deploying GrowTent Backend with prebuilt images

This deployment mode pulls a prebuilt API image from GHCR instead of building the API on the target host.
It is intended for Raspberry Pi / ARM systems as well as x86 servers.

## Published host ports

Only the API is published to the host:

- API: `8088:8080`

The following services are internal-only in Docker Compose:

- PostgreSQL: internal `db:5432`, no host port
- go2rtc: internal `go2rtc:1984` / `go2rtc:8554`, no host port

## Image tags

The image-based Compose file defaults to:

```text
ghcr.io/syschelle/growtent-backend-api:latest
```

For deterministic deployments, pin a specific version with `GT_API_IMAGE`, for example:

```text
ghcr.io/syschelle/growtent-backend-api:v0.249
```

## Server deployment

Use the pinned release image:

```bash
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.249 docker compose -f docker-compose.images.yml pull
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.249 docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Or use `latest`:

```bash
docker compose -f docker-compose.images.yml pull
docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

If GHCR is private, log in on the server first:

```bash
echo "$CR_PAT" | docker login ghcr.io -u syschelle --password-stdin
```

The token needs `read:packages`.

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
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.249 docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
```

Then verify again with `docker port` and `ss`.

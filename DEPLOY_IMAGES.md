# Deploying GrowTent Backend with prebuilt images

This deployment mode pulls the prebuilt API image from GHCR instead of building on the target host.

## Published host ports

Only the API is published to the host:

- API: `8088:8080`

The following services are internal-only in Docker Compose:

- PostgreSQL: internal `db:5432`, no host port
- go2rtc: internal `go2rtc:1984` / `go2rtc:8554`, no host port

## Release build

Commit and tag the release:

```bash
git add .
git commit -m "fix(compose): keep go2rtc internal"
git push origin main
git tag -a v0.247 -m "Release v0.247"
git push origin v0.247
```

The GitHub Actions workflow builds and pushes:

- `ghcr.io/syschelle/growtent-backend-api:v0.247`
- `ghcr.io/syschelle/growtent-backend-api:latest`

for `linux/amd64` and `linux/arm64`.

## Server deployment

Use the pinned release image:

```bash
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.247 docker compose -f docker-compose.images.yml pull
GT_API_IMAGE=ghcr.io/syschelle/growtent-backend-api:v0.247 docker compose -f docker-compose.images.yml up -d --force-recreate --remove-orphans
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

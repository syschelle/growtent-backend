# v0.415 – Browser headers, HSTS and container hardening

## CSP in production

The backend applies the same **enforced** `Content-Security-Policy` to the
login/install screens, authenticated pages, embedded iframe pages, static assets
and API error responses, whether you use the modular `main:app` or legacy app.
It permits only same-origin JavaScript files and SHA-256 hashes of the *trusted
inline scripts in repository templates*. It explicitly blocks inline event
handler attributes, third-party script origins, `<object>` and foreign iframes.
Script hashes are **not** computed from incoming requests or rendered user data:
that would authorize an injected `<script>` tag. If a template script changes,
regenerate `api/services/csp_script_hashes.json` from audited code using:

```bash
python scripts/generate_csp_hashes.py
python scripts/generate_csp_hashes.py --check
```

The existing inline CSS and dynamic viewer styles still require `style-src
'unsafe-inline'`; this is not a fully nonce-only CSP. The app shell's same-origin
iframes, embedded dashboard, Original/HDR image/data URLs, 2FA, theme scripts,
local audio and mobile fullscreen are explicitly supported. The policy does
**not** upgrade HTTP links to ESP controllers, because those may only support
LAN HTTP. No remote JavaScript origin is permitted.

Inspect browser DevTools for `Content Security Policy` violations after update;
if something breaks, fix the trusted template and regenerate the hashes rather
than disabling the whole policy or adding `script-src 'unsafe-inline'`.

## HSTS (HTTPS only)

`GT_HSTS_MAX_AGE=0` (default) deliberately leaves HSTS off, so local HTTP
installations and unrelated hostnames are unaffected. For HTTPS-only reverse
proxy deployments, set HSTS **on the public HTTPS router** (Traefik example):

```yaml
http:
  middlewares:
    canopyops-hsts:
      headers:
        stsSeconds: 86400
        stsIncludeSubdomains: false
        stsPreload: false
```

Apply `canopyops-hsts@file` only to the appropriate HTTPS router, or configure
`GT_HSTS_MAX_AGE=86400` in `.env` and recreate the API container. A browser
only honors HSTS over HTTPS. Do **not** enable `includeSubdomains` or preload
without verifying all affected subdomains. Once verified, you may increase
`max-age` to 31536000. Do not enable HSTS on arbitrary LAN-only installations.

## Docker hardening

Both Compose variants now restrict **only the API** with `cap_drop: [ALL]`,
`no-new-privileges`, a read-only root filesystem, `pids_limit: 256`, and an
isolated writable `/tmp` tmpfs. The existing writable `./data:/data` mount is
retained because strains.csv and other runtime files live there. PostgreSQL and
go2rtc are left unchanged to avoid breaking persistent data or camera streams.

Existing API containers still run as root by default: automatically changing
UID could break current bind-mount ownership and make migration fail. For a **separately tested opt-in rollout**,
Linux can run the API with numeric UID/GID 10001 even without an `/etc/passwd`
entry. The runtime root filesystem is read-only either way. After backing up the data folder and adjusting its
ownership/ACLs, add an API service override `user: '10001:10001'` and verify
write access to `/data`, camera/ESP endpoints, OTA and backups. Never blindly
`chown -R` a production directory without identifying its existing owners.

The historical `./:/project:ro` mount remains for the optional project download
and changelog route. It is read-only but exposes the repo and possibly `.env`
**inside the container**. `PROJECT_DOWNLOAD_ENABLED=false` remains the
recommended default. The full-repo mount should be removed in a future
separate compatibility-checked release after changing project download behavior;
**do not claim this risk is closed in v0.415.**

`GT_TRUSTED_PROXY_CIDRS` stays optional and is **not** automatically populated.
Use only actual trusted reverse-proxy hop addresses. This works with Traefik
on the same host, another host or with no reverse proxy at all.

## Smoke test after deployment

1. Verify `docker compose -f docker-compose.images.yml config --quiet` before
   recreation. Do not change `GT_DATA_ENCRYPTION_KEY`.
2. Log in with password/2FA; open dashboard, embedded layout, GrowGuide, Setup,
   Original/HDR fullscreen, and hoverable pot labels.
3. Check Shelly lighting schedule, screenshot ZIP, ESP status/HMAC and 2FA QR.
4. Check response headers (authenticated browser): CSP, nosniff, SAMEORIGIN,
   no-referrer; HSTS only after enabling HTTPS-only operation.
5. Check container logs for read-only-file errors. If a write path is found,
   add a **specific** writable mount/tmpfs after review, not a writable rootfs.

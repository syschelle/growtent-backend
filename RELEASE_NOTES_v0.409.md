# GrowTent Backend v0.409 – First hardening follow-up (device URLs and guest camera secrets)

## Security fixes

- **SEC-01 / High:** Guest API responses (`GET /tents`, `GET /tents/{id}/latest`) no longer expose raw RTSP camera URLs or embedded usernames/passwords. The legacy and modular tent paths are covered, while admins may still edit the configured camera URL. Browser camera previews continue through the existing authenticated backend endpoint.
- **SEC-02 / High–Medium:** Strict `rtsp://` / `rtsps://` allowlist for go2rtc registrations, previews and ZIP capture; HTTP(S) controller source URLs reject unsafe schemes, embedded credentials, loopback/link-local/public IPs, and Docker service hosts. Hostnames must resolve to private, non-reserved LAN IPs when saved and before use; backups are checked before database replacement. Previously stored invalid camera URLs no longer reach go2rtc.
- **SEC-03 / Medium:** Controller action forwarding disables HTTP redirects, does not return arbitrary device response bodies or raw target URLs, and returns a generic upstream error instead of exception internals.
- **SEC-04 / Medium:** Camera player/WebRTC URLs no longer derive from the untrusted HTTP Host header or embed RTSP credentials. Optional explicitly configured `GO2RTC_PUBLIC_BASE_URL` requires HTTPS and is used only for admin URLs with the registered stream name `tent_<id>`. Without this option, the already-supported authenticated preview remains active, but raw external player links are not generated. **Do not publish go2rtc directly without its own authentication.**
- **SEC-05 / Defense-in-depth:** Modular tent write routes explicitly require an admin session in addition to the mandatory central authentication middleware.
- **SEC-06 / Low:** CSV imports reject oversized bodies while streaming; installation token is now accepted only in `X-Install-Token` (not URL/query/body); new and changed guest passwords require 8–1024 characters, and admin/login passwords have a 1024-character cap.

## Compatibility

The default API Docker bind address remains `127.0.0.1`, and go2rtc's HTTP port is not host-published in the Compose files. Existing IP-based LAN ESP/controller and RTSP cameras remain supported; URLs using public/Docker-local addresses, alternative stream protocols (including `ffmpeg:`/`exec:`) or unresolvable hostnames must be corrected in Setup. No DB schema or ESP firmware change. JSON/ZIP analysis payloads, irrigation, VPD and camera image processing are unchanged.

## Verification

Local regression coverage includes all existing Python tests (except the optional PostgreSQL integration suite), dedicated guest/URL/redirect tests, five JavaScript suites and browser smoke checks. Docker, live PostgreSQL, production RTSP, Traefik and network egress tests are still required before deployment.

## Security work still open

The remainder of the reported findings are **not resolved by this release**: step-up verification for password/admin/2FA/backup operations; encryption or protected export of backup/database secrets; strict Content-Security-Policy and HTTPS HSTS deployment; proxy-aware, DoS-resistant rate limiting and TOTP replay protection; moving 2FA enrollment QR payloads off GET query strings; deployment non-root/least-privilege, bind mounts, dependency pinning; and complete error-message redaction. See `GrowTent_Security_Followup_v0.409.md` for priorities. The source URL allowlist is defense-in-depth: restrict container egress to trusted devices to prevent DNS rebinding and private-network SSRF. No penetration test has been performed.

# GrowTent Security Follow-up — v0.409

The externally supplied 10-point report was checked against the v0.408 source. This table differentiates confirmed changes in v0.409 from work that still needs implementation and deployment verification.

| # | Finding | v0.409 status | Next action |
|---|---|---|---|
| 1 | Guest RTSP credentials in `/tents` and `/latest` | **Fixed in both modular and legacy handlers;** player URLs no longer include credentials | Audit all other read-only API responses; verify that go2rtc remains internal/authenticated |
| 2 | Dangerous RTSP/HTTP controller sources and SSRF with response body | **Partial mitigation:** strict schemes, LAN source validation, no redirects, no response-body/target echo, and backup check | Add egress network policy and DNS pinning; staging-test existing device URLs and alternate RTSP protocols |
| 3 | Missing step-up authentication | **Open** | Require password or TOTP for password/admin/2FA and sensitive backup actions; add dialogs and session-level expiry |
| 4 | Plaintext database and backup secrets | **Open** | Use environment-backed encryption with tested key rotation and backward-compatible data migration, plus encrypted or redacted backup strategy |
| 5 | CSP/HSTS missing | **Open** | Introduce nonce-based CSP after removing inline handlers/scripts; configure HSTS on HTTPS Traefik edge |
| 6 | Shared-proxy rate-limit DoS / timing / TOTP reuse | **Open** | Trust only configured proxy IPs for forwarded client identity, distributed storage, dummy Argon2 verification and one-time TOTP acceptance |
| 7 | TOTP enrollment secret in QR URL | **Open** | Use short-lived server-side opaque enrollment token, POST, no secret in URLs/history/logs |
| 8 | Middleware-only route authorization | **Partially fixed** on modular tent mutation routes | Extend explicit endpoint dependencies to system/admin routers and legacy public functions |
| 9 | Docker root, whole-repo mount, latest, Host-derived player, installer query token | **Partially fixed:** Host-header link generation removed, header-only installer token | Non-root container and writable-volume migration, narrow bind mount, pinned Docker/tag/dependency hashes, Traefik/go2rtc separation |
| 10 | Internal exceptions, unbounded import body, weak guest passwords, long Argon2 inputs | **Partially fixed:** streaming CSV size bound and password length limits | Sanitize remaining client-visible exception details and logs |

**Deployment caution:** Rejecting historically stored non-LAN, Docker-internal, unsupported, or unresolvable camera/controller URLs can make a stream or ESP status unavailable until corrected. This is fail-closed behavior. Backend-managed go2rtc is not a general public streaming API. The code cannot assert that external Traefik routing or firewall rules are secure without a live configuration review.

# GrowTent Backend v0.411 – Security follow-up

This version addresses the remaining **step-up** and **QR URL** findings in the supplied security review. It does not claim to fix the other findings, and is not a penetration test.

| Original finding | v0.411 status | Evidence and limitations |
|---|---|---|
| 3. No re-authentication for sensitive actions | **Addressed** | `/auth/step-up` checks the logged-in admin's current password and active TOTP when enabled. Session-bound proof expires after ≤300s; 5 failed attempts cause a 15-minute per-session lock. Middleware and modular dependencies protect sensitive auth/admin/backup routes; 2FA enrollment verification also needs the bound session. |
| 7. Secret-bearing QR GET URL | **Addressed** | `/auth/qr.png?token=<opaque>` now refers to a short-lived server-side enrollment bound to the initiating admin session. The seed remains server-side and is not included in URL, history or logs. It is encoded in the QR graphic by design (the authenticator app needs it). |
| 4. Stored cleartext secrets/backup secrets | **Still open** | Encrypted at-rest storage, migration, backup encryption and key rotation are outside v0.411. The backup export requires fresh verification but still contains secrets. Handle as confidential. |
| 5. CSP/HSTS | **Open** | Plan nonce-based CSP and configure HTTPS-only HSTS at the Traefik edge after a staging compatibility check. |
| 6. Proxy rate limiting, timing, TOTP replay | **Open** | The new step-up has its own per-session lockout, but the existing *login* rate limiter and TOTP replay protections need separate work. |
| 8. Route-level authorization | **Partially addressed** | Specific modular auth/system sensitive routes now use `Depends(legacy.require_recent_admin_confirmation)`, with centralized middleware protection as an additional layer. More routes remain to be reviewed. |
| 9. Docker/image hardening | **Open** | Root container, broad read-only mount and unpinned `latest`/dependencies need deployment work. |
| 2. Remaining SSRF risk | **Partially addressed in v0.409** | Keep go2rtc/network egress restrictions and host validation on the list. |

### Deployment considerations

- After upgrade, the first sensitive Setup operation asks for the current administrator password and, if enabled, a TOTP code. A new confirmation is needed after five minutes or a credential/2FA change.
- The **Setup Backup export button** fetches a protected blob and prompts correctly. Direct navigation to the backup URL returns HTTP 428 until verified.
- Exports and backups may contain authentication secrets; store and transmit them only over protected channels and do not upload them publicly.
- The QR is session-bound, valid for ten minutes, cannot be redeemed by a different session and does not put the seed in the URL. Finishing the setup requires a fresh confirmation if five minutes have elapsed.
- Verify actual login, existing 2FA, backup export/import and Setup changes behind the deployment's Traefik routing. No physical pumps, relays or other devices are modified.

# GrowTent Backend v0.411 – Fresh administrator confirmation and safer 2FA QR setup

## Security improvements

- **Step-up authentication for sensitive administrator actions:** The currently logged-in administrator must confirm their **current password**, and also a **TOTP code when 2FA is enabled**, before changing account/password/2FA settings, creating/updating/deleting administrators, regenerating recovery codes, or importing/exporting configuration backups. This is enforced server-side (both legacy and modular FastAPI routes); the Setup UI displays a bilingual modal when the backend returns HTTP 428 and retries the exact original request only after success.
- **Five-minute confirmation:** The confirmation is stored only with the current in-memory session (maximum **300 seconds**, configurable downward via `STEP_UP_TTL_SECONDS`). It is bound to the admin's current password hash and 2FA state. Updating the account or enabling 2FA invalidates old confirmations; logout/session expiry ends the authorization. A revoked administrator session cannot be resurrected by the normal sliding-TTL refresh. After **five** failed confirmation attempts, that session is locked from retrying for **15 minutes**. Sessions still need the existing mandatory login.
- **2FA QR secret removed from GET URLs:** `/auth/qr.png` now accepts only a short-lived opaque `token` tied to the initiating administrator session. The TOTP URI is built **server-side** from the pending enrollment; it is no longer accepted as a query parameter, returned in routine `/config/auth` reads, or included in enrollment responses. QR data is marked no-store, and final 2FA enrollment verification also checks the initiating session.
- **Backups protected:** The Setup export button now fetches an authenticated blob rather than navigating directly to a protected URL, so the modal can run before the download. The import and export API routes require step-up independently of browser behavior.
- **Defence in depth:** Both the authentication middleware and modular route dependencies enforce step-up on the listed endpoints. Normal authenticated camera previews, ESP/Shelly actions, VPD, scheduled irrigation, historical analysis and guest read-only access are unaffected.

## Verification

- **442 Python tests passed, 8 skipped locally** (7 tests need an isolated PostgreSQL server; one checks the installed PostgreSQL driver in CI). Additional targeted tests cover expired or invalid proof, password/hash rotation, required TOTP, five-failure lockout, guest denial, session-bound QR, and the modular production ASGI router.
- **Five JavaScript test suites passed.** Chromium: security confirmation DE/EN, wrong-password retry, TOTP, 320 px mobile, XSS, Setup layout, HDR and camera pot markers passed.
- GitHub Actions adds the step-up Chromium browser check. Full PostgreSQL integration, Docker image build, Traefik and live-system tests must still run in their respective environments.

## Remaining security work

- Database and backup secrets remain stored without application-level encryption; secure key management and safe migration are **planned separately**, not part of this update.
- Rate-limit policy behind Traefik, distributed login state and TOTP replay protection remain separate follow-up work.
- CSP/HSTS, non-root Docker deployment and pinned dependencies remain pending. Do not expose go2rtc or PostgreSQL externally.
- **Browser behavior:** A direct link to `/config/backup/export` may return HTTP 428 until confirmation; use the Setup Backup export button for the interactive confirmation and download.

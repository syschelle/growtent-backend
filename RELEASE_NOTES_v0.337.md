# GrowTent Backend v0.337

## Authenticated GrowTent firmware write API

This release adds controlled backend-to-controller writes for GrowTent firmware v0.5.0 and newer.

### Added
- Per-tent Backend Write API configuration with controller address, enable/disable control and a write-only 256-bit HMAC secret.
- Authenticated partial updates for target temperature, target VPD, flowering start, drying start and current phase.
- Exact HMAC-SHA256 request signing compatible with the firmware contract, including body hashing, Unix timestamp and a fresh cryptographically secure nonce.
- Validation for allowed fields, value ranges, ISO calendar dates, phase requirements and explicit `null` date deletion.
- Bounded retries for temporary `409` controller conflicts with a newly generated timestamp, nonce and signature for every attempt.
- Verification after `202 Accepted` against both controller `stored` and `runtime` state before reporting success.
- Admin-only Grow Profile editing in Setup with a preview of the exact JSON payload being sent.
- Audit records for controller writes without storing HMAC secrets or signatures in the audit log.
- Safe error mapping for firmware authentication, validation, busy-state and verification failures.

### Security
- The HMAC secret is never returned through the tent API, is not included in normal backups, and is not logged.
- Full HMAC signatures are not written to application logs.
- HMAC protects authenticity, integrity and replay resistance; the controller connection remains HTTP on TCP/8080 and is **not encrypted**.
- The firmware's allowed backend source-IP check remains mandatory and must be configured with the TCP peer IP actually seen by the ESP (often the Docker host LAN IP when NAT is involved).

### Database / configuration
- Added `tents.backend_write_enabled`.
- Added `tents.backend_controller_url`.
- Added `tents.backend_hmac_secret`.
- Added the `grow_write_audit` table.
- Backup schema version is now `12`; the HMAC secret stays redacted.

### Tests
- Added the mandatory firmware HMAC test vector.
- Added coverage for valid partial writes, auth failures, replay handling, range/date/phase validation, verification success/timeout, fresh retry signing and log redaction.
- Full test suite passes for this source tree.

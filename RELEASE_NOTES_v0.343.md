# GrowTent Backend v0.343

## HMAC status hint in the Grow Phase card

This release adds a small security-status indicator to the Grow Phase card.

### Dashboard
- Added a green **HMAC** label in the top-right area of the Grow Phase card.
- The label is shown only when the Backend Write API is enabled, the controller URL is configured, and an HMAC secret is stored for the tent.
- Added an information hint using the same popover style as the existing Temperature and VPD explanations.

### Hint text
**English:** HMAC stands for Hash-based Message Authentication Code. The backend and GrowTent controller share a secret key. Write requests are signed so the controller can verify that they are unchanged and come from the authorized backend. HMAC does not encrypt the HTTP connection.

**German:** HMAC steht für Hash-based Message Authentication Code. Backend und GrowTent-Controller teilen einen geheimen Schlüssel. Schreibzugriffe werden damit signiert, sodass der Controller prüfen kann, ob sie unverändert und vom berechtigten Backend stammen. HMAC verschlüsselt die HTTP-Verbindung nicht.

### Security
- No secret value is exposed by the indicator or hint.
- Existing HMAC-SHA256 request signing, source-IP checks, nonce/timestamp replay protection, and controller verification are unchanged.

### Tests
- Added regression tests for HMAC indicator placement, configuration-based visibility, green styling, and bilingual hint handling.
- Full automated test suite: **100 passed**.
- Dashboard JavaScript syntax check: **passed**.

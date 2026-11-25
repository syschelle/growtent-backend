# GrowTent Backend v0.421 – Matching green VPD auto status

- **Matching green:** The VPD tile's unframed **auto** text now uses exactly the same green as the **good** VPD range assessment, in both dark and light themes.
- **Unchanged statuses:** Orange still signals a failed last sync; the label remains hidden when disabled or its status is unavailable, and the DE/EN tooltip remains.
- **No behavior changes:** Status API, tent isolation, 30-second refresh, user rights, VPD phase/week plans, HMAC, camera, HDR, irrigation, Shelly, backups and schema are unchanged.
- **Verification:** Browser checks compare computed text color directly against the good VPD assessment in both themes and retain existing borderless, status and responsive regressions.

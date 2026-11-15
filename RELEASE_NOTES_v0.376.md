# GrowTent Backend v0.376

- Make the VPD reference table accessible to guest viewers by aligning CSS with the existing JavaScript read-only button allowlist.
- Guests can open/close the table and save its browser-local week mapping. Controller settings and write actions remain protected.

Validation: VPD unit tests and release-note checker passed; browser coverage added for guest controls and blocked write buttons (runs in CI).

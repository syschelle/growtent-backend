# GrowTent Backend v0.377

- Rename ESP-Regel-VPD to IST-VPD (Actual VPD in English).
- Remove week-mapping controls, browser-local overrides and save handling from the VPD table. The table is display-only for guests and administrators.
- Remove the extended-phase suffix; retain phase/week reference highlighting and the same late-phase range for extended phases.
- Default mapping remains weeks 1–2 early, week 3 onward late; no ESP targets or control behaviour change.

Validation: VPD unit tests and release-note check; browser regressions updated for display-only markup and ignored old overrides (CI).

# GrowTent Backend v0.375

- Show a compact phase/week reference assessment beside the current VPD value, without the ESP-Regelwert prefix.
- Reuse the per-tent week mapping from the VPD table. Extended phases retain their range; drying and stale/missing data show no in-range claim.
- Keep the assessment on the existing value row, with ellipsis and full-text tooltip for narrow tiles. No ESP target or control changes.
- Refresh the VPD script cache version.

Validation: VPD unit tests passed. Browser regression coverage added for inline status and stale expiry; executed by CI.

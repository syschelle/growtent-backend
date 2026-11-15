# GrowTent Backend v0.373

- Match VPD reference-table colours to the displayed two-decimal values. A displayed 1.60 kPa stays orange; 1.61 kPa uses the outer-range colour.
- Apply consistent display rounding at all colour boundaries. ESP measurements, control values and regulation remain unchanged.
- Keep only the current versioned release-notes file.

Validation: VPD table unit and rounding-boundary regression tests.

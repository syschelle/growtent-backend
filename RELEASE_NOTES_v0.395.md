# GrowTent Backend v0.395

- Add historical `grow_phase` metadata to the export and each homogeneous time bucket: language-independent phase, week and early/late stage, German/English labels, and the VPD table reference range in kPa.
- Use the ESP's stored phase/week, with early weeks 1–2 and late from week 3 as in the VPD table. Drying has no stage or reference band; missing/invalid weeks remain unknown. The top-level phase is from the final exported sample, with its observation timestamp.
- For mixed buckets, output `grow_phase: null` and `grow_phase_counts` with sample counts per phase (including unknown); the aggregate metrics are not split or incorrectly assigned. Existing context, measurements, irrigation data and size guard remain intact. No database, ESP or dashboard behavior changes.

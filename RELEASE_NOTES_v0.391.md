# GrowTent Backend v0.391

- Add an optional flowering time selector: Short (up to 8 weeks), Medium (9–10 weeks), Long (from 11 weeks). German and English labels include the week ranges.
- Show the flowering category in the strain library and dashboard strain details.
- Persist language-independent category codes in PostgreSQL with an additive migration. Include them in CSV and configuration backup export/import. Legacy CSV imports and API updates without the field preserve existing values; older restored backups without the field default to unspecified.
- The category is informational only and does not change controller settings, schedules or grow-phase logic.

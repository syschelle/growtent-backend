# GrowTent Backend v0.397

- Make Setup denser on desktop: place the existing Appearance + Charts + Backup cards in a left column, Access + Guest users + Administrators in a middle column, and Pushover + Air Sensor in a right column. Tents still span full available width below the overview.
- Preserve the five section anchors and quick links; apply responsive two-column tablet and single-column phone layouts with no horizontal scrolling.
- All existing input/control IDs, language strings, save handlers, authorization behavior, API calls and tent edit/irrigation plan workflows are unchanged. This is layout-only; no database or ESP changes.
- Strengthen the browser regression to assert column geometry, arrangement on tablet/mobile, full-width Tents area, and the existing modal and mocked tent save request.

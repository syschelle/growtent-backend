# GrowTent Backend v0.371

## Changes

- Move the VPD table button to the lower-left corner beside the target change action.
- Use one compact footer row instead of a separate full-width button row, reducing VPD tile height.

## Compatibility

Layout only. VPD data, reference table, target editing and permissions are unchanged. No firmware update or database migration required.

## Validation

Production browser checks verify shared-row alignment, compact width, no overlap and footer height at desktop, tablet and mobile widths. Existing table and target-editor tests remain in place.

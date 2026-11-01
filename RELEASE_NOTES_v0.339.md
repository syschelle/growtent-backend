# GrowTent Backend v0.339

## Simplified Grow Profile page

This release simplifies day-to-day Grow Profile changes and moves the editor out of the dashboard content area.

### Changed

- The selected tent dashboard now contains only a compact **Grow Profile / Grow-Profil** action.
- Grow Profile editing opens as a dedicated CanopyOps page, similar to the other separate application pages.
- Each writable setting is presented on its own card with the current value, an input field and a single **Send** button.
- Removed the JSON preview, manual controller reload action and the visible **Send and verify** workflow.
- Controller verification still happens automatically in the backend after every successful firmware request.
- Flowering and drying dates have an additional explicit **Delete** action. Deletion continues to send JSON `null`; an empty date is never treated as a delete request.
- The page is responsive and changes to a single-column layout with full-width buttons on phones.

### Security and controller behavior

The authenticated firmware integration is unchanged:

- administrator-only writes
- per-tent Write API configuration
- HMAC-SHA256 signing
- fresh timestamp and nonce handling
- bounded retries for temporary controller conflicts
- verification against both firmware `stored` and `runtime` values before success is reported
- no HMAC secret or signature exposure in the UI or logs

### Tests

- Updated UI regression tests for the detached Grow Profile page and simplified one-value-at-a-time send flow.
- Full automated test suite: **90 passed**.
- JavaScript syntax check: passed.

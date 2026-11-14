# GrowTent Backend v0.360

## Changes

- Prevent the target dialog from briefly appearing oversized before its embedded editor has loaded.
- Prepare its scoped width and content size while the card is hidden, then reveal it after the editor reports a ready layout.
- Show compact loading feedback with a close action while waiting. Load errors remain visible and can be dismissed.
- Ignore unready and stale navigation height messages; retain content-height updates after opening.

## Compatibility

- Keep the 280 px target-dialog width, two-decimal current VPD and ändern/change labels from v0.359.
- Existing editor scopes, validation, administrator gates, HMAC writes and dashboard/camera continuity are unchanged.
- No additional ESP polling or artificial production loading delay is introduced.

## Validation

Browser tests delay synthetic profile responses to verify hidden initial sizing, loading cancellation, stale-message rejection, stable first visible geometry and visible load errors. Existing scoped PATCH, validation, permissions, PostgreSQL, security and CodeQL checks remain required. No live ESP is contacted by tests.

# GrowTent Backend v0.359

## Changes

- Label both dashboard target-edit buttons `ändern` in German and `change` in English.
- Keep the specific target-temperature and target-VPD dialog headings and tooltips.
- Reduce target-only dialogs from 560 px to 280 px desktop width while retaining responsive limits and the phase/date dialog size.
- Display current VPD with two decimals, preserving values such as 1.17 kPa.

## Compatibility

- Button positions, editor scopes, validation, administrator checks and HMAC writes are unchanged.

## Validation

Existing target-editor browser checks verify production DE/EN button-label assignments, specific dialog headings, compact target widths, no iframe overflow, two-decimal current VPD and unchanged phase/date dialog width. Existing backend, security and database checks remain required. No live controller write is performed by tests.

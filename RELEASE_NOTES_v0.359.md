# GrowTent Backend v0.359

## Changes

- Label both dashboard target-edit buttons `ändern` in German and `change` in English.
- Keep the specific target-temperature and target-VPD dialog headings and tooltips.

## Compatibility

- Button positions, editor scopes, validation, administrator checks and HMAC writes are unchanged.

## Validation

Existing target-editor browser checks now verify the production DE/EN button-label assignments and unchanged specific dialog headings. Existing backend, security and database checks remain required. No live controller write is performed by tests.

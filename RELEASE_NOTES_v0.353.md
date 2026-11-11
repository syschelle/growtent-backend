# GrowTent Backend v0.353

## One Save button for Grow Profile edits

This release simplifies the Grow Profile adjustment dialog by replacing five separate **Send** buttons with one **Save changes** action at the bottom of the editor.

### User interface

- All five fields remain editable: target temperature, target VPD, current phase, flowering start, and drying start.
- A single **Save changes / Änderungen speichern** button submits the pending changes together.
- The button is disabled until valid changes are present; the editor displays a count of pending changes.
- Only changed fields are included in the outgoing partial PATCH. Unchanged values are never resent.
- Date **Delete / Löschen** marks a date for deletion; **Undo / Rückgängig** cancels the pending deletion. The actual deletion occurs only on Save and uses JSON `null`.
- Preserved compact layout, mobile responsiveness, and bilingual labels.

### Security and compatibility

- Administrator-only access, HMAC-SHA256 request signing, nonce/timestamp replay protection, and stored/runtime verification are unchanged.
- Temperature adjustments remain in 0.5 °C increments and VPD adjustments in 0.1 kPa increments.
- No database migration, additional controller polling, or GrowTent firmware update is required.

### Tests

- **142 automated tests passed**.
- Browser interaction checks verified single-field and combined PATCH payloads, reversible date deletion, disabled state for invalid/no changes, and no horizontal overflow at 320/390 px.
- JavaScript and Python syntax checks passed.
- No live ESP hardware validation performed.

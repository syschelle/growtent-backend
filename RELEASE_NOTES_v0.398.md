# GrowTent Backend v0.398

- Add a compact **Cancel / Abbrechen** button beside **Save tent / Zelt speichern** in the tent editor. It is available while editing an existing tent or drafting a new one.
- Cancel discards unsaved form changes, clears secret inputs and any pending HMAC-secret removal checkbox, resets the editor to Add tent mode and closes the editor. No request is sent, and stored tent configuration is unchanged.
- Preserve the existing Save, Edit, irrigation-plan and Delete actions, responsive setup layout, bilingual labels and both themes. Successful saves continue to use the existing POST/PUT endpoints and payload.
- Extend the isolated Chromium regression with edit/cancel/reopen, safe secret and checkbox reset, create/cancel, zero writes on cancel, and DE/EN button labels.

# GrowTent Backend v0.407 – Camera hover strain hint and outside pot toggle (DE/EN)

- **No pot buttons on the image:** The fullscreen camera no longer shows the **Töpfe / Pots** toggle on top of the picture. It moved into the toolbar above the image together with **Positionen bearbeiten / Edit positions**, **Speichern / Save**, and **Abbrechen / Cancel**, keeping the plant view unobstructed.
- **Hover / focus hint:** Hovering a numbered pot marker (or focusing it by keyboard) now shows the currently assigned strain for that pot, for example **Oreoz**. Empty assignments show a localized fallback (**Keine Sorte / No strain**). The saved JSON/export mapping remains unchanged.
- **Markers remain simple:** The fullscreen image and `camera-marked.jpg` still display only the numeric pot circles **1–3**. Visible strain names stay out of the image itself; they appear only as hover hints and in the exported JSON mapping.
- **Compatibility:** Existing saved marker positions continue to work. No changes to ESP, watering, VPD, HDR/original preview modes, ZIP contents, permissions, database schema, or camera capture sources.
- **Verification:** Targeted browser/manual checks for DE/EN, admin/guest, hover/focus tooltip, save/cancel and responsive layout completed. Release package and version metadata updated.

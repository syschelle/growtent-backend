# GrowTent Backend v0.399 – Bilingual full Grow-Guide

- Replace the former short, German-only Grow-Guide with the complete user-supplied 20-chapter indoor cultivation reference (version 1.0, November 2026), from germination and cuttings through vegetative/flowering stages, harvest, drying, and optional curing.
- Provide a complete English translation in addition to the original German text, including all phase tables, VPD/planning values, precautions, irrigation and nutrient considerations, problem reference, and 13 linked sources.
- Keep the original guide in `docs/grow-guide-de.md` and the matching English text in `docs/grow-guide-en.md`. Pre-render escaped, table-enabled HTML fragments in `api/static` to avoid adding runtime Markdown dependencies. Optional build helper: `scripts/build_grow_guide.py` (dev-only mistune 3).
- Introduce a responsive reading view with 20-chapter navigation, client-side chapter search, a language switch using the existing `gt_lang` preference, and the current dark/light setting (`gt_theme`). Horizontal scrolling is limited to tables on narrow screens.
- Preserve the `/grow-guide` URL, `/app?page=grow-guide` redirect, embedded shell navigation and remaining application routes.
- Read-only content. The guide's finer VPD guidance does **not** change the existing dashboard VPD reference table, ESP setpoints, phase logic, or controller behavior.

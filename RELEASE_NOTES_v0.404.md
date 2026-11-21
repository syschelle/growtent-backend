# GrowTent Backend v0.404 – Pot strain names in per-tent analysis export

- Include the three assigned strain names from the selected tent's saved Setup configuration in **both** the JSON-only analysis export and the JSON inside the high-resolution camera ZIP export.
- New top-level JSON fields: `tent_name`, `pot_strains` (exactly `pot1`, `pot2`, `pot3`, with an empty string for unassigned pots) and `pot_strains_source: "current_tent_configuration"`. `tentId` continues to identify the originating tent.
- Pot names are **current backend configuration**, not historical ESP measurements or a reconstructed strain timeline. A change in Setup affects subsequent exports only; old measurements and phase metadata are untouched.
- Read the existing `pot_strains_json` column for the specific tent ID. No schema migration, additional controller call, new writable endpoint, camera image processing or UI change.
- Preserve `growtent.analysis.v1`, all existing analytics/ZIP members (`camera.jpg`, `camera-hdr.jpg`), and the 1 MB bound for JSON exports. Do not export RTSP credentials, HMAC secrets, device IPs or unrelated tent settings.
- Add regression coverage for tent-specific SQL reads, three-pot mapping, unassigned pots and identical JSON metadata in both export formats.
- Verification: run existing Python/Node test suites and `python scripts/check_release_notes.py --tag v0.404`. Live PostgreSQL, Docker and RTSP validation are separate deployment checks.

# Release notes

- Keep exactly one `RELEASE_NOTES_<current-version>.md` file in the repository root, matching `APP_VERSION` in `api/app.py`.
- When changing the version, replace the old notes file; do not accumulate versioned notes.
- Preserve published releases, tags and Git history. Historical links must point to an existing historical commit or published release.
- Run `python scripts/check_release_notes.py` before completion. Keep TESTING.md and SECURITY.md current with release changes.

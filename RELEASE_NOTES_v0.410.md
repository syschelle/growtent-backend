# GrowTent Backend v0.410 – GitHub Actions PostgreSQL test isolation fix

## Fixed

- **CI blocker (v0.409):** `tests/test_security_hardening.py` inserted a fake `psycopg2` module during pytest collection whenever `psycopg2` had not yet been imported. Because GitHub Actions executes the full suite in one process, that fake driver also intercepted the seven real PostgreSQL integration tests and raised `RuntimeError: DB access not expected in security unit tests`.
- **Safe import behavior:** Security unit tests now first import the real installed PostgreSQL driver. Only environments where `psycopg2` is genuinely missing get the lightweight fallback stub. The real driver is never replaced in GitHub Actions.
- **Regression check:** Added a test asserting that the installed `psycopg2-binary` driver remains a real module with a callable `connect`. This prevents future test-import changes from silently disabling the PostgreSQL integration suite.

## Compatibility and verification

- No change to production authentication, hardware, database schema, RTSP/go2rtc, irrigation, exports or deployment configuration. The actual application change is only the version identifier.
- Local test run: **429 passed, 8 skipped, 2 existing FastAPI deprecation warnings**, with the 7 live-PostgreSQL integration tests skipped because `IRRIGATION_TEST_DATABASE_URL` and a PostgreSQL server are not available in the local sandbox. The eighth skip is the installed-driver regression test; it runs in CI, which installs `psycopg2-binary`.
- An isolated subprocess using a locally supplied driver module confirmed that importing the security tests no longer replaces an existing `connect()` function. The seven PostgreSQL integration tests must still run in GitHub Actions against the workflow's isolated PostgreSQL 17 service; no claim of a live database test is made here.
- All v0.409 security controls remain in force; open security follow-up items documented in the previous release remain open.

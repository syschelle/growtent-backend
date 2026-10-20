from pathlib import Path


def _source() -> str:
    return (Path(__file__).resolve().parents[1] / "api" / "app.py").read_text(encoding="utf-8")


def test_setup_uses_per_admin_2fa_ui_only():
    source = _source()
    assert 'id=\\"adminsCard\\"' in source
    assert 'data-admin-2fa-info' in source
    assert 'id=\\"twofaCard\\"' not in source
    assert 'id=\\"recoveryCard\\"' not in source


def test_admin_list_endpoint_self_heals_legacy_migration():
    source = _source()
    start = source.index('@app.get("/config/admins")')
    end = source.index('@app.post("/config/admins")', start)
    route = source[start:end]
    assert '_migrate_legacy_admin_if_needed(cur)' in route
    assert 'current_admin_id' in route

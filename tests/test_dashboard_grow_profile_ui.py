from pathlib import Path


def _source() -> str:
    return (Path(__file__).resolve().parents[1] / "api" / "app.py").read_text(encoding="utf-8")


def _dashboard_source() -> str:
    source = _source()
    return source[source.index('@app.get("/dashboard", response_class=HTMLResponse)'):]


def _setup_source() -> str:
    source = _source()
    return source[:source.index('@app.get("/dashboard", response_class=HTMLResponse)')]


def test_grow_profile_editor_is_in_dashboard_and_not_setup_tent_actions():
    dashboard = _dashboard_source()
    setup = _setup_source()
    assert 'id=\\"growProfileInline\\"' in dashboard
    assert 'id="openGrowProfileBtn"' in dashboard
    assert 'data-grow-profile-tent' not in setup
    # Technical controller/HMAC configuration intentionally remains in Setup.
    assert 'id=\\"tentBackendWriteEnabled\\"' in setup
    assert 'id=\\"tentBackendControllerUrl\\"' in setup
    assert 'id=\\"tentBackendHmacSecret\\"' in setup


def test_dashboard_grow_profile_editor_is_mobile_responsive():
    dashboard = _dashboard_source()
    assert '.grow-profile-editor { grid-template-columns:1fr; }' in dashboard
    assert 'body.force-mobile .grow-profile-editor { grid-template-columns:1fr; }' in dashboard
    assert '.grow-profile-actions button { width:100%; padding:10px 12px; }' in dashboard


def test_dashboard_grow_profile_uses_existing_admin_protected_routes():
    dashboard = _dashboard_source()
    assert "currentUserRole !== 'admin'" in dashboard
    assert "fetch(`/tents/${currentTentId}/grow-profile`, { cache:'no-store' })" in dashboard
    assert "method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(patch)" in dashboard
    assert "currentTentMeta?.backend_write_enabled" in dashboard
    assert "currentTentMeta?.has_backend_hmac_secret" in dashboard


def test_dashboard_date_deletion_is_explicit_null_and_blank_dates_are_rejected():
    dashboard = _dashboard_source()
    assert 'if (floweringDelete) patch.floweringStart = null;' in dashboard
    assert 'if (dryingDelete) patch.dryingStart = null;' in dashboard
    assert "dashboardGrowProfileOriginal.floweringStart && !flowering" in dashboard
    assert "dashboardGrowProfileOriginal.dryingStart && !drying" in dashboard
    assert "growDateDeleteRequired" in dashboard


def test_dashboard_editor_keeps_controller_api_in_celsius():
    dashboard = _dashboard_source()
    assert 'Target temperature (°C)' in dashboard
    assert 'Solltemperatur (°C)' in dashboard
    assert 'id=\\"dbGrowTargetTemperature\\" type=\\"number\\" min=\\"18\\" max=\\"30\\" step=\\"0.1\\"' in dashboard
    assert 'id=\\"dbGrowTargetVpd\\" type=\\"number\\" min=\\"0.5\\" max=\\"3.5\\" step=\\"0.01\\"' in dashboard

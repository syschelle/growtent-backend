from pathlib import Path


def _source() -> str:
    return (Path(__file__).resolve().parents[1] / "api" / "app.py").read_text(encoding="utf-8")


def _dashboard_source() -> str:
    source = _source()
    return source[source.index('@app.get("/dashboard", response_class=HTMLResponse)'):]


def _grow_profile_page_source() -> str:
    source = _source()
    start = source.index('@app.get("/grow-profile", response_class=HTMLResponse)')
    end = source.index('@app.get("/app", response_class=HTMLResponse)', start)
    return source[start:end]


def _setup_source() -> str:
    source = _source()
    return source[:source.index('@app.get("/grow-profile", response_class=HTMLResponse)')]


def test_grow_profile_editor_is_detached_from_dashboard_and_setup():
    source = _source()
    dashboard = _dashboard_source()
    setup = _setup_source()
    page = _grow_profile_page_source()
    assert '@app.get("/grow-profile", response_class=HTMLResponse)' in source
    assert 'id=\\"growProfileInline\\"' not in dashboard
    assert 'openGrowProfileBtn' in dashboard
    assert 'function openGrowProfilePage()' in dashboard
    assert 'data-grow-profile-tent' not in setup
    assert 'id=\\"tentBackendWriteEnabled\\"' in setup
    assert 'id=\\"tentBackendControllerUrl\\"' in setup
    assert 'id=\\"tentBackendHmacSecret\\"' in setup
    assert 'data-send="targetTemperature"' in page


def test_shell_opens_grow_profile_as_separate_embedded_page():
    source = _source()
    assert "page === 'grow-profile' && tent" in source
    assert "src = `/grow-profile?embed=1&tent=${encodeURIComponent(tent)}`" in source
    dashboard = _dashboard_source()
    assert "`/app?page=grow-profile&tent=${encodeURIComponent(String(currentTentId))}`" in dashboard


def test_simple_page_is_one_value_then_send_without_json_preview_controls():
    page = _grow_profile_page_source()
    for field in ("targetTemperature", "targetVPD", "currentPhase", "floweringStart", "dryingStart"):
        assert f'data-send="{field}"' in page
    assert 'Will be sent' not in page
    assert 'Wird übertragen' not in page
    assert 'Send and verify' not in page
    assert 'Senden und verifizieren' not in page
    assert 'Reload controller state' not in page
    assert 'JSON.stringify(patch, null, 2)' not in page


def test_simple_page_is_mobile_responsive():
    page = _grow_profile_page_source()
    assert '@media (max-width:640px)' in page
    assert '.edit-row, .date-row { grid-template-columns:1fr; }' in page
    assert 'button { width:100%; }' in page


def test_detached_page_uses_existing_admin_protected_routes_and_dashboard_gate():
    dashboard = _dashboard_source()
    page = _grow_profile_page_source()
    assert "currentUserRole !== 'admin'" in dashboard
    assert "currentTentMeta?.backend_write_enabled" in dashboard
    assert "currentTentMeta?.has_backend_hmac_secret" in dashboard
    assert "fetch(`/tents/${tentId}/grow-profile`,{cache:'no-store'})" in page
    assert "method:'PATCH'" in page
    assert "body:JSON.stringify(patch)" in page
    assert "who?.role!=='admin'" in page


def test_date_deletion_is_explicit_null_and_blank_date_is_not_sent():
    page = _grow_profile_page_source()
    assert 'data-delete="floweringStart"' in page
    assert 'data-delete="dryingStart"' in page
    assert "sendPatch({[btn.dataset.delete]:null},btn);" in page
    assert "if(!value){setStatus(T.chooseDate,'err');return;}" in page


def test_detached_editor_keeps_controller_api_in_celsius():
    page = _grow_profile_page_source()
    assert '<strong id="tempCurrent">-</strong> °C' in page
    assert 'id="tempInput" type="number" min="18" max="30" step="0.5"' in page
    assert 'id="vpdInput" type="number" min="0.5" max="3.5" step="0.1"' in page
    assert "matchesStep(value,0.5,18)" in page
    assert "matchesStep(value,0.1,0.5)" in page


def test_dashboard_adjust_button_is_inside_status_tile_after_status_text_and_not_in_phase_card():
    dashboard = _dashboard_source()
    row = r'<div class=\"status-row\">'
    status = r'<div id=\"status\" class=\"small\"><span id=\"statusText\">Loading…</span> __GROW_PROFILE_ACTION__</div>'
    assert row in dashboard
    assert status in dashboard
    assert "grow_profile_action = '<button id=\"openGrowProfileBtn\"" in dashboard
    assert "editGrowProfile: 'Anpassen'" in dashboard
    assert "const statusText = document.getElementById('statusText') || el;" in dashboard
    assert 'statusText.innerHTML = `Status: <span class="status-ok">OK</span>`;' in dashboard
    phase_line = 'phaseActions.innerHTML = `<button id="resetEnergyBtn"'
    phase_start = dashboard.index(phase_line)
    phase_end = dashboard.index(';', phase_start)
    assert 'openGrowProfileBtn' not in dashboard[phase_start:phase_end]

def test_dashboard_adjust_button_only_shows_for_admin_ready_online_ok_controller():
    dashboard = _dashboard_source()
    assert 'let currentEspOnline = false;' in dashboard
    assert 'let currentStatusOk = false;' in dashboard
    assert 'const visible = isAdmin && ready && currentEspOnline && currentStatusOk;' in dashboard
    assert "btn.style.display = visible ? 'inline-flex' : 'none';" in dashboard
    assert "if (currentUserRole !== 'admin' || !currentTentId || !currentEspOnline || !currentStatusOk) return;" in dashboard
    assert 'currentEspOnline = getTentOnlineState(j?.captured_at || currentTentMeta?.capturedAt || null);' in dashboard
    assert 'currentStatusOk = false;' in dashboard
    assert 'currentStatusOk = true;' in dashboard


def test_dashboard_button_is_server_rendered_only_for_real_admin_sessions():
    dashboard = _dashboard_source()
    assert "session = get_session(token)" in dashboard
    assert "is_admin = bool(session and (session.get(\"role\") or \"\") == \"admin\")" in dashboard
    assert "grow_profile_action = '<button id=\"openGrowProfileBtn\"" in dashboard
    assert "if is_admin else ''" in dashboard
    assert '__GROW_PROFILE_ACTION__' in dashboard
    assert '.replace("__GROW_PROFILE_ACTION__", grow_profile_action)' in dashboard


def test_grow_profile_page_has_route_level_real_admin_guard():
    page = _grow_profile_page_source()
    assert 'session = get_session(token)' in page
    assert 'if not session or (session.get("role") or "") != "admin":' in page
    assert 'raise HTTPException(status_code=403, detail="admin required")' in page

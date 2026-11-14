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


def test_grow_profile_editor_opens_as_dashboard_modal_and_stays_out_of_setup():
    source = _source()
    dashboard = _dashboard_source()
    setup = _setup_source()
    page = _grow_profile_page_source()
    assert '@app.get("/grow-profile", response_class=HTMLResponse)' in source
    assert 'id=\\"growProfileInline\\"' not in dashboard
    assert 'openGrowProfileBtn' in dashboard
    assert 'function openGrowProfilePage()' in dashboard
    assert 'dbGrowProfileModal' in dashboard
    assert '__GROW_PROFILE_MODAL__' in dashboard
    assert 'data-grow-profile-tent' not in setup
    assert 'id=\\"tentBackendWriteEnabled\\"' in setup
    assert 'id=\\"tentBackendControllerUrl\\"' in setup
    assert 'id=\\"tentBackendHmacSecret\\"' in setup
    assert 'id="saveProfileBtn"' in page


def test_dashboard_opens_grow_profile_as_modal_like_irrigation_plan():
    source = _source()
    dashboard = _dashboard_source()
    assert "page === 'grow-profile' && tent" in source  # legacy deep links keep working
    assert "src = `/grow-profile?embed=1&tent=${encodeURIComponent(tent)}`" in source
    assert 'id="dbGrowProfileModal" class="grow-profile-modal"' in dashboard
    assert 'id="dbGrowProfileFrame" title="Grow profile"' in dashboard
    assert 'dbIrPlanModal' in dashboard  # existing watering plan dialog retained
    assert 'role="dialog" aria-modal="true"' in dashboard
    assert "modal.style.display = 'flex';" in dashboard
    assert 'function closeGrowProfileModal()' in dashboard
    assert "frame.src = `/grow-profile?embed=1&modal=1&tent=${encodeURIComponent(String(currentTentId))}&section=${encodeURIComponent(section)}`;" in dashboard
    assert 'window.parent.location.href = url' not in dashboard[dashboard.index('function openGrowProfilePage()'):dashboard.index('function applyI18n()')]
    assert "frame.src = 'about:blank';" in dashboard
    assert "loadLatest().catch(() => {});" in dashboard


def test_modal_has_mobile_height_and_compact_editor_without_standalone_header():
    dashboard = _dashboard_source()
    page = _grow_profile_page_source()
    assert '.grow-profile-modal-card' in dashboard
    assert 'height:calc(100dvh - 12px)' in dashboard
    assert 'max-height:calc(100dvh - 12px)' in dashboard
    assert 'body.modal-editor .head { display:none; }' in page
    assert "qs.get('modal') === '1'" in page


def test_modal_is_server_side_admin_only_while_grow_profile_route_remains_protected():
    dashboard = _dashboard_source()
    page = _grow_profile_page_source()
    assert "grow_profile_modal = '''" in dashboard
    assert "''' if is_admin else ''" in dashboard
    assert '.replace("__GROW_PROFILE_MODAL__", grow_profile_modal)' in dashboard
    assert 'if not session or (session.get("role") or "") != "admin":' in page
    assert 'raise HTTPException(status_code=403, detail="admin required")' in page


def test_modal_closes_with_button_escape_and_backdrop_and_keeps_dashboard():
    dashboard = _dashboard_source()
    assert "dbGrowProfileCloseBtn')?.addEventListener('click', closeGrowProfileModal)" in dashboard
    assert "event.target?.id === 'dbGrowProfileModal'" in dashboard
    assert "event.key === 'Escape'" in dashboard
    assert "document.body.style.overflow = 'hidden';" in dashboard
    assert "modal.setAttribute('aria-hidden', 'true')" in dashboard
    assert "modal.setAttribute('aria-hidden', 'false')" in dashboard



def test_grow_profile_uses_one_save_action_without_json_preview_controls():
    page = _grow_profile_page_source()
    assert page.count('id="saveProfileBtn"') == 1
    assert 'Änderungen speichern' in page
    assert 'Save changes' in page
    assert 'data-send=' not in page
    assert "document.querySelectorAll('[data-send]')" not in page
    assert 'Will be sent' not in page
    assert 'Wird übertragen' not in page
    assert 'JSON.stringify(patch, null, 2)' not in page
    assert 'function buildPatch()' in page
    assert 'sendPatch(patch);' in page


def test_simple_page_is_mobile_responsive():
    page = _grow_profile_page_source()
    assert '@media (max-width:640px)' in page
    assert 'body:not(.modal-editor) .date-row { grid-template-columns:minmax(0,1fr) auto; }' in page
    assert 'body:not(.modal-editor) .save-row button { width:100%; }' in page


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
    assert 'pendingDeletes.add(field);' in page
    assert 'pendingDeletes.delete(field);' in page
    assert 'patch[field]=null;' in page
    assert 'return {patch,error:T.dateDeleteExplicit};' in page
    assert 'sendPatch(patch);' in page


def test_detached_editor_keeps_controller_api_in_celsius():
    page = _grow_profile_page_source()
    assert '<strong id="tempCurrent">-</strong> °C' in page
    assert 'id="tempInput" type="number" min="18" max="30" step="0.5"' in page
    assert 'id="vpdInput" type="number" min="0.5" max="3.5" step="0.1"' in page
    assert "matchesStep(temp,0.5,18)" in page
    assert "matchesStep(vpd,0.1,0.5)" in page


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


def test_dashboard_shows_green_hmac_badge_in_grow_phase_card_when_write_api_is_configured():
    dashboard = _dashboard_source()
    assert 'id=\\"hmacBadge\\" class=\\"hmac-badge\\"' in dashboard
    assert '.hmac-badge { display:none;' in dashboard
    assert 'color:#22c55e;' in dashboard
    assert 'function syncHmacBadge()' in dashboard
    assert 'currentTentMeta?.backend_write_enabled && currentTentMeta?.backend_controller_url && currentTentMeta?.has_backend_hmac_secret' in dashboard
    assert "badge.style.display = configured ? 'inline-flex' : 'none';" in dashboard
    phase_heading = dashboard.index('class=\\"phase-heading-row\\"')
    phase_main = dashboard.index('id=\\"growPhaseValue\\"', phase_heading)
    assert dashboard.index('id=\\"hmacBadge\\"', phase_heading) < phase_main


def test_hmac_badge_uses_same_bilingual_info_popover_pattern_as_temperature_and_vpd():
    dashboard = _dashboard_source()
    assert "hmacHint: 'Adjust and the target-temperature/VPD tile buttons can change selected grow values directly on the GrowTent controller." in dashboard
    assert "hmacHint: 'Über „Anpassen“, „Solltemperatur“ und „Soll-VPD“ können ausgewählte Grow-Werte direkt im GrowTent-Controller geändert werden." in dashboard
    assert 'id=\\"hmacMeaningHint\\"' in dashboard
    assert "const hmacMeaningEl = document.getElementById('hmacMeaningHint');" in dashboard
    assert "showInfoPopover(hmacMeaningEl, hint)" in dashboard
    assert "const triggerHmac = document.getElementById('hmacMeaningHint');" in dashboard
    assert 'HMAC does not encrypt the HTTP connection.' in dashboard
    assert 'HMAC verschlüsselt die HTTP-Verbindung nicht.' in dashboard


def test_dashboard_adjust_button_stays_compact_on_mobile():
    dashboard = _dashboard_source()
    assert 'button, .stream-open-btn { width:100%; text-align:center; }' in dashboard
    start = dashboard.index('#openGrowProfileBtn {')
    end = dashboard.index('}', start)
    block = dashboard[start:end]
    assert 'width:auto;' in block
    assert 'max-width:max-content;' in block
    assert 'flex:0 0 auto;' in block


def test_dashboard_info_popover_is_clamped_inside_mobile_visual_viewport():
    dashboard = _dashboard_source()
    assert 'max-width: min(460px, calc(100vw - 24px));' in dashboard
    assert 'overflow-wrap: anywhere;' in dashboard
    assert 'const vv = window.visualViewport;' in dashboard
    assert 'const maxLeft = Math.max(minLeft, viewportLeft + viewportWidth - pr.width - margin);' in dashboard
    assert 'if (top + pr.height > maxBottom) top = r.top - pr.height - gap;' in dashboard
    assert 'pop.style.left = `${Math.round(left)}px`;' in dashboard
    assert 'pop.style.top = `${Math.round(top)}px`;' in dashboard

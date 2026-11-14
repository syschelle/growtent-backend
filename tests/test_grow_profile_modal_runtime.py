"""Render-level coverage of the dashboard Grow Profile modal (without a database)."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse


SOURCE = (Path(__file__).parents[1] / 'api' / 'app.py').read_text(encoding='utf-8')


def _render_functions(role):
    selected = []
    for node in ast.parse(SOURCE).body:
        if isinstance(node, ast.FunctionDef) and node.name in ('dashboard_page', 'grow_profile_page'):
            node.decorator_list = []
            selected.append(node)
    assert len(selected) == 2
    ns = {
        'Request': Request,
        'RedirectResponse': RedirectResponse,
        'HTTPException': HTTPException,
        'FAVICON_LINKS': '',
        'get_session': lambda _token: {'role': role} if role else None,
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), 'api/app.py', 'exec'), ns)
    return ns


def _request():
    return SimpleNamespace(query_params={'embed': '1', 'tent': '3'}, cookies={'caop_session': 'test'})


def test_admin_dashboard_renders_usable_modal_and_keeps_the_irrigation_modal():
    html = _render_functions('admin')['dashboard_page'](_request())
    assert 'id="openGrowProfileBtn"' in html
    assert 'id="dbProfileDialog"' in html
    assert 'id="dbGrowProfileFrame"' not in html
    assert 'id="dbIrPlanModal"' in html
    assert '__GROW_PROFILE_MODAL__' not in html
    assert 'dialog.showModal()' in html
    assert 'closeGrowProfileModal' in html
    assert 'profileActive(ctx)' in html


@pytest.mark.parametrize('role', [None, 'guest'])
def test_guest_or_anonymous_html_has_no_adjust_button_or_modal_and_cannot_open_page(role):
    funcs = _render_functions(role)
    html = funcs['dashboard_page'](_request())
    assert 'id="openGrowProfileBtn"' not in html
    assert 'id="dbProfileDialog"' not in html
    with pytest.raises(HTTPException) as exc:
        funcs['grow_profile_page'](_request())
    assert exc.value.status_code == 403


def test_admin_modal_editor_is_compact_and_sends_only_modified_fields():
    html = _render_functions('admin')['grow_profile_page'](_request())
    assert "qs.get('modal') === '1'" in html
    assert 'body.modal-editor .head { display:none; }' in html
    assert 'id="saveProfileBtn"' in html
    assert 'data-send=' not in html
    assert 'data-delete="floweringStart"' in html
    assert 'data-delete="dryingStart"' in html
    assert 'function buildPatch()' in html
    assert 'patch.targetTemperature=temp;' in html
    assert 'patch.targetVPD=vpd;' in html
    assert 'patch[field]=null;' in html
    assert 'sendPatch(patch);' in html
    assert "body:JSON.stringify(patch)" in html
    assert "postMessage({type:'grow-profile-modal-close'}, window.location.origin)" in html


def test_compact_modal_uses_content_height_and_retains_viewport_scroll_limit():
    page = _render_functions('admin')['grow_profile_page'](_request())
    dashboard = _render_functions('admin')['dashboard_page'](_request())
    assert "body.modal-editor #editor { display:grid; gap:7px; }" in page
    assert "body.modal-editor .card {" in page
    assert "grid-template-columns:minmax(135px,.8fr) minmax(0,1.7fr);" in page
    assert "body.modal-editor .edit-row { grid-column:2; grid-row:1 / span 2;" in page
    assert "type:'grow-profile-modal-height'" in page
    assert "new ResizeObserver(reportHeight).observe(content)" in page
    assert "max-height:calc(100dvh - 24px); overflow:auto;" in dashboard
    assert "dbGrowProfileFrame" not in dashboard


def test_compact_mobile_layout_preserves_single_save_and_delete_actions():
    page = _render_functions('admin')['grow_profile_page'](_request())
    assert "body.modal-editor .edit-row button { width:auto; }" in page
    assert "body.modal-editor .date-row { grid-template-columns:minmax(0,1fr) auto; }" in page
    assert 'body.modal-editor #saveProfileBtn { width:100%; }' in page
    assert 'min-height:36px;' in page
    assert 'body.modal-editor .notice { display:none; margin:0; }' in page
    assert 'body.modal-editor input, body.modal-editor select, body.modal-editor button { min-height:40px; }' in page
    assert page.count('id="saveProfileBtn"') == 1
    assert 'data-send=' not in page
    assert 'pendingDeletes.add(field);' in page


def test_narrow_modal_keeps_desktop_rows_without_breaking_phone_layout():
    dashboard = _render_functions('admin')['dashboard_page'](_request())
    editor = _render_functions('admin')['grow_profile_page'](_request())
    assert '.profile-dialog { width:min(320px,calc(100vw - 24px)); }' in dashboard
    assert 'class="target-dialog profile-dialog"' in dashboard
    assert 'width:min(720px,100%)' not in dashboard
    # The iframe is narrower than 640px on desktop. Use a lower breakpoint so
    # it does not inadvertently render every setting in two rows.
    assert '@media (max-width:530px)' in editor
    assert 'body.modal-editor .card {' in editor
    assert 'grid-template-columns:minmax(135px,.8fr) minmax(0,1.7fr);' in editor
    assert 'body.modal-editor .date-row { grid-template-columns:minmax(0,1fr) auto; }' in editor
    assert 'body.modal-editor #saveProfileBtn { width:100%; }' in editor

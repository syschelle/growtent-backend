"""Access-control and routing regressions for per-tile target editing."""
import pytest
from types import SimpleNamespace
from fastapi import HTTPException
from test_grow_profile_modal_runtime import _render_functions, _request
from html.parser import HTMLParser

class Controls(HTMLParser):
    def __init__(self,html):super().__init__();self.tags=[];self.feed(html)
    def handle_starttag(self,tag,attrs):self.tags.append((tag,dict(attrs)))

@pytest.mark.parametrize('role',[None,'guest'])
def test_non_admin_dashboard_has_no_target_controls_or_editor_access(role):
    funcs=_render_functions(role);html=funcs['dashboard_page'](_request())
    assert 'id="editTemperatureTargetBtn"' not in html
    assert 'id="editVpdTargetBtn"' not in html
    assert 'id="dbTargetDialog"' not in html
    for section in ('temperature','vpd','profile'):
        request=SimpleNamespace(query_params={'embed':'1','tent':'3','section':section},cookies={})
        with pytest.raises(HTTPException) as exc:funcs['grow_profile_page'](request)
        assert exc.value.status_code==403

def test_admin_buttons_and_scoped_editor_fields_are_rendered():
    funcs=_render_functions('admin');html=funcs['dashboard_page'](_request())
    assert 'id="dbTargetDialog"' in html
    assert 'function openTargetDialog(section)' in html
    tags=Controls(html).tags
    for id in ('editTemperatureTargetBtn','editVpdTargetBtn'):
        matches=[a for tag,a in tags if a.get('id')==id]
        assert len(matches)==1 and matches[0]['type']=='button'
    editor=funcs['grow_profile_page'](_request())
    fields={a['data-profile-field'] for tag,a in Controls(editor).tags if 'data-profile-field'in a}
    assert fields=={'targetTemperature','targetVPD','currentPhase','floweringStart','dryingStart'}
    assert "if(!allowsField(field)) continue;" in editor

@pytest.mark.parametrize('section',['temperature','vpd','profile','<script>'])
def test_standalone_scoped_redirect_is_allowlisted(section):
    req=SimpleNamespace(query_params={'tent':'3','section':section},cookies={})
    response=_render_functions('admin')['grow_profile_page'](req)
    expected='/app?page=grow-profile&tent=3'+('&section='+section if section!='<script>' else '')
    assert response.headers['location']==expected

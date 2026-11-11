"""Regressions for the simpler, combined Grow Profile save action."""
from pathlib import Path


def _page():
    source = (Path(__file__).resolve().parents[1] / 'api' / 'app.py').read_text(encoding='utf-8')
    start = source.index('@app.get("/grow-profile", response_class=HTMLResponse)')
    return source[start:source.index('@app.get("/app", response_class=HTMLResponse)', start)]


def test_one_save_button_for_all_five_values_and_bilingual_copy():
    page = _page()
    assert page.count('id="saveProfileBtn"') == 1
    assert 'Änderungen speichern' in page
    assert "save:'Save changes'" in page
    assert page.count('data-send=') == 0
    for field in ('tempInput', 'vpdInput', 'phaseInput', 'flowerInput', 'dryInput'):
        assert f'id="{field}"' in page
    assert "$('saveProfileBtn').addEventListener('click',()=>{" in page


def test_unsaved_changes_are_combined_into_a_single_partial_patch():
    page = _page()
    assert "if(temp!==Number(original.targetTemperature))" in page
    assert "patch.targetTemperature=temp;" in page
    assert "if(vpd!==Number(original.targetVPD))" in page
    assert "patch.targetVPD=vpd;" in page
    assert "if(phase!==Number(original.currentPhase)) patch.currentPhase=phase;" in page
    assert "patch[field]=value;" in page
    assert "if(Object.keys(patch).length===0) return;" in page
    assert "sendPatch(patch);" in page
    assert "body:JSON.stringify(patch)" in page
    assert "$('saveProfileBtn').disabled=busy||!profileLoaded||count===0||!!result.error;" in page


def test_date_deletion_is_explicit_reversible_and_not_sent_immediately():
    page = _page()
    assert 'data-delete="floweringStart"' in page
    assert 'data-delete="dryingStart"' in page
    assert 'pendingDeletes.add(field);' in page
    assert 'pendingDeletes.delete(field);' in page
    assert "$(dateInputs[field]).value=original[field]||'';" in page
    assert 'if(before) patch[field]=null;' in page
    assert 'return {patch,error:T.dateDeleteExplicit};' in page
    assert 'sendPatch({[btn.dataset.delete]:null}' not in page


def test_validation_and_failed_write_keep_the_pending_changes():
    page = _page()
    assert 'matchesStep(temp,0.5,18)' in page
    assert 'matchesStep(vpd,0.1,0.5)' in page
    assert 'if(!res.ok) throw new Error' in page
    assert "}catch(err){ setStatus(err?.message||'Error','err'); }" in page
    assert 'finally{ setBusy(false); }' in page
    assert 'fill(body?.state?.runtime||body?.state?.stored||fallback);' in page
    assert 'profileLoaded=true;' in page

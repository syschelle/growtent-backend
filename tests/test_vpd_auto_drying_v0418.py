"""v0.418 phase-3 VPD target and backwards-compatible per-tent plans."""
import json

import pytest

# Ensure optional driver stubs are installed when running only this file.
from test_vpd_auto import FakeDB, snapshot  # noqa: F401
from services import vpd_auto
from services import vpd_auto_store as store


def test_old_v0417_plan_loads_with_drying_default_and_preserves_other_targets():
    old = {'enabled': True, 'vegetative': [0.65, 0.85], 'flowering': [1.25, 1.40]}
    restored = vpd_auto.normalize_plan(json.dumps(old))
    assert restored == {**old, 'drying': 0.90}
    assert vpd_auto.normalize_plan(restored) == restored
    assert vpd_auto.target_for(restored, 1, 2) == 0.85
    assert vpd_auto.target_for(restored, 2, 2) == 1.40
    assert vpd_auto.target_for(restored, 3, 1) == 0.90


@pytest.mark.parametrize('week', [None, 0, 1, 2, 10, 261, 'unknown'])
def test_drying_is_one_phase_target_even_if_esp_week_is_missing_or_changes(week):
    assert vpd_auto.phase_week(snapshot(3, week)) == (3, 1)


@pytest.mark.parametrize('invalid', [None, True, '0.90', 0.49, 3.51, 0.901, float('nan'), float('inf')])
def test_drying_target_validation_is_strict(invalid):
    plan = vpd_auto.default_plan()
    plan['drying'] = invalid
    with pytest.raises(ValueError):
        vpd_auto.normalize_plan(plan)


def test_drying_respects_opt_in_and_is_independent_per_tent(monkeypatch):
    one = vpd_auto.default_plan(); one['enabled'] = True
    two = vpd_auto.default_plan(); two['enabled'] = True; two['drying'] = 1.05
    off = vpd_auto.default_plan()
    assert vpd_auto.target_for(off, 3, 1) is None
    db = FakeDB({1: one, 2: two, 3: off})
    monkeypatch.setattr(store, 'get_conn', lambda: db)
    writes = []
    monkeypatch.setattr(store, '_claim', lambda *args: writes.append(args) or False)
    store.reconcile(1, snapshot(3, None, 1.4))
    store.reconcile(2, snapshot(3, 100, 1.4))
    store.reconcile(3, snapshot(3, None, 1.4))
    assert writes == [(1, 3, 1, 0.90), (2, 3, 1, 1.05)]


def test_drying_emits_only_hmac_vpd_write_and_no_weekly_repeat(monkeypatch):
    plan = vpd_auto.default_plan(); plan['enabled'] = True
    monkeypatch.setattr(store, 'get_conn', lambda: FakeDB({4: plan}))
    applied = set()
    def claim(tid, phase, week, target):
        key = (tid, phase, week, target)
        if key in applied: return False
        applied.add(key)
        return True
    monkeypatch.setattr(store, '_claim', claim)
    finished = []
    monkeypatch.setattr(store, '_finish', lambda *args: finished.append(args))
    from services.tent_service import TentService
    writes = []
    monkeypatch.setattr(TentService, 'update_grow_profile',
                        lambda self, tid, patch, username:
                        writes.append((tid, patch.model_dump(exclude_unset=True), username)))
    store.reconcile(4, snapshot(3, None, 1.2))
    store.reconcile(4, snapshot(3, 2, 1.2))
    store.reconcile(4, snapshot(3, 5, 1.2))
    assert writes == [(4, {'targetVPD': 0.90}, 'vpd-automation')]
    assert finished[0][-2:] == ('applied', True)


def test_phase_change_back_to_vegetative_uses_weekly_plan(monkeypatch):
    plan = vpd_auto.default_plan(); plan['enabled'] = True
    assert vpd_auto.phase_week(snapshot(3, None)) == (3, 1)
    assert vpd_auto.phase_week(snapshot(1, 2)) == (1, 2)
    assert vpd_auto.target_for(plan, 1, 2) == 0.70
    assert vpd_auto.target_for(plan, 3, 1) == 0.90

@pytest.mark.parametrize('week', [7, 8, 9, 12, 60, 260])
def test_extended_vegetative_stays_vegetative_and_never_uses_flowering(week):
    plan = vpd_auto.default_plan()
    plan['enabled'] = True
    phase, current_week = vpd_auto.phase_week(snapshot(1, week))
    assert phase == 1  # Never infer phase 2 from the elapsed week.
    assert vpd_auto.target_for(plan, phase, current_week) == plan['vegetative'][-1]
    assert vpd_auto.tracking_week(plan, phase, current_week) == len(plan['vegetative'])
    assert vpd_auto.target_for(plan, phase, current_week) != plan['flowering'][0]


def test_extended_flowering_does_not_switch_to_drying_or_rewrite_every_week():
    plan = vpd_auto.default_plan(); plan['enabled'] = True
    for week in (11, 12, 20, 100):
        phase, current_week = vpd_auto.phase_week(snapshot(2, week))
        assert phase == 2
        assert vpd_auto.target_for(plan, phase, current_week) == plan['flowering'][-1]
        assert vpd_auto.tracking_week(plan, phase, current_week) == len(plan['flowering'])
        assert vpd_auto.target_for(plan, phase, current_week) != plan['drying']


def test_prolonged_vegetative_only_writes_last_value_once_and_never_changes_phase(monkeypatch):
    plan = vpd_auto.default_plan(); plan['enabled'] = True
    monkeypatch.setattr(store, 'get_conn', lambda: FakeDB({11: plan}))
    claimed = set()
    claim_attempts = []
    def claim(*args):
        claim_attempts.append(args)
        if args in claimed: return False
        claimed.add(args)
        return True
    monkeypatch.setattr(store, '_claim', claim)
    monkeypatch.setattr(store, '_finish', lambda *args: None)
    from services.tent_service import TentService
    writes = []
    monkeypatch.setattr(TentService, 'update_grow_profile',
                        lambda self, tid, patch, username:
                        writes.append((tid, patch.model_dump(exclude_unset=True), username)))

    # Six configured vegetative weeks, but deliberately stay in vegetative
    # for ten weeks; week 7+ must not advance the phase or resend targetVPD.
    store.reconcile(11, snapshot(1, 6, .80))
    store.reconcile(11, snapshot(1, 7, .75))
    store.reconcile(11, snapshot(1, 8, .75))
    store.reconcile(11, snapshot(1, 10, .75))
    assert claim_attempts == [(11, 1, 6, 1.15)] * 4
    assert writes == [(11, {'targetVPD': 1.15}, 'vpd-automation')]

    # Only when the ESP itself reports flowering is its schedule used.
    store.reconcile(11, snapshot(2, 1, 1.15))
    assert writes[-1] == (11, {'targetVPD': 1.00}, 'vpd-automation')
    # Drying similarly happens only on ESP-reported phase 3, not by time.
    store.reconcile(11, snapshot(3, None, 1.00))
    assert writes[-1] == (11, {'targetVPD': .90}, 'vpd-automation')
    assert len(writes) == 3


def test_first_activation_during_extended_veg_still_applies_final_veg_target(monkeypatch):
    plan = vpd_auto.default_plan(); plan['enabled'] = True
    monkeypatch.setattr(store, 'get_conn', lambda: FakeDB({12: plan}))
    claimed = []
    monkeypatch.setattr(store, '_claim', lambda *args: claimed.append(args) or False)
    store.reconcile(12, snapshot(1, 14, .55))
    assert claimed == [(12, 1, 6, 1.15)]


def test_prolonged_flowering_only_writes_last_value_once_and_never_changes_phase(monkeypatch):
    """An extended bloom must not start drying or repeat HMAC writes."""
    plan = vpd_auto.default_plan()
    plan['enabled'] = True
    plan['flowering'] = [1.00, 1.20, 1.30]
    monkeypatch.setattr(store, 'get_conn', lambda: FakeDB({21: plan}))
    claimed = set()
    claim_attempts = []

    def claim(*args):
        claim_attempts.append(args)
        if args in claimed:
            return False
        claimed.add(args)
        return True

    monkeypatch.setattr(store, '_claim', claim)
    monkeypatch.setattr(store, '_finish', lambda *args: None)
    from services.tent_service import TentService
    writes = []
    monkeypatch.setattr(
        TentService, 'update_grow_profile',
        lambda self, tid, patch, username:
        writes.append((tid, patch.model_dump(exclude_unset=True), username)),
    )

    # The ESP remains in flowering for six extra weeks. No drying target
    # may be used and a manual VPD override after week 3 must persist.
    for week in (3, 4, 5, 9):
        store.reconcile(21, snapshot(2, week, .80))
    assert claim_attempts == [(21, 2, 3, 1.30)] * 4
    assert writes == [(21, {'targetVPD': 1.30}, 'vpd-automation')]

    # The actual ESP phase transition, not elapsed weeks, invokes drying.
    store.reconcile(21, snapshot(3, None, 1.30))
    assert writes == [
        (21, {'targetVPD': 1.30}, 'vpd-automation'),
        (21, {'targetVPD': .90}, 'vpd-automation'),
    ]
    assert claim_attempts[-1] == (21, 3, 1, .90)


def test_both_phases_keep_their_individual_last_week_with_different_lengths():
    plan = vpd_auto.default_plan()
    plan.update({'enabled': True, 'vegetative': [.60, .80],
                 'flowering': [1.10, 1.20, 1.35, 1.40]})
    for reported_week in (5, 15, 260):
        assert vpd_auto.target_for(plan, 1, reported_week) == .80
        assert vpd_auto.tracking_week(plan, 1, reported_week) == 2
        assert vpd_auto.target_for(plan, 2, reported_week) == 1.40
        assert vpd_auto.tracking_week(plan, 2, reported_week) == 4
    assert vpd_auto.target_for(plan, 3, 1) == .90

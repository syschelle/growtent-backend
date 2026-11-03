"""Regression coverage for heap warning deduplication and thresholds."""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "api" / "app.py").read_text(encoding="utf-8")


def _helpers():
    tree = ast.parse(SOURCE)
    wanted = {"_heap_warning_ready_to_send", "_heap_warning_reason"}
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    assert len(selected) == len(wanted)
    mod = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))

    def _to_float(value):
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    env = {
        "datetime": datetime,
        "_to_float": _to_float,
        "HEAP_WARN_CONSECUTIVE_SAMPLES": 3,
        "HEAP_WARN_COOLDOWN_SECONDS": 3600,
        "HEAP_WARN_FREE_BYTES": 120000,
        "HEAP_WARN_LARGEST_BLOCK_BYTES": 60000,
        "HEAP_WARN_FRAGMENTATION_RATIO": 0.35,
    }
    exec(compile(mod, "app.py", "exec"), env)
    return env


def test_screenshot_values_trigger_only_largest_block_threshold():
    ns = _helpers()
    for free, minimum, largest in [(124880, 66792, 59380), (122648, 64188, 47092)]:
        problem, reason, metrics = ns["_heap_warning_reason"]({
            "sys.freeHeap": free,
            "sys.minFreeHeap": minimum,
            "sys.largestFreeHeapBlock": largest,
        })
        assert problem
        assert reason == f"largestFreeBlock low ({largest} B)"
        assert metrics["ratio"] > 0.35


def test_initial_warning_needs_three_consecutive_samples():
    ns = _helpers()
    t = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
    for n in (0, 1, 2):
        assert not ns["_heap_warning_ready_to_send"]({}, n, t)
    assert ns["_heap_warning_ready_to_send"]({}, 3, t)


def test_active_episode_never_realerts_even_after_cooldown_expires():
    ns = _helpers()
    t = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
    state = {"heap_warn_active": True, "heap_warn_sent_at": (t - timedelta(days=3)).isoformat()}
    assert not ns["_heap_warning_ready_to_send"](state, 3, t)
    assert not ns["_heap_warning_ready_to_send"](state, 1000, t)


def test_recovered_episode_can_alert_again_after_cooldown():
    ns = _helpers()
    t = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
    state = {"heap_warn_active": False, "heap_warn_sent_at": (t - timedelta(hours=2)).isoformat()}
    assert ns["_heap_warning_ready_to_send"](state, 3, t)


def test_cooldown_still_prevents_rapid_repeat_after_recovery():
    ns = _helpers()
    t = datetime(2026, 11, 3, 20, 0, tzinfo=timezone.utc)
    state = {"heap_warn_active": False, "heap_warn_sent_at": (t - timedelta(minutes=5)).isoformat()}
    assert not ns["_heap_warning_ready_to_send"](state, 3, t)


def test_poller_checks_active_episode_and_rearms_on_stable_recovery():
    assert "if _heap_warning_ready_to_send(st, heap_count, now):" in SOURCE
    assert 'st["heap_warn_active"] = True' in SOURCE
    assert "heap_ok_count >= max(1, HEAP_RECOVER_CONSECUTIVE_SAMPLES)" in SOURCE
    assert 'st["heap_warn_active"] = False' in SOURCE
    assert "CanopyOps: heap recovered" in SOURCE

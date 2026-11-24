"""Optional per-tent VPD target schedule, based on the ESP's reported phase/week.

The VPD reference table is informative only. These default weekly target values
are editable by an administrator and never take effect unless explicitly enabled.
Drying uses a single configurable phase target (default 0.90 kPa), with no weekly changes.
Phases are never changed by this service. Extended vegetative/flowering phases
hold their own final programmed target without crossing into another phase.
Unknown or invalid phase data never cause a controller write.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

# Defaults are conservative examples within the existing reference phase bands;
# operators should review the targets for their grow setup before enabling.
DEFAULT_VEGETATIVE = (0.60, 0.70, 0.90, 1.00, 1.10, 1.15)
DEFAULT_FLOWERING = (1.00, 1.10, 1.25, 1.30, 1.35, 1.40, 1.40, 1.35, 1.30, 1.30)
DEFAULT_DRYING = 0.90
RETRY_MINUTES = 30


def default_plan() -> dict:
    return {"enabled": False, "vegetative": list(DEFAULT_VEGETATIVE),
            "flowering": list(DEFAULT_FLOWERING), "drying": DEFAULT_DRYING}


def normalize_plan(value: dict | str | None) -> dict:
    """Strictly validate a full plan; prevent bool/string/NaN values as targets."""
    if value is None or value == "":
        return default_plan()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid VPD automation configuration") from exc
    # v0.417 persisted plans have no drying key. Keep all of them compatible;
    # never reset an already enabled plan during an upgrade.
    if not isinstance(value, dict) or not {"enabled", "vegetative", "flowering"} <= set(value) or \
            set(value) - {"enabled", "vegetative", "flowering", "drying"}:
        raise ValueError("VPD plan must contain enabled, vegetative and flowering (drying is optional for legacy plans)")
    if type(value["enabled"]) is not bool:
        raise ValueError("enabled must be a boolean")
    plan = {"enabled": value["enabled"]}
    for key in ("vegetative", "flowering"):
        items = value[key]
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise ValueError(f"{key} must contain 1 to 20 weekly values")
        normalized = []
        for item in items:
            if type(item) not in (float, int) or not math.isfinite(item) or not 0.50 <= item <= 3.50:
                raise ValueError(f"{key} target must be numeric and between 0.50 and 3.50 kPa")
            if round(item, 2) != item:
                raise ValueError(f"{key} values require no more than two decimal places")
            normalized.append(round(float(item), 2))
        plan[key] = normalized
    drying = value.get("drying", DEFAULT_DRYING)
    if type(drying) not in (int, float) or not math.isfinite(drying) or \
            not 0.50 <= drying <= 3.50 or round(drying, 2) != drying:
        raise ValueError("drying target must be numeric between 0.50 and 3.50 kPa with at most two decimals")
    plan["drying"] = round(float(drying), 2)
    return plan


def phase_week(payload: dict | None) -> tuple[int, int] | None:
    if not isinstance(payload, dict):
        return None
    phase, week = payload.get("settings.grow.currentPhase"), payload.get("settings.grow.currentPhaseWeek")
    # Never trust textual/bool phase fallbacks or the unrelated database grow ID.
    if type(phase) not in (int, float) or not math.isfinite(phase) or \
            int(phase) != phase or int(phase) not in (1, 2, 3):
        return None
    if int(phase) == 3:
        # Drying has one phase-level target, even if the ESP omits its week.
        # Always use canonical week=1 to avoid periodic writes while drying.
        return 3, 1
    if type(week) not in (int, float) or not math.isfinite(week) or \
            int(week) != week or not 1 <= week <= 260:
        return None
    return int(phase), int(week)


def target_for(plan: dict, phase: int, week: int) -> float | None:
    if not plan["enabled"]:
        return None
    if phase == 3:
        return plan["drying"] if week == 1 else None
    if phase not in (1, 2) or not 1 <= week <= 260:
        return None
    values = plan["vegetative" if phase == 1 else "flowering"]
    return values[min(week - 1, len(values) - 1)]


def tracking_week(plan: dict, phase: int, reported_week: int) -> int:
    """Stable plan slot for the ESP's phase/week, without advancing its phase.

    Once a phase runs past its configured weeks, keep the last slot as both
    the target lookup and the durable claim identity. This prevents redundant
    HMAC writes on weeks 7, 8, ... of a six-week vegetative plan, preserving
    a manual override until a real phase transition or plan edit.
    """
    if phase == 3:
        return 1
    if phase == 1:
        return min(reported_week, len(plan["vegetative"]))
    if phase == 2:
        return min(reported_week, len(plan["flowering"]))
    raise ValueError("Unknown grow phase")


def live_target(payload: dict) -> float | None:
    value = payload.get("settings.grow.targetVPD")
    if type(value) not in (int, float) or not math.isfinite(value):
        return None
    return float(value)


def should_apply(applied: tuple | None, phase: int, week: int, target: float) -> bool:
    return applied is None or tuple(applied) != (phase, week, target)


def retry_ready(last_attempt: datetime | None, attempt: tuple | None, desired: tuple, now: datetime) -> bool:
    if attempt != desired or last_attempt is None:
        return True
    if last_attempt.tzinfo is None:
        last_attempt = last_attempt.replace(tzinfo=timezone.utc)
    return now - last_attempt >= timedelta(minutes=RETRY_MINUTES)

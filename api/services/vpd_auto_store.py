"""PostgreSQL-backed optional VPD schedule, one tent and one weekly transition at a time.

The claim row prevents duplicated HMAC writes in multi-worker deployments. No
DB transaction remains open while waiting for a controller response. Retried
failures have a 30-minute cooldown; successful phase/week changes are durable.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from db.database import get_conn
from services.vpd_auto import (default_plan, live_target, normalize_plan, phase_week,
                               retry_ready, should_apply, target_for, tracking_week)

LOGGER = logging.getLogger("growtent.vpd_auto")


def get_plan(tent_id: int) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT vpd_auto_plan_json FROM tents WHERE id=%s", (tent_id,))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(404, "tent not found")
            plan = normalize_plan(row[0])
            cur.execute("""SELECT applied_phase, applied_week, applied_target, applied_at,
                                  attempt_at, last_status FROM tent_vpd_auto_state WHERE tent_id=%s""", (tent_id,))
            state = cur.fetchone()
    return {"tentId": tent_id, "plan": plan, "lastApplied": (
        {"phase": state[0], "week": state[1], "targetVPD": float(state[2]),
         "at": state[3].isoformat() if state[3] else None}
        if state and state[0] is not None else None),
        "lastAttemptAt": state[4].isoformat() if state and state[4] else None,
        "lastStatus": state[5] if state else None}


def get_badge_status(tent_id: int) -> dict:
    """Minimal, authenticated read-only automation state for the dashboard.

    A guest can see whether automation is enabled and whether its latest
    attempt failed, but cannot read the editable plan or controller secrets.
    The join and WHERE clause bind plan and status to the *same* tent.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT t.vpd_auto_plan_json, s.last_status
                           FROM tents AS t
                           LEFT JOIN tent_vpd_auto_state AS s ON s.tent_id = t.id
                           WHERE t.id = %s""", (tent_id,))
            row = cur.fetchone()
    if row is None:
        raise HTTPException(404, "tent not found")
    plan = normalize_plan(row[0])
    enabled = bool(plan["enabled"])
    last_status = row[1] if enabled else None
    # Only report a terminal failure as failed. Pending or no attempt yet
    # means enabled, not failed; it does not imply successful synchronization.
    failed = isinstance(last_status, str) and (
        last_status.startswith("failed") or last_status.startswith("error")
    )
    return {"tentId": tent_id, "enabled": enabled, "lastSyncFailed": failed}


def save_plan(tent_id: int, body: dict) -> dict:
    try:
        plan = normalize_plan(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT vpd_auto_plan_json, backend_write_enabled, backend_controller_url, backend_hmac_secret
                           FROM tents WHERE id=%s FOR UPDATE""", (tent_id,))
            row = cur.fetchone()
            if row is None:
                raise HTTPException(404, "tent not found")
            if plan["enabled"] and not (row[1] and row[2] and row[3]):
                raise HTTPException(409, detail="Configure the controller URL, HMAC secret and Backend Write API before enabling VPD automation")
            previous = normalize_plan(row[0])
            if previous != plan:
                cur.execute("UPDATE tents SET vpd_auto_plan_json=%s WHERE id=%s",
                            (json.dumps(plan, separators=(",", ":")), tent_id))
                # A changed plan / re-enabled automation should apply once on next valid poll.
                cur.execute("DELETE FROM tent_vpd_auto_state WHERE tent_id=%s", (tent_id,))
    return get_plan(tent_id)


def _claim(tent_id: int, phase: int, week: int, target: float) -> bool:
    """Return True for the single worker allowed to make the next attempt."""
    desired = (phase, week, target)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT vpd_auto_plan_json FROM tents WHERE id=%s FOR UPDATE", (tent_id,))
            row = cur.fetchone()
            if not row:
                return False
            plan = normalize_plan(row[0])
            if target_for(plan, phase, week) != target:
                return False
            cur.execute("""INSERT INTO tent_vpd_auto_state (tent_id) VALUES (%s)
                           ON CONFLICT (tent_id) DO NOTHING""", (tent_id,))
            cur.execute("""SELECT applied_phase, applied_week, applied_target,
                                  attempt_phase, attempt_week, attempt_target, attempt_at
                           FROM tent_vpd_auto_state WHERE tent_id=%s FOR UPDATE""", (tent_id,))
            state = cur.fetchone()
            applied = tuple(state[:3]) if state[0] is not None else None
            previous_attempt = tuple(state[3:6]) if state[3] is not None else None
            if not should_apply(applied, phase, week, target):
                return False
            if not retry_ready(state[6], previous_attempt, desired, datetime.now(timezone.utc)):
                return False
            cur.execute("""UPDATE tent_vpd_auto_state SET attempt_phase=%s, attempt_week=%s,
                           attempt_target=%s, attempt_at=NOW(), last_status='pending'
                           WHERE tent_id=%s""", (phase, week, target, tent_id))
            return True


def _finish(tent_id: int, phase: int, week: int, target: float, status: str, success: bool):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Do not overwrite a more recent claim or plan reset.
            if success:
                cur.execute("""UPDATE tent_vpd_auto_state SET applied_phase=%s, applied_week=%s,
                               applied_target=%s, applied_at=NOW(), last_status=%s
                               WHERE tent_id=%s AND attempt_phase=%s AND attempt_week=%s
                               AND attempt_target=%s""",
                            (phase, week, target, status, tent_id, phase, week, target))
            else:
                cur.execute("""UPDATE tent_vpd_auto_state SET last_status=%s
                               WHERE tent_id=%s AND attempt_phase=%s AND attempt_week=%s
                               AND attempt_target=%s""", (status, tent_id, phase, week, target))


def reconcile(tent_id: int, payload: dict) -> None:
    """Called only after a *successful* ESP state poll. Never changes phase.

    A manual VPD change while the same configured plan slot is applied is
    left alone until the next configured slot, an actual ESP-reported phase
    transition, or a plan change. Extended phases do not repeat writes.
    """
    phase_and_week = phase_week(payload)
    if not phase_and_week:  # unknown phase, invalid/partial state
        return
    phase, reported_week = phase_and_week
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT vpd_auto_plan_json FROM tents WHERE id=%s", (tent_id,))
            row = cur.fetchone()
    if not row:
        return
    plan = normalize_plan(row[0])
    target = target_for(plan, phase, reported_week)
    if target is None:
        return
    # An overlong phase stays at its final configured week. Importantly,
    # crossing that boundary does not force a new write of the same target.
    # This never changes currentPhase: the ESP/operator controls that alone.
    week = tracking_week(plan, phase, reported_week)
    if not _claim(tent_id, phase, week, target):
        return
    if live_target(payload) is not None and abs(live_target(payload) - target) < .005:
        _finish(tent_id, phase, week, target, "already_at_target", True)
        return
    try:
        # Existing signed write/verification and audit path; no direct ESP action.
        from services.tent_service import TentService
        TentService().update_grow_profile(tent_id, __import__("models.schemas", fromlist=["GrowProfilePatch"]).GrowProfilePatch(targetVPD=target), "vpd-automation")
    except Exception:
        LOGGER.warning("VPD automation write failed for tent_id=%s phase=%s week=%s; retry after cooldown",
                       tent_id, phase, week)
        _finish(tent_id, phase, week, target, "failed_retry_later", False)
        return
    _finish(tent_id, phase, week, target, "applied", True)
    LOGGER.info("VPD automation updated tent_id=%s phase=%s week=%s target_kpa=%.2f",
                tent_id, phase, week, target)

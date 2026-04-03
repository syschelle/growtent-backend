import json

from fastapi import HTTPException

from db.database import get_conn


def list_tents_raw():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, source_url, rtsp_url,
                       shelly_main_user, shelly_main_password,
                       irrigation_plan_json, irrigation_last_run_date,
                       created_at
                FROM tents
                ORDER BY id
                """
            )
            rows = cur.fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "id": r[0],
                "name": r[1],
                "source_url": r[2],
                "rtsp_url": r[3],
                "shelly_main_user": r[4] or "",
                "shelly_main_password": r[5] or "",
                "irrigation_plan": json.loads(r[6] or "{}") if r[6] else {},
                "irrigation_last_run_date": r[7].isoformat() if r[7] else None,
                "created_at": r[8].isoformat(),
            }
        )
    return out


def create_tent_raw(payload: dict):
    name = str(payload.get("name", "")).strip()
    source_url = str(payload.get("source_url", "")).strip()
    rtsp_url = str(payload.get("rtsp_url", "")).strip() or None
    shelly_main_user = str(payload.get("shelly_main_user", "")).strip() or None
    shelly_main_password = str(payload.get("shelly_main_password", "")).strip() or None

    if not name or not source_url:
        raise HTTPException(status_code=400, detail="name and source_url are required")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tents(name, source_url, rtsp_url, shelly_main_user, shelly_main_password)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (source_url) DO NOTHING
                RETURNING id, name, source_url, rtsp_url, shelly_main_user, shelly_main_password, created_at
                """,
                (name, source_url, rtsp_url, shelly_main_user, shelly_main_password),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=409, detail="tent with same source_url already exists")

    return {
        "id": row[0],
        "name": row[1],
        "source_url": row[2],
        "rtsp_url": row[3],
        "shelly_main_user": row[4] or "",
        "shelly_main_password": row[5] or "",
        "created_at": row[6].isoformat(),
    }


def delete_tent_raw(tent_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM tents
                WHERE id=%s
                RETURNING id, name
                """,
                (tent_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="tent not found")

    return {"ok": True, "deleted": {"id": row[0], "name": row[1]}}


def update_tent_raw(tent_id: int, payload: dict):
    name = str(payload.get("name", "")).strip()
    source_url = str(payload.get("source_url", "")).strip()
    rtsp_url = str(payload.get("rtsp_url", "")).strip() or None
    shelly_main_user = str(payload.get("shelly_main_user", "")).strip() or None
    shelly_main_password = str(payload.get("shelly_main_password", "")).strip() or None

    if not name or not source_url:
        raise HTTPException(status_code=400, detail="name and source_url are required")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tents
                SET name=%s, source_url=%s, rtsp_url=%s, shelly_main_user=%s, shelly_main_password=%s
                WHERE id=%s
                RETURNING id, name, source_url, rtsp_url, shelly_main_user, shelly_main_password, created_at
                """,
                (name, source_url, rtsp_url, shelly_main_user, shelly_main_password, tent_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="tent not found")

    return {
        "id": row[0],
        "name": row[1],
        "source_url": row[2],
        "rtsp_url": row[3],
        "shelly_main_user": row[4] or "",
        "shelly_main_password": row[5] or "",
        "created_at": row[6].isoformat(),
    }


def get_irrigation_plan_raw(tent_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT irrigation_plan_json, irrigation_last_run_date FROM tents WHERE id=%s", (tent_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="tent not found")
            plan = json.loads(row[0] or '{}') if row[0] else {}
            return {
                "tent_id": tent_id,
                "plan": {
                    "enabled": bool(plan.get("enabled", False)),
                    "every_n_days": max(1, int(plan.get("every_n_days", 1) or 1)),
                    "offset_after_light_on_min": max(0, int(plan.get("offset_after_light_on_min", 0) or 0)),
                },
                "last_run_date": row[1].isoformat() if row[1] else None,
            }


def update_irrigation_plan_raw(tent_id: int, payload: dict):
    enabled = bool(payload.get("enabled", False))
    try:
        every_n_days = max(1, int(payload.get("every_n_days", 1)))
        offset_after_light_on_min = max(0, int(payload.get("offset_after_light_on_min", 0)))
    except Exception:
        raise HTTPException(status_code=400, detail="invalid schedule values")

    plan_json = json.dumps(
        {
            "enabled": enabled,
            "every_n_days": every_n_days,
            "offset_after_light_on_min": offset_after_light_on_min,
        }
    )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT irrigation_plan_json, irrigation_last_run_date FROM tents WHERE id=%s", (tent_id,))
            prev = cur.fetchone()
            if not prev:
                raise HTTPException(status_code=404, detail="tent not found")

            prev_plan = json.loads(prev[0] or '{}') if prev[0] else {}
            prev_enabled = bool(prev_plan.get("enabled", False))
            last_run_date = prev[1]

            # On first enable, start schedule from "tomorrow" by treating today as last run.
            # If it already ran today, keep today's date.
            if enabled and not prev_enabled:
                from datetime import date
                today = date.today()
                if not last_run_date or last_run_date < today:
                    last_run_date = today

            cur.execute(
                """
                UPDATE tents
                SET irrigation_plan_json=%s,
                    irrigation_last_run_date=%s
                WHERE id=%s
                RETURNING id
                """,
                (plan_json, last_run_date, tent_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="tent not found")

    return {
        "ok": True,
        "tent_id": tent_id,
        "plan": {
            "enabled": enabled,
            "every_n_days": every_n_days,
            "offset_after_light_on_min": offset_after_light_on_min,
        },
        "last_run_date": last_run_date.isoformat() if last_run_date else None,
    }


def get_exhaust_vpd_plan_raw(tent_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT exhaust_vpd_plan_json, exhaust_vpd_triggered FROM tents WHERE id=%s", (tent_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="tent not found")
            plan = json.loads(row[0] or '{}') if row[0] else {}
            return {
                "tent_id": tent_id,
                "plan": {
                    "enabled": bool(plan.get("enabled", False)),
                    "min_vpd_kpa": max(0.1, float(plan.get("min_vpd_kpa", 0.6) or 0.6)),
                    "hysteresis_kpa": max(0.0, float(plan.get("hysteresis_kpa", 0.05) or 0.05)),
                },
                "triggered": bool(row[1]),
            }


def update_exhaust_vpd_plan_raw(tent_id: int, payload: dict):
    enabled = bool(payload.get("enabled", False))
    try:
        min_vpd_kpa = float(payload.get("min_vpd_kpa", 0.6))
        if min_vpd_kpa < 0.1:
            min_vpd_kpa = 0.1
    except Exception:
        raise HTTPException(status_code=400, detail="invalid min_vpd_kpa")

    try:
        hysteresis_kpa = float(payload.get("hysteresis_kpa", 0.05))
        if hysteresis_kpa < 0.0:
            hysteresis_kpa = 0.0
    except Exception:
        raise HTTPException(status_code=400, detail="invalid hysteresis_kpa")

    plan_json = json.dumps({"enabled": enabled, "min_vpd_kpa": min_vpd_kpa, "hysteresis_kpa": hysteresis_kpa})

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tents
                SET exhaust_vpd_plan_json=%s,
                    exhaust_vpd_triggered=CASE WHEN %s THEN exhaust_vpd_triggered ELSE FALSE END
                WHERE id=%s
                RETURNING id
                """,
                (plan_json, enabled, tent_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="tent not found")

    return {"ok": True, "tent_id": tent_id, "plan": {"enabled": enabled, "min_vpd_kpa": min_vpd_kpa, "hysteresis_kpa": hysteresis_kpa}}

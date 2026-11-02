import json
from datetime import date

from fastapi import HTTPException

from db.database import get_conn
from services.air_sensor_service import normalize_air_sensor_host, validate_safe_sensor_host
from services.grow_write_service import normalize_controller_url, validate_secret_hex


def _clean_optional_str(value):
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _clean_required_str(value):
    if value is None:
        return ""
    return str(value).strip()


def _normalise_backend_controller_url(value):
    if value is None:
        return None
    try:
        return normalize_controller_url(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _validate_growlight_power_drop(value, default=20.0):
    try:
        result = float(default if value is None else value)
    except Exception:
        raise HTTPException(status_code=400, detail="growlight power-drop threshold must be numeric")
    if result < 1.0 or result > 1000.0:
        raise HTTPException(status_code=400, detail="growlight power-drop threshold must be between 1 and 1000 W")
    return result


def _validate_backend_secret(value):
    if value is None:
        return None
    try:
        return validate_secret_hex(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _normalise_pot_strains(value) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except Exception:
            value = {}
    if not isinstance(value, dict):
        value = {}
    result = {}
    for idx in range(1, 4):
        key = f"pot{idx}"
        strain = value.get(key)
        if strain is None:
            strain = value.get(f"pot{idx}_strain")
        result[key] = str(strain or "").strip()[:200]
    return result


def _pot_strains_json(value) -> str:
    return json.dumps(_normalise_pot_strains(value), ensure_ascii=False)


def _normalise_soil_sensor_hosts(value, *, validate_hosts: bool = False) -> list[str]:
    """Return exactly three pot-aligned soil sensor host slots.

    Empty entries are intentionally preserved so sensor 2 remains assigned to
    pot 2 even when pot 1 has no configured sensor.
    """
    if isinstance(value, str):
        try:
            parsed = json.loads(value or "[]")
            value = parsed
        except Exception:
            value = [line.strip() for line in value.splitlines()]
    if isinstance(value, dict):
        value = [value.get(f"sensor{idx}") or value.get(f"soil{idx}") for idx in range(1, 4)]
    if not isinstance(value, list):
        value = []

    result: list[str] = ["", "", ""]
    seen: set[str] = set()
    for index, item in enumerate(value[:3]):
        raw = str(item or "").strip()
        if not raw:
            continue
        try:
            host = validate_safe_sensor_host(raw) if validate_hosts else normalize_air_sensor_host(raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"invalid soil sensor host: {exc}")
        if host and host not in seen:
            result[index] = host
            seen.add(host)
    return result


def _soil_sensors_json(value, *, validate_hosts: bool = False) -> str:
    return json.dumps(_normalise_soil_sensor_hosts(value, validate_hosts=validate_hosts), ensure_ascii=False)


def list_tents_raw():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, source_url, rtsp_url,
                       shelly_main_user, shelly_main_password,
                       irrigation_plan_json, irrigation_last_run_date,
                       pot_strains_json, soil_sensors_json,
                       backend_write_enabled, backend_controller_url, backend_hmac_secret,
                       growlight_power_alert_enabled, growlight_power_drop_w, created_at
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
                "has_shelly_main_password": bool(r[5]),
                "irrigation_plan": json.loads(r[6] or "{}") if r[6] else {},
                "irrigation_last_run_date": r[7].isoformat() if r[7] else None,
                "pot_strains": _normalise_pot_strains(r[8] if len(r) > 8 else None),
                "soil_sensors": _normalise_soil_sensor_hosts(r[9] if len(r) > 9 else None),
                "backend_write_enabled": bool(r[10]),
                "backend_controller_url": r[11] or "",
                "has_backend_hmac_secret": bool(r[12]),
                "growlight_power_alert_enabled": bool(r[13]),
                "growlight_power_drop_w": float(r[14] if r[14] is not None else 20.0),
                "created_at": r[15].isoformat(),
            }
        )
    return out


def create_tent_raw(payload: dict):
    name = _clean_required_str(payload.get("name"))
    source_url = _clean_required_str(payload.get("source_url"))
    rtsp_url = _clean_optional_str(payload.get("rtsp_url"))
    shelly_main_user = _clean_optional_str(payload.get("shelly_main_user"))
    shelly_main_password = _clean_optional_str(payload.get("shelly_main_password"))
    backend_write_enabled = bool(payload.get("backend_write_enabled", False))
    backend_controller_url_raw = _clean_optional_str(payload.get("backend_controller_url"))
    backend_controller_url = _normalise_backend_controller_url(backend_controller_url_raw) if backend_controller_url_raw else None
    backend_hmac_secret_raw = _clean_optional_str(payload.get("backend_hmac_secret"))
    backend_hmac_secret = _validate_backend_secret(backend_hmac_secret_raw) if backend_hmac_secret_raw else None
    if backend_write_enabled and (not backend_controller_url or not backend_hmac_secret):
        raise HTTPException(status_code=400, detail="backend write API requires controller URL and HMAC secret")
    growlight_power_alert_enabled = bool(payload.get("growlight_power_alert_enabled", False))
    growlight_power_drop_w = _validate_growlight_power_drop(payload.get("growlight_power_drop_w", 20.0))
    pot_strains_json = _pot_strains_json(payload.get("pot_strains"))
    soil_sensors_json = _soil_sensors_json(payload.get("soil_sensors"), validate_hosts=True)

    if not name or not source_url:
        raise HTTPException(status_code=400, detail="name and source_url are required")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tents(
                    name, source_url, rtsp_url, shelly_main_user, shelly_main_password,
                    backend_write_enabled, backend_controller_url, backend_hmac_secret,
                    growlight_power_alert_enabled, growlight_power_drop_w,
                    pot_strains_json, soil_sensors_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_url) DO NOTHING
                RETURNING id, name, source_url, rtsp_url, shelly_main_user, shelly_main_password IS NOT NULL,
                          pot_strains_json, soil_sensors_json, backend_write_enabled, backend_controller_url,
                          backend_hmac_secret IS NOT NULL, growlight_power_alert_enabled, growlight_power_drop_w, created_at
                """,
                (name, source_url, rtsp_url, shelly_main_user, shelly_main_password, backend_write_enabled, backend_controller_url, backend_hmac_secret, growlight_power_alert_enabled, growlight_power_drop_w, pot_strains_json, soil_sensors_json),
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
        "has_shelly_main_password": bool(row[5]),
        "pot_strains": _normalise_pot_strains(row[6]),
        "soil_sensors": _normalise_soil_sensor_hosts(row[7]),
        "backend_write_enabled": bool(row[8]),
        "backend_controller_url": row[9] or "",
        "has_backend_hmac_secret": bool(row[10]),
        "growlight_power_alert_enabled": bool(row[11]),
        "growlight_power_drop_w": float(row[12] if row[12] is not None else 20.0),
        "created_at": row[13].isoformat(),
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
    name = _clean_required_str(payload.get("name"))
    source_url = _clean_required_str(payload.get("source_url"))
    rtsp_url = _clean_optional_str(payload.get("rtsp_url"))
    shelly_main_user = _clean_optional_str(payload.get("shelly_main_user"))
    shelly_main_password_raw = _clean_optional_str(payload.get("shelly_main_password")) or ""
    shelly_password_provided = "shelly_main_password" in payload and shelly_main_password_raw != ""
    shelly_password_clear = bool(payload.get("shelly_main_password_clear", False))
    shelly_main_password = shelly_main_password_raw or None

    backend_write_enabled_provided = "backend_write_enabled" in payload
    backend_write_enabled = bool(payload.get("backend_write_enabled", False))
    backend_controller_url_provided = "backend_controller_url" in payload
    backend_controller_url_raw = _clean_optional_str(payload.get("backend_controller_url"))
    backend_controller_url = _normalise_backend_controller_url(backend_controller_url_raw) if backend_controller_url_raw else None
    backend_secret_raw = _clean_optional_str(payload.get("backend_hmac_secret")) or ""
    backend_secret_provided = "backend_hmac_secret" in payload and backend_secret_raw != ""
    backend_secret_clear = bool(payload.get("backend_hmac_secret_clear", False))
    backend_hmac_secret = _validate_backend_secret(backend_secret_raw) if backend_secret_provided else None

    growlight_power_alert_enabled_provided = "growlight_power_alert_enabled" in payload
    growlight_power_alert_enabled = bool(payload.get("growlight_power_alert_enabled", False))
    growlight_power_drop_w_provided = "growlight_power_drop_w" in payload
    growlight_power_drop_w = _validate_growlight_power_drop(payload.get("growlight_power_drop_w", 20.0)) if growlight_power_drop_w_provided else 20.0

    pot_strains_provided = "pot_strains" in payload
    pot_strains_json = _pot_strains_json(payload.get("pot_strains")) if pot_strains_provided else None
    soil_sensors_provided = "soil_sensors" in payload
    soil_sensors_json = _soil_sensors_json(payload.get("soil_sensors"), validate_hosts=True) if soil_sensors_provided else None

    if not name or not source_url:
        raise HTTPException(status_code=400, detail="name and source_url are required")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT backend_write_enabled, backend_controller_url, backend_hmac_secret, growlight_power_alert_enabled, growlight_power_drop_w FROM tents WHERE id=%s FOR UPDATE",
                (tent_id,),
            )
            current = cur.fetchone()
            if not current:
                raise HTTPException(status_code=404, detail="tent not found")

            effective_enabled = backend_write_enabled if backend_write_enabled_provided else bool(current[0])
            effective_controller = backend_controller_url if backend_controller_url_provided else (current[1] or None)
            if backend_secret_clear:
                effective_secret = None
            elif backend_secret_provided:
                effective_secret = backend_hmac_secret
            else:
                effective_secret = current[2] or None
            if effective_enabled and (not effective_controller or not effective_secret):
                raise HTTPException(status_code=400, detail="backend write API requires controller URL and HMAC secret")

            cur.execute(
                """
                UPDATE tents
                SET name=%s,
                    source_url=%s,
                    rtsp_url=%s,
                    shelly_main_user=%s,
                    shelly_main_password=CASE
                        WHEN %s THEN NULL
                        WHEN %s THEN %s
                        ELSE shelly_main_password
                    END,
                    backend_write_enabled=CASE WHEN %s::boolean THEN %s::boolean ELSE backend_write_enabled END,
                    backend_controller_url=CASE WHEN %s::boolean THEN %s::text ELSE backend_controller_url END,
                    backend_hmac_secret=CASE
                        WHEN %s THEN NULL
                        WHEN %s THEN %s
                        ELSE backend_hmac_secret
                    END,
                    growlight_power_alert_enabled=CASE WHEN %s::boolean THEN %s::boolean ELSE growlight_power_alert_enabled END,
                    growlight_power_drop_w=CASE WHEN %s::boolean THEN %s::double precision ELSE growlight_power_drop_w END,
                    pot_strains_json=CASE WHEN %s::boolean THEN %s::text ELSE pot_strains_json END,
                    soil_sensors_json=CASE WHEN %s::boolean THEN %s::text ELSE soil_sensors_json END
                WHERE id=%s
                RETURNING id, name, source_url, rtsp_url, shelly_main_user, shelly_main_password IS NOT NULL,
                          pot_strains_json, soil_sensors_json, backend_write_enabled, backend_controller_url,
                          backend_hmac_secret IS NOT NULL, growlight_power_alert_enabled, growlight_power_drop_w, created_at
                """,
                (
                    name, source_url, rtsp_url, shelly_main_user,
                    shelly_password_clear, shelly_password_provided, shelly_main_password,
                    backend_write_enabled_provided, backend_write_enabled,
                    backend_controller_url_provided, backend_controller_url,
                    backend_secret_clear, backend_secret_provided, backend_hmac_secret,
                    growlight_power_alert_enabled_provided, growlight_power_alert_enabled,
                    growlight_power_drop_w_provided, growlight_power_drop_w,
                    pot_strains_provided, pot_strains_json, soil_sensors_provided, soil_sensors_json, tent_id,
                ),
            )
            row = cur.fetchone()

    return {
        "id": row[0],
        "name": row[1],
        "source_url": row[2],
        "rtsp_url": row[3],
        "shelly_main_user": row[4] or "",
        "has_shelly_main_password": bool(row[5]),
        "pot_strains": _normalise_pot_strains(row[6]),
        "soil_sensors": _normalise_soil_sensor_hosts(row[7]),
        "backend_write_enabled": bool(row[8]),
        "backend_controller_url": row[9] or "",
        "has_backend_hmac_secret": bool(row[10]),
        "growlight_power_alert_enabled": bool(row[11]),
        "growlight_power_drop_w": float(row[12] if row[12] is not None else 20.0),
        "created_at": row[13].isoformat(),
    }

def get_tent_write_config_raw(tent_id: int) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, source_url, backend_write_enabled, backend_controller_url, backend_hmac_secret
                FROM tents WHERE id=%s
                """,
                (tent_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="tent not found")
    return {
        "id": int(row[0]),
        "name": row[1] or "",
        "source_url": row[2] or "",
        "backend_write_enabled": bool(row[3]),
        "backend_controller_url": row[4] or "",
        "_backend_hmac_secret": row[5] or "",
    }


def insert_grow_write_audit_raw(
    *,
    tent_id: int,
    tent_name: str,
    admin_username: str,
    changed_fields: list[str],
    firmware_request_id=None,
    http_status: int | None = None,
    result_code: str = "",
    verification_ok: bool = False,
) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO grow_write_audit(
                    tent_id, tent_name, admin_username, changed_fields_json, firmware_request_id,
                    http_status, result_code, verification_ok
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    tent_id, tent_name, admin_username,
                    json.dumps(list(changed_fields), ensure_ascii=False),
                    str(firmware_request_id) if firmware_request_id is not None else None,
                    http_status, str(result_code or "")[:120], bool(verification_ok),
                ),
            )


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

    raw_last_run_date = payload.get("last_run_date", None)
    manual_last_run_date = None
    if raw_last_run_date is not None and str(raw_last_run_date).strip() != "":
        try:
            manual_last_run_date = date.fromisoformat(str(raw_last_run_date).strip())
        except Exception:
            raise HTTPException(status_code=400, detail="invalid last_run_date (expected YYYY-MM-DD)")

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

            plan_changed = (
                bool(prev_plan.get("enabled", False)) != enabled
                or int(prev_plan.get("every_n_days", 1) or 1) != every_n_days
                or int(prev_plan.get("offset_after_light_on_min", 0) or 0) != offset_after_light_on_min
            )

            if manual_last_run_date is not None:
                last_run_date = manual_last_run_date
            else:
                # Prevent immediate schedule-triggered watering right after plan edits.
                # When an enabled plan is newly enabled or changed, baseline to "today".
                if enabled and (not prev_enabled or plan_changed):
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

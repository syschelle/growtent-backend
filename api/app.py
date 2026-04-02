import base64
import hashlib
import io
import csv
import json
import os
import secrets
import threading
import time
import tempfile
import zipfile
import re
import math
import logging
from datetime import datetime, timezone, date, timedelta
from urllib.parse import quote_plus, urlsplit

import httpx
import psycopg2
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://growtent:growtent@db:5432/growtent")
# POLL_URL removed: no default tent source is injected on fresh installs.
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
GO2RTC_BASE_URL = os.getenv("GO2RTC_BASE_URL", "http://go2rtc:1984")
PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/project")
GROMATE_API_PASSWORD = os.getenv("GROMATE_API_PASSWORD", "")
APP_VERSION = "v0.203"

app = FastAPI(title="GrowTent Backend PoC")
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

SESSIONS: dict[str, dict] = {}
TWOFA_ENROLL: dict[str, dict] = {}
SESSION_TTL_SECONDS = 60 * 60 * 12
EMA_ALPHA = float(os.getenv("EMA_ALPHA", "0.3"))
EMA_STATE: dict[int, dict] = {}
SENSOR_INIT: dict[int, bool] = {}
LOGGER = logging.getLogger("growtent.api")

TEMP_MIN_C = float(os.getenv("SENSOR_TEMP_MIN_C", "-20"))
TEMP_MAX_C = float(os.getenv("SENSOR_TEMP_MAX_C", "80"))
VPD_MIN_KPA = float(os.getenv("SENSOR_VPD_MIN_KPA", "0"))
VPD_MAX_KPA = float(os.getenv("SENSOR_VPD_MAX_KPA", "6"))

PUSHOVER_APP_TOKEN = (os.getenv("PUSHOVER_APP_TOKEN") or "").strip()
PUSHOVER_USER_KEY = (os.getenv("PUSHOVER_USER_KEY") or "").strip()
PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
PUSHOVER_DEVICE = (os.getenv("PUSHOVER_DEVICE") or "").strip()
POLL_NOTIFY_STATE: dict[int, dict] = {}


@app.get("/", response_class=HTMLResponse)
def root_page():
    return RedirectResponse(url="/app?page=dashboard", status_code=302)




@app.get("/favicon.svg")
def favicon_svg():
    svg = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
  <defs>
    <linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0%' stop-color='#22d3ee'/>
      <stop offset='100%' stop-color='#22c55e'/>
    </linearGradient>
  </defs>
  <rect x='2' y='2' width='60' height='60' rx='14' fill='#0f172a'/>
  <path d='M16 42c0-10 7-18 16-20 0 11-7 20-16 20z' fill='url(#g)'/>
  <path d='M48 42c0-10-7-18-16-20 0 11 7 20 16 20z' fill='url(#g)' opacity='0.9'/>
  <circle cx='32' cy='26' r='4' fill='#86efac'/>
</svg>"""
    return HTMLResponse(content=svg, media_type="image/svg+xml")


@app.get("/auth/login", response_class=HTMLResponse)
def auth_login_page():
    return """
    <html><head><title>CanopyOps Login</title><meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      :root{--bg:#0f172a;--text:#e2e8f0;--card:#1e293b;--input:#0b1220;--inputBorder:rgba(148,163,184,.25);--btn:#2563eb}
      :root[data-theme='light']{--bg:#eef2f5;--text:#0f172a;--card:#f8fafc;--input:#ffffff;--inputBorder:rgba(51,65,85,.22);--btn:#1d4ed8}
      body{font-family:Arial;background:var(--bg);color:var(--text);display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
      .card{background:var(--card);padding:16px;border-radius:12px;max-width:360px;width:92%;box-shadow:0 2px 10px rgba(2,6,23,.2)}
      input,button{width:100%;padding:10px;border-radius:8px;margin-top:8px}
      input{background:var(--input);color:var(--text);border:1px solid var(--inputBorder)}
      button{background:var(--btn);color:#fff;border:0}
      .hidden{display:none}
    </style></head>
    <body><div class='card'><h3>CanopyOps Login</h3>
      <div id='step1'>
        <input id='u' placeholder='Username'/><input id='p' type='password' placeholder='Password'/><button id='b1'>Weiter</button>
      </div>
      <div id='step2' class='hidden'>
        <input id='c' placeholder='2FA Code'/><input id='r' placeholder='Recovery Code (optional)'/><button id='b2'>Anmelden</button>
      </div>
      <div id='m' style='margin-top:10px;opacity:.9'></div></div>
    <script>
      try {
        const t = (localStorage.getItem('gt_theme') || 'dark');
        document.documentElement.setAttribute('data-theme', t === 'light' ? 'light' : 'dark');
      } catch {}
      let preauthToken='';
      b1.onclick=async()=>{const res=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u.value.trim(),password:p.value})});const j=await res.json().catch(()=>({}));if(!res.ok){m.textContent=j.detail||'Login failed';return;}if(j.requires2fa){preauthToken=j.preauth_token||'';step1.classList.add('hidden');step2.classList.remove('hidden');m.textContent='2FA Code eingeben';setTimeout(()=>c.focus(),0);return;}location.href='/app?page=dashboard';};
      b2.onclick=async()=>{const res=await fetch('/auth/login/2fa',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preauth_token:preauthToken,code:c.value.trim(),recoveryCode:r.value.trim()})});const j=await res.json().catch(()=>({}));if(!res.ok){m.textContent=j.detail||'2FA failed';setTimeout(()=>c.focus(),0);return;}location.href='/app?page=dashboard';};
      [u,p].forEach(el=>el.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();b1.click();}}));
      [c,r].forEach(el=>el.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();b2.click();}}));
    </script></body></html>
    """


class LoginPayload(BaseModel):
    username: str
    password: str


class Login2FAPayload(BaseModel):
    preauth_token: str
    code: str | None = None
    recoveryCode: str | None = None


class StatusNotifyPayload(BaseModel):
    title: str | None = None
    message: str
    priority: int = 0
    device: str | None = None


def _send_pushover(title: str, message: str, priority: int = 0, device: str | None = None) -> bool:
    try:
        cfg = load_auth_config()
        token = (cfg.get("pushover_app_token") or PUSHOVER_APP_TOKEN or "").strip()
        user = (cfg.get("pushover_user_key") or PUSHOVER_USER_KEY or "").strip()
        if not token or not user:
            return False
        data = {
            "token": token,
            "user": user,
            "title": title[:100],
            "message": message[:1024],
            "priority": int(priority),
        }
        dev = (device or (cfg.get("pushover_device") or "") or PUSHOVER_DEVICE or "").strip()
        if dev:
            data["device"] = dev
        with httpx.Client(timeout=8.0) as client:
            r = client.post(PUSHOVER_API_URL, data=data)
            return r.status_code == 200
    except Exception:
        return False


@app.post("/notify/status")
def notify_status(payload: StatusNotifyPayload):
    ok = _send_pushover(payload.title or "CanopyOps", payload.message, payload.priority, payload.device)
    if not ok:
        raise HTTPException(status_code=503, detail="Pushover not configured or send failed")
    return {"ok": True}


@app.post("/auth/login")
def auth_login(payload: LoginPayload):
    cfg = load_auth_config()
    if not cfg.get("enabled"):
        token = secrets.token_urlsafe(32)
        SESSIONS[token] = {"authenticated": True, "role": "admin", "expires_at": time.time() + SESSION_TTL_SECONDS}
        resp = JSONResponse({"ok": True})
        resp.set_cookie("caop_session", token, httponly=True, samesite="lax", max_age=SESSION_TTL_SECONDS)
        return resp

    admin_user = (cfg.get("username") or "")
    admin_hash = (cfg.get("password_hash") or "")
    guest_user = (cfg.get("guest_username") or "")
    guest_hash = (cfg.get("guest_password_hash") or "")
    guest_enabled = bool(cfg.get("guest_enabled"))
    guest_expires_at = cfg.get("guest_expires_at")

    is_admin_login = payload.username == admin_user and hashlib.sha256(payload.password.encode("utf-8")).hexdigest() == admin_hash
    is_guest_login = payload.username == guest_user and guest_enabled and guest_hash and hashlib.sha256(payload.password.encode("utf-8")).hexdigest() == guest_hash

    if not is_admin_login and not is_guest_login:
        raise HTTPException(status_code=401, detail="invalid credentials")

    if is_guest_login:
        guest_exp_ts = None
        try:
            if guest_expires_at:
                guest_exp_ts = datetime.fromisoformat(str(guest_expires_at).replace('Z', '+00:00')).timestamp()
        except Exception:
            guest_exp_ts = None
        if guest_exp_ts is None or guest_exp_ts <= time.time():
            raise HTTPException(status_code=401, detail="guest access expired")
        token = secrets.token_urlsafe(32)
        exp = min(time.time() + SESSION_TTL_SECONDS, guest_exp_ts)
        SESSIONS[token] = {"authenticated": True, "role": "guest", "username": payload.username, "expires_at": exp}
        resp = JSONResponse({"ok": True, "role": "guest", "guest_expires_at": guest_expires_at})
        resp.set_cookie("caop_session", token, httponly=True, samesite="lax", max_age=max(1, int(exp - time.time())))
        return resp

    if cfg.get("twofa_enabled"):
        pre = secrets.token_urlsafe(24)
        SESSIONS[pre] = {"preauth": True, "role": "admin", "username": payload.username, "expires_at": time.time() + 300}
        return {"ok": True, "requires2fa": True, "preauth_token": pre}

    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"authenticated": True, "role": "admin", "expires_at": time.time() + SESSION_TTL_SECONDS}
    resp = JSONResponse({"ok": True})
    resp.set_cookie("caop_session", token, httponly=True, samesite="lax", max_age=SESSION_TTL_SECONDS)
    return resp


@app.post("/auth/login/2fa")
def auth_login_2fa(payload: Login2FAPayload):
    s = SESSIONS.get(payload.preauth_token)
    if not s or not s.get("preauth") or s.get("expires_at", 0) < time.time():
        raise HTTPException(status_code=401, detail="2FA session expired")

    cfg = load_auth_config()
    if not cfg.get("twofa_enabled"):
        raise HTTPException(status_code=400, detail="2FA not enabled")

    code_ok = False
    secret = cfg.get("totp_secret") or ""
    if payload.code:
        try:
            code_ok = pyotp.TOTP(secret).verify(payload.code, valid_window=1)
        except Exception:
            code_ok = False

    if not code_ok and payload.recoveryCode:
        try:
            rc_list = json.loads(cfg.get("recovery_codes_json") or "[]")
        except Exception:
            rc_list = []
        rc_hash = hashlib.sha256(payload.recoveryCode.strip().encode("utf-8")).hexdigest()
        matched = False
        new_list = []
        for item in rc_list:
            if not matched and item.get("hash") == rc_hash and not item.get("used"):
                item["used"] = True
                matched = True
            new_list.append(item)
        if matched:
            code_ok = True
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE app_auth_config SET recovery_codes_json=%s, updated_at=NOW() WHERE id=1", (json.dumps(new_list),))

    if not code_ok:
        raise HTTPException(status_code=401, detail="2FA code or recovery code required")

    SESSIONS.pop(payload.preauth_token, None)
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"authenticated": True, "role": "admin", "expires_at": time.time() + SESSION_TTL_SECONDS}
    resp = JSONResponse({"ok": True})
    resp.set_cookie("caop_session", token, httponly=True, samesite="lax", max_age=SESSION_TTL_SECONDS)
    return resp


@app.post("/auth/logout")
def auth_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("caop_session")
    return resp


@app.get("/auth/whoami")
def auth_whoami(request: Request):
    s = get_session(request.cookies.get("caop_session"))
    if not s:
        return {"authenticated": False, "role": "none"}
    return {
        "authenticated": True,
        "role": s.get("role") or "admin",
        "username": s.get("username") or None,
        "expires_at": s.get("expires_at"),
    }


@app.get("/auth/qr.png")
def auth_qr_png(u: str):
    img = qrcode.make(u)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def load_auth_config():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT enabled, username, password_hash, twofa_enabled, totp_secret, recovery_codes_json, guest_enabled, guest_username, guest_password_hash, guest_expires_at, pushover_device, pushover_app_token, pushover_user_key, gromate_api_password, history_api_enabled FROM app_auth_config WHERE id=1")
            row = cur.fetchone()
            if not row:
                return {"enabled": False, "username": None, "password_hash": None, "twofa_enabled": False, "totp_secret": None, "recovery_codes_json": "[]", "guest_enabled": False, "guest_username": None, "guest_password_hash": None, "guest_expires_at": None, "pushover_device": "", "pushover_app_token": "", "pushover_user_key": "", "gromate_api_password": "", "history_api_enabled": True}
            return {
                "enabled": bool(row[0]),
                "username": row[1],
                "password_hash": row[2],
                "twofa_enabled": bool(row[3]) if row[3] is not None else False,
                "totp_secret": row[4],
                "recovery_codes_json": row[5] or "[]",
                "guest_enabled": bool(row[6]) if row[6] is not None else False,
                "guest_username": row[7],
                "guest_password_hash": row[8],
                "guest_expires_at": row[9].isoformat() if row[9] else None,
                "pushover_device": row[10] or "",
                "pushover_app_token": row[11] or "",
                "pushover_user_key": row[12] or "",
                "gromate_api_password": row[13] or "",
                "history_api_enabled": bool(row[14]) if row[14] is not None else True,
            }


def get_session(token: str | None):
    if not token:
        return None
    s = SESSIONS.get(token)
    if not s:
        return None
    if s.get("expires_at", 0) < time.time():
        SESSIONS.pop(token, None)
        return None
    if not bool(s.get("authenticated")):
        return None
    return s


def is_valid_session(token: str | None) -> bool:
    return get_session(token) is not None


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    exempt_prefixes = ("/health", "/favicon.svg", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/auth/")
    if path == "/api/history":
        return await call_next(request)
    if path.startswith(exempt_prefixes):
        return await call_next(request)

    try:
        cfg = load_auth_config()
    except Exception:
        cfg = {"enabled": False}

    if cfg.get("enabled"):
        token = request.cookies.get("caop_session")
        session = get_session(token)
        if not session:
            if "text/html" in (request.headers.get("accept") or ""):
                return RedirectResponse(url="/auth/login", status_code=302)
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})

        if (session.get("role") or "admin") == "guest":
            if path.startswith("/config") or path.startswith("/setup") or (path.startswith("/app") and request.query_params.get("page") == "setup"):
                if "text/html" in (request.headers.get("accept") or ""):
                    return RedirectResponse(url="/app?page=dashboard", status_code=302)
                return JSONResponse(status_code=403, content={"detail": "guest mode: access denied"})
            if request.method.upper() != "GET" and path != "/auth/logout":
                return JSONResponse(status_code=403, content={"detail": "guest mode: write actions disabled"})

    response = await call_next(request)
    if request.method == "GET" and (
        path.startswith("/app") or path.startswith("/setup") or path.startswith("/dashboard") or path.startswith("/changelog")
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tents (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_url TEXT NOT NULL UNIQUE,
                    rtsp_url TEXT,
                    shelly_main_user TEXT,
                    shelly_main_password TEXT,
                    irrigation_plan_json TEXT NOT NULL DEFAULT '{"enabled":false,"every_n_days":1,"offset_after_light_on_min":0}',
                    irrigation_last_run_date DATE,
                    exhaust_vpd_plan_json TEXT NOT NULL DEFAULT '{"enabled":false,"min_vpd_kpa":0.6,"hysteresis_kpa":0.05}',
                    exhaust_vpd_triggered BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute("ALTER TABLE tents ADD COLUMN IF NOT EXISTS rtsp_url TEXT;")
            cur.execute("ALTER TABLE tents ADD COLUMN IF NOT EXISTS shelly_main_user TEXT;")
            cur.execute("ALTER TABLE tents ADD COLUMN IF NOT EXISTS shelly_main_password TEXT;")
            cur.execute("ALTER TABLE tents ADD COLUMN IF NOT EXISTS irrigation_plan_json TEXT NOT NULL DEFAULT '{\"enabled\":false,\"every_n_days\":1,\"offset_after_light_on_min\":0}';")
            cur.execute("ALTER TABLE tents ADD COLUMN IF NOT EXISTS irrigation_last_run_date DATE;")
            cur.execute("ALTER TABLE tents ADD COLUMN IF NOT EXISTS exhaust_vpd_plan_json TEXT NOT NULL DEFAULT '{\"enabled\":false,\"min_vpd_kpa\":0.6,\"hysteresis_kpa\":0.05}';")
            cur.execute("ALTER TABLE tents ADD COLUMN IF NOT EXISTS exhaust_vpd_triggered BOOLEAN NOT NULL DEFAULT FALSE;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS tent_state (
                    id BIGSERIAL PRIMARY KEY,
                    tent_id INTEGER NOT NULL REFERENCES tents(id) ON DELETE CASCADE,
                    captured_at TIMESTAMPTZ NOT NULL,
                    payload JSONB NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_auth_config (
                    id INTEGER PRIMARY KEY,
                    enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    username TEXT,
                    password_hash TEXT,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS twofa_enabled BOOLEAN NOT NULL DEFAULT FALSE;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS totp_secret TEXT;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS recovery_codes_json TEXT NOT NULL DEFAULT '[]';")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS guest_enabled BOOLEAN NOT NULL DEFAULT FALSE;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS guest_username TEXT;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS guest_password_hash TEXT;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS guest_expires_at TIMESTAMPTZ;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS pushover_device TEXT;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS pushover_app_token TEXT;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS pushover_user_key TEXT;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS gromate_api_password TEXT;")
            cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS history_api_enabled BOOLEAN NOT NULL DEFAULT TRUE;")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tent_state_tent_time ON tent_state(tent_id, captured_at DESC);")
            cur.execute(
                """
                INSERT INTO app_auth_config(id, enabled)
                VALUES (1, FALSE)
                ON CONFLICT (id) DO NOTHING;
                """
            )
            # No default tent auto-insert on fresh installs.


def _to_float(v):
    try:
        n = float(v)
        return n if n == n else None
    except Exception:
        return None


def _calc_vpd_kpa(temp_c: float | None, leaf_offset_c: float | None, humidity_pct: float | None):
    if temp_c is None or humidity_pct is None:
        return None
    t_leaf = float(temp_c) + float(leaf_offset_c or 0.0)
    rh = max(0.0, min(100.0, float(humidity_pct)))
    svp = 0.6108 * math.exp((17.27 * t_leaf) / (t_leaf + 237.3))
    return max(0.0, svp * (1.0 - rh / 100.0))


def _ema_next(prev: float | None, cur: float | None, alpha: float):
    if cur is None:
        return prev
    if prev is None:
        return cur
    a = max(0.0, min(1.0, float(alpha)))
    return (a * cur) + ((1.0 - a) * prev)


def _sensor_values_valid(temp_c: float | None, humidity_pct: float | None, vpd_kpa: float | None) -> bool:
    if temp_c is None or humidity_pct is None or vpd_kpa is None:
        return False
    if not (TEMP_MIN_C <= temp_c <= TEMP_MAX_C):
        return False
    if not (0.0 <= humidity_pct <= 100.0):
        return False
    if not (VPD_MIN_KPA <= vpd_kpa <= VPD_MAX_KPA):
        return False
    return True


def _get_last_payload(tent_id: int):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT payload
                    FROM tent_state
                    WHERE tent_id=%s
                    ORDER BY captured_at DESC
                    LIMIT 1
                    """,
                    (tent_id,),
                )
                row = cur.fetchone()
                return (row[0] or {}) if row else {}
    except Exception:
        return {}


def save_state(tent_id: int, payload: dict):
    captured_at = datetime.now(timezone.utc)

    # Source of truth: controller-provided channels.
    # Keep explicit raw and smoothed values if provided by firmware.
    d = dict(payload or {})

    raw_t = _to_float(d.get("sensors.cur.temperatureRawC"))
    raw_h = _to_float(d.get("sensors.cur.humidityRawPct"))
    if raw_t is None:
        raw_t = _to_float(d.get("sensors.raw.temperatureC"))
    if raw_h is None:
        raw_h = _to_float(d.get("sensors.raw.humidityPct"))

    leaf_offset = _to_float(d.get("settings.grow.offsetLeafTemperature")) or 0.0
    raw_vpd = _to_float(d.get("sensors.raw.vpdKpa"))
    if raw_vpd is None:
        raw_vpd = _calc_vpd_kpa(raw_t, leaf_offset, raw_h)

    # If current sample is incomplete/invalid, reuse last known values for continuity.
    if not _sensor_values_valid(raw_t, raw_h, raw_vpd):
        prev = _get_last_payload(tent_id)
        if raw_t is None:
            raw_t = _to_float(prev.get("sensors.raw.temperatureC"))
        if raw_h is None:
            raw_h = _to_float(prev.get("sensors.raw.humidityPct"))
        if raw_vpd is None:
            raw_vpd = _to_float(prev.get("sensors.raw.vpdKpa"))
        if raw_vpd is None:
            raw_vpd = _calc_vpd_kpa(raw_t, leaf_offset, raw_h)

    # Mark tent sensor initialization as valid from first accepted sample.
    if not SENSOR_INIT.get(tent_id):
        SENSOR_INIT[tent_id] = True

    sm_t = _to_float(d.get("sensors.smoothed.temperatureC"))
    sm_h = _to_float(d.get("sensors.smoothed.humidityPct"))
    if sm_t is None:
        sm_t = _to_float(d.get("sensors.cur.temperatureC"))
    if sm_h is None:
        sm_h = _to_float(d.get("sensors.cur.humidityPct"))
    sm_vpd = _to_float(d.get("sensors.smoothed.vpdKpa"))
    if sm_t is None or sm_h is None:
        prev = _get_last_payload(tent_id)
        if sm_t is None:
            sm_t = _to_float(prev.get("sensors.smoothed.temperatureC"))
        if sm_h is None:
            sm_h = _to_float(prev.get("sensors.smoothed.humidityPct"))
    if sm_vpd is None:
        sm_vpd = _calc_vpd_kpa(sm_t, leaf_offset, sm_h)
    if sm_vpd is None:
        prev = _get_last_payload(tent_id)
        sm_vpd = _to_float(prev.get("sensors.smoothed.vpdKpa"))

    payload = dict(payload or {})
    payload["sensors.raw.temperatureC"] = raw_t
    payload["sensors.raw.humidityPct"] = raw_h
    payload["sensors.raw.vpdKpa"] = raw_vpd
    payload["sensors.smoothed.temperatureC"] = sm_t
    payload["sensors.smoothed.humidityPct"] = sm_h
    payload["sensors.smoothed.vpdKpa"] = sm_vpd

    # Keep UI-facing cur keys populated for continuity when controller sends nulls.
    if _to_float(payload.get("sensors.cur.temperatureC")) is None:
        payload["sensors.cur.temperatureC"] = sm_t
    if _to_float(payload.get("sensors.cur.humidityPct")) is None:
        payload["sensors.cur.humidityPct"] = sm_h
    if _to_float(payload.get("sensors.cur.vpdKpa")) is None:
        payload["sensors.cur.vpdKpa"] = sm_vpd
    if _to_float(payload.get("sensors.cur.temperatureRawC")) is None:
        payload["sensors.cur.temperatureRawC"] = raw_t
    if _to_float(payload.get("sensors.cur.humidityRawPct")) is None:
        payload["sensors.cur.humidityRawPct"] = raw_h
    if _to_float(payload.get("sensors.cur.vpdRawKpa")) is None:
        payload["sensors.cur.vpdRawKpa"] = raw_vpd

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tent_state(tent_id, captured_at, payload) VALUES (%s, %s, %s::jsonb)",
                (tent_id, captured_at, json.dumps(payload)),
            )


def cleanup_old_data():
    # Keep only the last RETENTION_DAYS days of history.
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM tent_state
                WHERE captured_at < NOW() - (%s || ' days')::interval
                """,
                (RETENTION_DAYS,),
            )


def list_tent_sources():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, source_url, rtsp_url, shelly_main_user, shelly_main_password, irrigation_plan_json, irrigation_last_run_date, exhaust_vpd_plan_json, exhaust_vpd_triggered FROM tents ORDER BY id")
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "source_url": r[2],
                    "rtsp_url": r[3],
                    "shelly_main_user": r[4] or "",
                    "shelly_main_password": r[5] or "",
                    "irrigation_plan": json.loads(r[6] or '{}') if r[6] else {},
                    "irrigation_last_run_date": r[7].isoformat() if r[7] else None,
                    "exhaust_vpd_plan": json.loads(r[8] or '{}') if r[8] else {},
                    "exhaust_vpd_triggered": bool(r[9]),
                }
                for r in rows
            ]


def register_rtsp_stream(tent_id: int, rtsp_url: str):
    if not rtsp_url:
        return
    try:
        with httpx.Client(timeout=4.0) as client:
            client.put(f"{GO2RTC_BASE_URL}/api/streams", json={f"tent_{tent_id}": rtsp_url})
    except Exception as e:
        print(f"[go2rtc] register failed for tent #{tent_id}: {e}")


def _refresh_main_shelly_in_payload(payload: dict, tent: dict):
    try:
        ip = str((payload or {}).get("settings.shelly.main.ip") or "").strip()
        if not ip:
            return
        gen = int((payload or {}).get("settings.shelly.main.gen") or 2)
        base = ip if ip.startswith("http://") or ip.startswith("https://") else f"http://{ip}"
        user = (tent.get("shelly_main_user") or "").strip()
        pw = (tent.get("shelly_main_password") or "").strip()
        auth_candidates = _shelly_auth_candidates(user, pw)

        with httpx.Client(timeout=4.0) as client:
            last_err = None
            for auth in auth_candidates:
                try:
                    if gen >= 2:
                        r = client.get(f"{base}/rpc/Shelly.GetStatus", auth=auth)
                        r.raise_for_status()
                        j = r.json() or {}
                        sw = (j.get("switch:0") or {})
                        watt = sw.get("apower")
                        wh = (sw.get("aenergy") or {}).get("total")
                    else:
                        r = client.get(f"{base}/status", auth=auth)
                        r.raise_for_status()
                        j = r.json() or {}
                        meters = j.get("meters") or [{}]
                        watt = (meters[0] or {}).get("power")
                        wh = (meters[0] or {}).get("total")
                    break
                except Exception as e:
                    last_err = e
                    continue
            else:
                raise last_err if last_err else RuntimeError("main shelly read failed")

        payload["cur.shelly.main.Watt"] = watt
        payload["cur.shelly.main.Wh"] = wh
    except Exception as e:
        print(f"[main-shelly-refresh] tent #{tent.get('id')} failed: {e}")


def _parse_light_on_minutes(payload: dict) -> int | None:
    try:
        line = str((payload or {}).get("settings.shelly.light.line") or "")
        m = re.search(r"ON\s*(\d{1,2}):(\d{2})", line, flags=re.IGNORECASE)
        if not m:
            return None
        h = int(m.group(1))
        mi = int(m.group(2))
        if h < 0 or h > 23 or mi < 0 or mi > 59:
            return None
        return h * 60 + mi
    except Exception:
        return None


def _shelly_auth_candidates(user: str, pw: str):
    user = (user or "").strip()
    if not user:
        return [None]
    return [
        (user, pw),
        httpx.DigestAuth(user, pw),
        None,
    ]


def _read_exhaust_shelly_output(payload: dict, tent: dict | None = None) -> bool | None:
    ip = str((payload or {}).get("settings.shelly.exhaust.ip") or "").strip()
    if not ip:
        return None
    gen = int((payload or {}).get("settings.shelly.exhaust.gen") or 2)
    base = ip if ip.startswith("http://") or ip.startswith("https://") else f"http://{ip}"
    user = ((tent or {}).get("shelly_main_user") or "").strip() if tent else ""
    pw = ((tent or {}).get("shelly_main_password") or "").strip() if tent else ""
    auth_candidates = _shelly_auth_candidates(user, pw)
    tried = set()

    with httpx.Client(timeout=4.0) as client:
        for auth in auth_candidates:
            key = str(auth)
            if key in tried:
                continue
            tried.add(key)
            try:
                if gen >= 2:
                    r = client.get(f"{base}/rpc/Shelly.GetStatus", auth=auth)
                    r.raise_for_status()
                    j = r.json() or {}
                    sw = (j.get("switch:0") or {})
                    return bool(sw.get("output"))
                r = client.get(f"{base}/status", auth=auth)
                r.raise_for_status()
                j = r.json() or {}
                relays = j.get("relays") or [{}]
                return bool((relays[0] or {}).get("ison"))
            except Exception:
                continue
    print(f"[exhaust-direct-read] failed for {base} (tent #{(tent or {}).get('id')})")
    return None


def _get_exhaust_shelly_direct_state_from_payload(payload: dict, tent: dict | None = None) -> dict | None:
    ip = str((payload or {}).get("settings.shelly.exhaust.ip") or "").strip()
    if not ip:
        return None
    gen = int((payload or {}).get("settings.shelly.exhaust.gen") or 2)
    base = ip if ip.startswith("http://") or ip.startswith("https://") else f"http://{ip}"
    user = ((tent or {}).get("shelly_main_user") or "").strip() if tent else ""
    pw = ((tent or {}).get("shelly_main_password") or "").strip() if tent else ""
    auth_candidates = _shelly_auth_candidates(user, pw)
    tried = set()
    with httpx.Client(timeout=4.0) as client:
        for auth in auth_candidates:
            key = str(auth)
            if key in tried:
                continue
            tried.add(key)
            try:
                if gen >= 2:
                    r = client.get(f"{base}/rpc/Shelly.GetStatus", auth=auth)
                    r.raise_for_status()
                    j = r.json() or {}
                    sw = (j.get("switch:0") or {})
                    is_on = bool(sw.get("output"))
                    watt = sw.get("apower")
                    wh = (sw.get("aenergy") or {}).get("total")
                else:
                    r = client.get(f"{base}/status", auth=auth)
                    r.raise_for_status()
                    j = r.json() or {}
                    relays = j.get("relays") or [{}]
                    meters = j.get("meters") or [{}]
                    is_on = bool((relays[0] or {}).get("ison"))
                    watt = (meters[0] or {}).get("power")
                    wh = (meters[0] or {}).get("total")
                return {"isOn": is_on, "Watt": watt, "Wh": wh, "ip": base, "gen": gen}
            except Exception:
                continue
    return None


def _set_exhaust_shelly_output(payload: dict, turn_on: bool, tent: dict | None = None) -> bool:
    ip = str((payload or {}).get("settings.shelly.exhaust.ip") or "").strip()
    if not ip:
        return False
    gen = int((payload or {}).get("settings.shelly.exhaust.gen") or 2)
    base = ip if ip.startswith("http://") or ip.startswith("https://") else f"http://{ip}"
    user = ((tent or {}).get("shelly_main_user") or "").strip() if tent else ""
    pw = ((tent or {}).get("shelly_main_password") or "").strip() if tent else ""
    auth_candidates = _shelly_auth_candidates(user, pw)
    tried = set()
    with httpx.Client(timeout=4.0) as client:
        for auth in auth_candidates:
            key = str(auth)
            if key in tried:
                continue
            tried.add(key)
            try:
                if gen >= 2:
                    r = client.post(f"{base}/rpc/Switch.Set", json={"id": 0, "on": bool(turn_on)}, auth=auth)
                    r.raise_for_status()
                else:
                    r = client.get(f"{base}/relay/0", params={"turn": "on" if turn_on else "off"}, auth=auth)
                    r.raise_for_status()
                return True
            except Exception:
                continue
    print(f"[exhaust-direct-set] failed for {base} -> {'on' if turn_on else 'off'} (tent #{(tent or {}).get('id')})")
    return False


def _try_run_exhaust_vpd_control(tent: dict, payload: dict):
    plan = tent.get("exhaust_vpd_plan") or {}
    if not plan.get("enabled"):
        return

    ip = str((payload or {}).get("settings.shelly.exhaust.ip") or "").strip()
    if not ip:
        return

    try:
        min_vpd = max(0.1, float(plan.get("min_vpd_kpa", 0.6) or 0.6))
        hysteresis = max(0.0, float(plan.get("hysteresis_kpa", 0.05) or 0.05))
    except Exception:
        return

    try:
        cur_vpd = float((payload or {}).get("sensors.cur.vpdKpa"))
    except Exception:
        return

    # Read real current exhaust state from Shelly directly (never from stale /api/state).
    direct_state = _read_exhaust_shelly_output(payload, tent)
    if direct_state is None:
        return
    is_on = bool(direct_state)

    # Hysteresis control:
    # - ON threshold:  VPD < min_vpd
    # - OFF threshold: VPD >= min_vpd + hysteresis
    if is_on:
        should_be_on = cur_vpd < (min_vpd + hysteresis)
    else:
        should_be_on = cur_vpd < min_vpd

    if should_be_on != is_on:
        ok = _set_exhaust_shelly_output(payload, should_be_on, tent)
        if not ok:
            print(f"[exhaust-vpd] tent #{tent.get('id')} direct set failed (vpd={cur_vpd:.2f}, min={min_vpd:.2f}, hyst={hysteresis:.2f}, is_on={is_on}, should_on={should_be_on})")
            return

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE tents SET exhaust_vpd_triggered=%s WHERE id=%s", (should_be_on, tent["id"]))


def _find_light_on_today_dt(tent_id: int):
    today = date.today()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT captured_at, payload
                FROM tent_state
                WHERE tent_id=%s
                  AND captured_at >= date_trunc('day', NOW())
                ORDER BY captured_at ASC
                """,
                (tent_id,),
            )
            rows = cur.fetchall()

    prev = None
    for ts, p in rows:
        d = p or {}
        cur_state = bool(d.get("cur.shelly.light.isOn"))
        if prev is None:
            prev = cur_state
            continue
        if (not prev) and cur_state:
            return ts
        prev = cur_state
    return None


def _try_run_irrigation_schedule(tent: dict, payload: dict):
    plan = tent.get("irrigation_plan") or {}
    if not plan.get("enabled"):
        return

    try:
        every_n_days = max(1, int(plan.get("every_n_days", 1)))
        offset_min = max(0, int(plan.get("offset_after_light_on_min", 0)))
    except Exception:
        return

    now_local = datetime.now()
    today = now_local.date()

    # Ensure this is an 8x relay setup and not currently watering
    relay_count = int((payload or {}).get("settings.active_relay_count") or 0)
    runs_left = int((payload or {}).get("irrigation.runsLeft") or 0)
    if relay_count != 8 or runs_left > 0:
        return

    # Prefer actual light-on timestamp from today's history; fallback to configured ON schedule.
    light_on_dt = _find_light_on_today_dt(tent["id"])
    if light_on_dt is not None:
        trigger_dt = light_on_dt + timedelta(minutes=offset_min)
        now_cmp = datetime.now(trigger_dt.tzinfo) if getattr(trigger_dt, 'tzinfo', None) else now_local
        if now_cmp < trigger_dt:
            return
    else:
        on_min = _parse_light_on_minutes(payload)
        if on_min is None:
            return
        now_min = now_local.hour * 60 + now_local.minute
        if now_min < (on_min + offset_min):
            return

    last_run_date = tent.get("irrigation_last_run_date")
    if last_run_date:
        try:
            last_d = date.fromisoformat(last_run_date)
            if (today - last_d).days < every_n_days:
                return
        except Exception:
            pass

    # Trigger irrigation once; on success write last run date.
    source_url = tent.get("source_url") or ""
    base = derive_controller_base_url(source_url)
    with httpx.Client(timeout=5.0) as client:
        r = client.post(f"{base}/startWatering")
        r.raise_for_status()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE tents SET irrigation_last_run_date=%s WHERE id=%s", (today, tent["id"]))



def poll_loop():
    loops = 0
    while True:
        try:
            tents = list_tent_sources()
            if not tents:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            with httpx.Client(timeout=5.0) as client:
                for tent in tents:
                    try:
                        if tent.get("rtsp_url"):
                            register_rtsp_stream(tent["id"], tent["rtsp_url"])

                        r = client.get(tent["source_url"])
                        r.raise_for_status()
                        payload = r.json()

                        # Keep main consumption history sourced from Shelly directly.
                        _refresh_main_shelly_in_payload(payload, tent)

                        save_state(tent["id"], payload)

                        # Status transition: offline -> online
                        st = POLL_NOTIFY_STATE.get(tent["id"]) or {"online": None}
                        if st.get("online") is False:
                            _send_pushover(
                                "CanopyOps: tent online",
                                f"Tent #{tent['id']} is reachable again ({tent['source_url']}).",
                                priority=0,
                            )
                        st["online"] = True
                        st["last_ok"] = datetime.now(timezone.utc).isoformat()
                        POLL_NOTIFY_STATE[tent["id"]] = st

                        try:
                            _try_run_exhaust_vpd_control(tent, payload)
                            _try_run_irrigation_schedule(tent, payload)
                        except Exception as sched_err:
                            print(f"[scheduler] tent #{tent['id']} schedule failed: {sched_err}")

                    except Exception as tent_err:
                        print(f"[poller] tent #{tent['id']} ({tent['source_url']}) failed: {tent_err}")
                        st = POLL_NOTIFY_STATE.get(tent["id"]) or {"online": None}
                        if st.get("online") is not False:
                            _send_pushover(
                                "CanopyOps: tent offline",
                                f"Tent #{tent['id']} is unreachable ({tent['source_url']}). Error: {tent_err}",
                                priority=0,
                            )
                        st["online"] = False
                        st["last_error"] = str(tent_err)
                        st["last_err_at"] = datetime.now(timezone.utc).isoformat()
                        POLL_NOTIFY_STATE[tent["id"]] = st

            loops += 1
            # Run retention cleanup regularly (roughly every 10 minutes at 10s poll interval).
            if loops % 60 == 0:
                cleanup_old_data()
        except Exception as e:
            print(f"[poller] error: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


@app.on_event("startup")
def startup_event():
    init_db()
    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/config/auth")
def get_auth_config():
    cfg = load_auth_config()
    username = cfg.get("username") or "admin"
    secret = cfg.get("totp_secret") or ""
    otpauth_url = None
    qr_png_url = None
    if cfg.get("twofa_enabled") and username and secret:
        otpauth_url = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="CanopyOps")
        qr_png_url = f"/auth/qr.png?u={quote_plus(otpauth_url)}"
    return {
        "enabled": bool(cfg.get("enabled")),
        "username": username,
        "twofa_enabled": bool(cfg.get("twofa_enabled")),
        "totp_configured": bool(cfg.get("totp_secret")),
        "has_password": bool(cfg.get("password_hash")),
        "guest_enabled": bool(cfg.get("guest_enabled")),
        "guest_username": cfg.get("guest_username") or "",
        "guest_has_password": bool(cfg.get("guest_password_hash")),
        "guest_expires_at": cfg.get("guest_expires_at"),
        "pushover_device": cfg.get("pushover_device") or "",
        "pushover_app_token": cfg.get("pushover_app_token") or "",
        "pushover_user_key": cfg.get("pushover_user_key") or "",
        "gromate_api_password": cfg.get("gromate_api_password") or "",
        "history_api_enabled": bool(cfg.get("history_api_enabled", True)),
        "otpauth_url": otpauth_url,
        "qr_png_url": qr_png_url,
    }


import pyotp
import qrcode


class AuthConfigPayload(BaseModel):
    enabled: bool = False
    username: str | None = None
    password: str | None = None
    twofa_enabled: bool | None = None
    regenerate_recovery_codes: bool = False
    guest_enabled: bool | None = None
    guest_username: str | None = None
    guest_password: str | None = None
    guest_expires_at: str | None = None
    pushover_device: str | None = None
    pushover_app_token: str | None = None
    pushover_user_key: str | None = None
    gromate_api_password: str | None = None
    history_api_enabled: bool | None = None


class TwoFAVerifyPayload(BaseModel):
    token: str
    code: str


class TwoFAConfigPayload(BaseModel):
    enabled: bool = False
    regenerate_recovery_codes: bool = False


@app.post("/config/auth")
def set_auth_config(payload: AuthConfigPayload):
    def as_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return int(v) != 0
        s = str(v).strip().lower()
        return s in {"1", "true", "yes", "on"}

    enabled = as_bool(payload.enabled)
    username = (payload.username or "").strip()
    password = payload.password
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username, password_hash, twofa_enabled, guest_enabled, guest_username, guest_password_hash, guest_expires_at, pushover_device, pushover_app_token, pushover_user_key, gromate_api_password, history_api_enabled FROM app_auth_config WHERE id=1")
            row = cur.fetchone() or (None, None, False, False, None, None, None, "", "", "", "", True)
            current_hash = row[1]
            is_twofa_enabled = bool(row[2])
            current_guest_enabled = bool(row[3])
            current_guest_hash = row[5]
            current_pushover_device = (row[7] or "")
            current_pushover_app_token = (row[8] or "")
            current_pushover_user_key = (row[9] or "")
            current_gromate_api_password = (row[10] or "")
            current_history_api_enabled = bool(row[11]) if row[11] is not None else True
            want_twofa = is_twofa_enabled if payload.twofa_enabled is None else as_bool(payload.twofa_enabled)

            if enabled and not username:
                raise HTTPException(status_code=400, detail="username required when auth is enabled")
            if enabled and not current_hash and not password:
                raise HTTPException(status_code=400, detail="password required for first auth enable")
            if want_twofa and not enabled:
                raise HTTPException(status_code=400, detail="2FA requires enabled authentication")

            new_hash = current_hash
            if isinstance(password, str) and password != "":
                new_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

            guest_enabled = current_guest_enabled if payload.guest_enabled is None else as_bool(payload.guest_enabled)
            guest_username = (payload.guest_username or "").strip()
            guest_password = payload.guest_password
            guest_hash = current_guest_hash
            if isinstance(guest_password, str) and guest_password != "":
                guest_hash = hashlib.sha256(guest_password.encode("utf-8")).hexdigest()

            guest_expires_at = payload.guest_expires_at
            guest_exp_ts = None
            pushover_device = current_pushover_device if payload.pushover_device is None else str(payload.pushover_device or "").strip()
            pushover_app_token = current_pushover_app_token if payload.pushover_app_token is None else str(payload.pushover_app_token or "").strip()
            pushover_user_key = current_pushover_user_key if payload.pushover_user_key is None else str(payload.pushover_user_key or "").strip()
            gromate_api_password = current_gromate_api_password if payload.gromate_api_password is None else str(payload.gromate_api_password or "").strip()
            history_api_enabled = current_history_api_enabled if payload.history_api_enabled is None else as_bool(payload.history_api_enabled)
            if guest_enabled:
                if not guest_username:
                    raise HTTPException(status_code=400, detail="guest username required when guest mode is enabled")
                if not guest_hash:
                    raise HTTPException(status_code=400, detail="guest password required when guest mode is enabled")
                try:
                    if not guest_expires_at:
                        raise ValueError("missing")
                    guest_exp_ts = datetime.fromisoformat(str(guest_expires_at).replace('Z', '+00:00'))
                except Exception:
                    raise HTTPException(status_code=400, detail="guest_expires_at must be ISO datetime")
                if guest_exp_ts.timestamp() <= time.time():
                    raise HTTPException(status_code=400, detail="guest_expires_at must be in the future")

            # Persist base auth settings first.
            cur.execute(
                """
                INSERT INTO app_auth_config(id, enabled, username, password_hash, guest_enabled, guest_username, guest_password_hash, guest_expires_at, pushover_device, pushover_app_token, pushover_user_key, gromate_api_password, history_api_enabled, updated_at)
                VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (id)
                DO UPDATE SET enabled=EXCLUDED.enabled, username=EXCLUDED.username, password_hash=EXCLUDED.password_hash,
                              guest_enabled=EXCLUDED.guest_enabled, guest_username=EXCLUDED.guest_username,
                              guest_password_hash=EXCLUDED.guest_password_hash, guest_expires_at=EXCLUDED.guest_expires_at,
                              pushover_device=EXCLUDED.pushover_device,
                              pushover_app_token=EXCLUDED.pushover_app_token,
                              pushover_user_key=EXCLUDED.pushover_user_key,
                              gromate_api_password=EXCLUDED.gromate_api_password,
                              history_api_enabled=EXCLUDED.history_api_enabled,
                              updated_at=NOW()
                """,
                (enabled, username or None, new_hash, guest_enabled, guest_username or None, guest_hash, guest_exp_ts, pushover_device or None, pushover_app_token or None, pushover_user_key or None, gromate_api_password or None, history_api_enabled),
            )

            # Explicit 2FA disable request
            if not want_twofa and is_twofa_enabled:
                cur.execute("UPDATE app_auth_config SET twofa_enabled=FALSE, totp_secret=NULL, recovery_codes_json='[]', updated_at=NOW() WHERE id=1")

    # Start 2FA enrollment flow (QR + verify code), do NOT enable immediately.
    if enabled and want_twofa and not load_auth_config().get("twofa_enabled"):
        secret = pyotp.random_base32()
        otpauth_url = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="CanopyOps")
        recovery_codes = [
            "-".join([secrets.token_hex(2), secrets.token_hex(2), secrets.token_hex(2)]).upper()
            for _ in range(10)
        ]
        recovery_payload = [
            {"hash": hashlib.sha256(c.encode("utf-8")).hexdigest(), "used": False}
            for c in recovery_codes
        ]
        token = secrets.token_urlsafe(24)
        TWOFA_ENROLL[token] = {
            "secret": secret,
            "recovery_json": json.dumps(recovery_payload),
            "expires_at": time.time() + 600,
            "username": username,
        }
        return {
            "ok": True,
            "enabled": True,
            "username": username,
            "twofa_enabled": False,
            "has_password": True,
            "pending_2fa": True,
            "verify_token": token,
            "otpauth_url": otpauth_url,
            "qr_png_url": f"/auth/qr.png?u={quote_plus(otpauth_url)}",
            "recovery_codes": recovery_codes,
            "pushover_device": cfg.get("pushover_device") or "",
        }

    cfg = load_auth_config()
    return {
        "ok": True,
        "enabled": bool(cfg.get("enabled")),
        "username": cfg.get("username") or "",
        "twofa_enabled": bool(cfg.get("twofa_enabled")),
        "has_password": bool(cfg.get("password_hash")),
        "guest_enabled": bool(cfg.get("guest_enabled")),
        "guest_username": cfg.get("guest_username") or "",
        "guest_has_password": bool(cfg.get("guest_password_hash")),
        "guest_expires_at": cfg.get("guest_expires_at"),
        "pushover_device": cfg.get("pushover_device") or "",
        "pushover_app_token": cfg.get("pushover_app_token") or "",
        "pushover_user_key": cfg.get("pushover_user_key") or "",
        "gromate_api_password": cfg.get("gromate_api_password") or "",
        "history_api_enabled": bool(cfg.get("history_api_enabled", True)),
        "otpauth_url": None,
        "qr_png_url": None,
        "recovery_codes": [],
    }


@app.post("/config/auth/2fa")
def set_2fa_config(payload: TwoFAConfigPayload):
    def as_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return int(v) != 0
        return str(v).strip().lower() in {"1", "true", "yes", "on"}

    want_twofa = as_bool(payload.enabled)
    regen_codes = as_bool(payload.regenerate_recovery_codes)
    cfg = load_auth_config()

    if not cfg.get("enabled"):
        raise HTTPException(status_code=400, detail="Enable authentication first")
    if not cfg.get("username") or not cfg.get("password_hash"):
        raise HTTPException(status_code=400, detail="Set username/password first")

    if not want_twofa:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE app_auth_config SET twofa_enabled=FALSE, totp_secret=NULL, recovery_codes_json='[]', updated_at=NOW() WHERE id=1")
        cfg2 = load_auth_config()
        return {"ok": True, "twofa_enabled": bool(cfg2.get("twofa_enabled")), "recovery_codes": []}

    # Already enabled + regenerate recovery codes only
    if cfg.get("twofa_enabled") and cfg.get("totp_secret") and regen_codes:
        recovery_codes = [
            "-".join([secrets.token_hex(2), secrets.token_hex(2), secrets.token_hex(2)]).upper()
            for _ in range(10)
        ]
        recovery_payload = [
            {"hash": hashlib.sha256(c.encode("utf-8")).hexdigest(), "used": False}
            for c in recovery_codes
        ]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE app_auth_config SET recovery_codes_json=%s, updated_at=NOW() WHERE id=1",
                    (json.dumps(recovery_payload),),
                )
        return {"ok": True, "twofa_enabled": True, "recovery_codes": recovery_codes}

    # Start enrollment flow (enable request or re-enroll)
    secret = pyotp.random_base32()
    username = str(cfg.get("username") or "admin")
    otpauth_url = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="CanopyOps")
    recovery_codes = [
        "-".join([secrets.token_hex(2), secrets.token_hex(2), secrets.token_hex(2)]).upper()
        for _ in range(10)
    ]
    recovery_payload = [
        {"hash": hashlib.sha256(c.encode("utf-8")).hexdigest(), "used": False}
        for c in recovery_codes
    ]
    token = secrets.token_urlsafe(24)
    TWOFA_ENROLL[token] = {
        "secret": secret,
        "recovery_json": json.dumps(recovery_payload),
        "expires_at": time.time() + 600,
        "username": username,
    }
    return {
        "ok": True,
        "pending_2fa": True,
        "verify_token": token,
        "twofa_enabled": False,
        "otpauth_url": otpauth_url,
        "qr_png_url": f"/auth/qr.png?u={quote_plus(otpauth_url)}",
        "recovery_codes": recovery_codes,
    }


@app.get("/tents")
def list_tents():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, source_url, rtsp_url, shelly_main_user, shelly_main_password, irrigation_plan_json, irrigation_last_run_date, exhaust_vpd_plan_json, exhaust_vpd_triggered, created_at FROM tents ORDER BY id")
            rows = cur.fetchall()
            return [
                {
                    "id": r[0],
                    "name": r[1],
                    "source_url": r[2],
                    "rtsp_url": r[3],
                    "shelly_main_user": r[4] or "",
                    "shelly_main_password": r[5] or "",
                    "irrigation_plan": json.loads(r[6] or '{}') if r[6] else {},
                    "irrigation_last_run_date": r[7].isoformat() if r[7] else None,
                    "exhaust_vpd_plan": json.loads(r[8] or '{}') if r[8] else {},
                    "exhaust_vpd_triggered": bool(r[9]),
                    "created_at": r[10].isoformat(),
                }
                for r in rows
            ]


@app.post("/config/auth/2fa/verify")
def verify_2fa_setup(payload: TwoFAVerifyPayload):
    pending = TWOFA_ENROLL.get(payload.token)
    if not pending or pending.get("expires_at", 0) < time.time():
        TWOFA_ENROLL.pop(payload.token, None)
        raise HTTPException(status_code=400, detail="2FA setup expired, please start again")

    secret = pending.get("secret") or ""
    code = (payload.code or "").strip()
    if not code or not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail="invalid 2FA code")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE app_auth_config SET twofa_enabled=TRUE, totp_secret=%s, recovery_codes_json=%s, updated_at=NOW() WHERE id=1",
                (secret, pending.get("recovery_json") or "[]"),
            )

    TWOFA_ENROLL.pop(payload.token, None)
    cfg = load_auth_config()
    return {"ok": True, "twofa_enabled": bool(cfg.get("twofa_enabled"))}


@app.get("/config/backup/export")
def export_config_backup():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, source_url, rtsp_url, shelly_main_user, shelly_main_password,
                       irrigation_plan_json, irrigation_last_run_date,
                       exhaust_vpd_plan_json, exhaust_vpd_triggered, created_at
                FROM tents
                ORDER BY id
                """
            )
            tent_rows = cur.fetchall()

            cur.execute(
                """
                SELECT enabled, username, password_hash, twofa_enabled, totp_secret, recovery_codes_json, pushover_device, pushover_app_token, pushover_user_key, gromate_api_password, history_api_enabled, updated_at
                FROM app_auth_config
                WHERE id=1
                """
            )
            auth_row = cur.fetchone()

    tents = []
    for r in tent_rows:
        tents.append(
            {
                "id": r[0],
                "name": r[1],
                "source_url": r[2],
                "rtsp_url": r[3],
                "shelly_main_user": r[4],
                "shelly_main_password": r[5],
                "irrigation_plan_json": r[6],
                "irrigation_last_run_date": r[7].isoformat() if r[7] else None,
                "exhaust_vpd_plan_json": r[8],
                "exhaust_vpd_triggered": bool(r[9]),
                "created_at": r[10].isoformat() if r[10] else None,
            }
        )

    auth = None
    if auth_row:
        auth = {
            "enabled": bool(auth_row[0]),
            "username": auth_row[1],
            "password_hash": auth_row[2],
            "twofa_enabled": bool(auth_row[3]),
            "totp_secret": auth_row[4],
            "recovery_codes_json": auth_row[5],
            "pushover_device": auth_row[6] or "",
            "pushover_app_token": auth_row[7] or "",
            "pushover_user_key": auth_row[8] or "",
            "gromate_api_password": auth_row[9] or "",
            "history_api_enabled": bool(auth_row[10]) if auth_row[10] is not None else True,
            "updated_at": auth_row[11].isoformat() if auth_row[11] else None,
        }

    backup = {
        "kind": "canopyops-config-backup",
        "schema_version": 1,
        "app_version": APP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "tents": tents,
            "auth": auth,
        },
    }

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    content = json.dumps(backup, ensure_ascii=False, indent=2)
    headers = {"Content-Disposition": f"attachment; filename=canopyops-backup-{ts}.json"}
    return Response(content=content, media_type="application/json", headers=headers)


@app.post("/config/backup/import")
def import_config_backup(payload: dict):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    if payload.get("kind") != "canopyops-config-backup":
        raise HTTPException(status_code=400, detail="invalid backup kind")

    data = payload.get("data") or {}
    tents = data.get("tents")
    auth = data.get("auth")
    if not isinstance(tents, list):
        raise HTTPException(status_code=400, detail="invalid tents section")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tents")

            for t in tents:
                if not isinstance(t, dict):
                    continue
                cur.execute(
                    """
                    INSERT INTO tents(
                        id, name, source_url, rtsp_url, shelly_main_user, shelly_main_password,
                        irrigation_plan_json, irrigation_last_run_date,
                        exhaust_vpd_plan_json, exhaust_vpd_triggered,
                        created_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,COALESCE(%s::timestamptz, NOW()))
                    """,
                    (
                        int(t.get("id") or 0),
                        str(t.get("name") or "").strip(),
                        str(t.get("source_url") or "").strip(),
                        (str(t.get("rtsp_url")).strip() if t.get("rtsp_url") else None),
                        (str(t.get("shelly_main_user")).strip() if t.get("shelly_main_user") else None),
                        (str(t.get("shelly_main_password")).strip() if t.get("shelly_main_password") else None),
                        str(t.get("irrigation_plan_json") or '{"enabled":false,"every_n_days":1,"offset_after_light_on_min":0}'),
                        t.get("irrigation_last_run_date"),
                        str(t.get("exhaust_vpd_plan_json") or '{"enabled":false,"min_vpd_kpa":0.6,"hysteresis_kpa":0.05}'),
                        bool(t.get("exhaust_vpd_triggered", False)),
                        t.get("created_at"),
                    ),
                )

            if auth and isinstance(auth, dict):
                cur.execute(
                    """
                    UPDATE app_auth_config
                    SET enabled=%s,
                        username=%s,
                        password_hash=%s,
                        twofa_enabled=%s,
                        totp_secret=%s,
                        recovery_codes_json=%s,
                        pushover_device=%s,
                        pushover_app_token=%s,
                        pushover_user_key=%s,
                        gromate_api_password=%s,
                        history_api_enabled=%s,
                        updated_at=NOW()
                    WHERE id=1
                    """,
                    (
                        bool(auth.get("enabled", False)),
                        (str(auth.get("username")).strip() if auth.get("username") else None),
                        (str(auth.get("password_hash")) if auth.get("password_hash") else None),
                        bool(auth.get("twofa_enabled", False)),
                        (str(auth.get("totp_secret")) if auth.get("totp_secret") else None),
                        str(auth.get("recovery_codes_json") or "[]"),
                        (str(auth.get("pushover_device")).strip() if auth.get("pushover_device") else None),
                        (str(auth.get("pushover_app_token")).strip() if auth.get("pushover_app_token") else None),
                        (str(auth.get("pushover_user_key")).strip() if auth.get("pushover_user_key") else None),
                        (str(auth.get("gromate_api_password")).strip() if auth.get("gromate_api_password") else None),
                        bool(auth.get("history_api_enabled", True)),
                    ),
                )

            cur.execute("SELECT COALESCE(MAX(id), 1) FROM tents")
            max_id = int(cur.fetchone()[0] or 1)
            cur.execute("SELECT setval(pg_get_serial_sequence('tents','id'), %s, true)", (max_id,))

    return {"ok": True, "imported_tents": len(tents)}


@app.post("/tents")
def create_tent(payload: dict):
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
            return {"id": row[0], "name": row[1], "source_url": row[2], "rtsp_url": row[3], "shelly_main_user": row[4] or "", "shelly_main_password": row[5] or "", "created_at": row[6].isoformat()}


@app.put("/tents/{tent_id}")
def update_tent(tent_id: int, payload: dict):
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
            return {"id": row[0], "name": row[1], "source_url": row[2], "rtsp_url": row[3], "shelly_main_user": row[4] or "", "shelly_main_password": row[5] or "", "created_at": row[6].isoformat()}


@app.get("/tents/{tent_id}/irrigation-plan")
def get_irrigation_plan(tent_id: int):
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


@app.put("/tents/{tent_id}/irrigation-plan")
def update_irrigation_plan(tent_id: int, payload: dict):
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
            cur.execute(
                """
                UPDATE tents
                SET irrigation_plan_json=%s
                WHERE id=%s
                RETURNING id
                """,
                (plan_json, tent_id),
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
    }


@app.get("/tents/{tent_id}/exhaust-vpd-plan")
def get_exhaust_vpd_plan(tent_id: int):
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


@app.put("/tents/{tent_id}/exhaust-vpd-plan")
def update_exhaust_vpd_plan(tent_id: int, payload: dict):
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


@app.get("/tents/{tent_id}/latest")
def latest_state(tent_id: int, request: Request):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.rtsp_url, s.captured_at, s.payload
                FROM tents t
                LEFT JOIN LATERAL (
                  SELECT captured_at, payload
                  FROM tent_state
                  WHERE tent_id=t.id
                  ORDER BY captured_at DESC
                  LIMIT 1
                ) s ON true
                WHERE t.id=%s
                """,
                (tent_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="tent not found")

            rtsp_url = row[0]
            captured = row[1]
            payload = row[2]

            host = request.headers.get("host", "localhost:8088")
            go2rtc_host = f"http://{host.split(':')[0]}:1984"
            # Force muted playback in UI/open-player links.
            rtsp_video_only = None
            if rtsp_url:
                rtsp_video_only = f"{rtsp_url}#media=video"

            player_url = (
                f"{go2rtc_host}/stream.html?src={quote_plus(rtsp_video_only)}&muted=1&volume=0&audio=0&media=video&defaultMute=1"
                if rtsp_video_only
                else None
            )
            preview_url = f"/tents/{tent_id}/preview"

            return {
                "tent_id": tent_id,
                "rtsp_url": rtsp_url,
                "webrtc_url": f"{go2rtc_host}/api/webrtc?src=tent_{tent_id}",
                "player_url": player_url,
                "preview_url": preview_url,
                "captured_at": captured.isoformat() if captured else None,
                "latest": payload,
            }


@app.get("/tents/{tent_id}/preview")
def tent_preview(
    tent_id: int,
    w: int = Query(1280, ge=320, le=3840),
    h: int = Query(720, ge=180, le=2160),
    q: int = Query(85, ge=30, le=100),
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT rtsp_url FROM tents WHERE id=%s", (tent_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="tent not found")
            rtsp_url = row[0]

    # Prefer explicit RTSP source, fallback to named go2rtc stream.
    src = f"{rtsp_url}#media=video" if rtsp_url else f"tent_{tent_id}"
    url = (
        f"{GO2RTC_BASE_URL}/api/frame.jpeg"
        f"?src={quote_plus(src)}&width={int(w)}&height={int(h)}&q={int(q)}"
    )
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
            if r.status_code != 200:
                raise HTTPException(status_code=502, detail="preview unavailable")
            content_type = r.headers.get("content-type", "image/jpeg")
            return Response(content=r.content, media_type=content_type)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="preview unavailable")


@app.get("/tents/{tent_id}/shelly/last-switches")
def shelly_last_switches(tent_id: int, max_rows: int = 5000):
    keys = ["main", "light", "humidifier", "heater", "fan", "exhaust"]

    def to_bool(v):
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return int(v) == 1
        s = str(v).strip().lower()
        return s in {"1", "true", "on", "yes"}

    max_rows = max(100, min(max_rows, 20000))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT captured_at, payload
                FROM tent_state
                WHERE tent_id=%s
                ORDER BY captured_at DESC
                LIMIT %s
                """,
                (tent_id, max_rows),
            )
            rows = cur.fetchall()

    if not rows:
        return {"tent_id": tent_id, "last_switches": {k: None for k in keys}}

    # Process oldest -> newest to find last state transitions.
    prev = {k: None for k in keys}
    last_switch = {k: None for k in keys}

    for captured_at, payload in reversed(rows):
        p = payload or {}
        for k in keys:
            cur_state = to_bool(p.get(f"cur.shelly.{k}.isOn"))
            if prev[k] is None:
                prev[k] = cur_state
                continue
            if cur_state != prev[k]:
                last_switch[k] = captured_at
                prev[k] = cur_state

    return {
        "tent_id": tent_id,
        "last_switches": {k: (last_switch[k].isoformat() if last_switch[k] else None) for k in keys},
    }


def _despike_series(values: list, rel_jump: float, abs_jump: float):
    out = []
    prev = None
    for v in values:
        n = None
        try:
            n = float(v)
        except Exception:
            n = None

        if n is None:
            out.append(v)
            continue

        if prev is None:
            out.append(n)
            prev = n
            continue

        jump = abs(n - prev)
        rel = (jump / max(0.0001, abs(prev)))
        if jump > abs_jump and rel > rel_jump:
            out.append(prev)
            continue

        out.append(n)
        prev = n
    return out


@app.get("/tents/{tent_id}/history")
def history_state(tent_id: int, minutes: int = 360, filter_spikes: int = 1):
    # Limit query window to keep payload slim and responsive (max retention window).
    max_minutes = RETENTION_DAYS * 24 * 60
    minutes = max(5, min(minutes, max_minutes))

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT captured_at, payload
                FROM tent_state
                WHERE tent_id=%s
                  AND captured_at >= NOW() - (%s || ' minutes')::interval
                ORDER BY captured_at ASC
                """,
                (tent_id, minutes),
            )
            rows = cur.fetchall()

    points = []
    for ts, payload in rows:
        d = payload or {}
        leaf_offset = _to_float(d.get("settings.grow.offsetLeafTemperature")) or 0.0
        temp_raw = _to_float(d.get("sensors.cur.temperatureRawC"))
        hum_raw = _to_float(d.get("sensors.cur.humidityRawPct"))
        vpd_raw = _to_float(d.get("sensors.cur.vpdRawKpa"))
        if temp_raw is None:
            temp_raw = _to_float(d.get("sensors.raw.temperatureC"))
        if hum_raw is None:
            hum_raw = _to_float(d.get("sensors.raw.humidityPct"))
        if vpd_raw is None:
            vpd_raw = _to_float(d.get("sensors.raw.vpdKpa"))
        if vpd_raw is None:
            vpd_raw = _calc_vpd_kpa(temp_raw, leaf_offset, hum_raw)

        # Ignore invalid startup/noise samples in history pipeline.
        if not _sensor_values_valid(temp_raw, hum_raw, vpd_raw):
            continue

        points.append(
            {
                "t": ts.isoformat(),
                "temperature_raw": temp_raw,
                "humidity_raw": hum_raw,
                "vpd_raw": vpd_raw,
                "temperature_smoothed": _to_float(d.get("sensors.smoothed.temperatureC")),
                "humidity_smoothed": _to_float(d.get("sensors.smoothed.humidityPct")),
                "vpd_smoothed": _to_float(d.get("sensors.smoothed.vpdKpa")),
                "leafOffsetC": leaf_offset,
                "effectiveAlfaTempC": _to_float(d.get("sensors.cur.effectiveAlfaTempC")),
                "effectiveAlfaHumPct": _to_float(d.get("sensors.cur.effectiveAlfaHumPct")),
                "extTemp": d.get("sensors.cur.extTempC"),
                "mainW": d.get("cur.shelly.main.Watt"),
                "mainWh": d.get("cur.shelly.main.Wh"),
                "mainCost": d.get("cur.shelly.main.Cost"),
            }
        )

    # Ensure smoothed values exist from controller channels.
    # Fallback chain: smoothed -> current -> raw (no backend EMA re-smoothing).
    temp_sm = []
    hum_sm = []
    for p in points:
        tsm = _to_float(p.get("temperature_smoothed"))
        hsm = _to_float(p.get("humidity_smoothed"))
        if tsm is None:
            tsm = _to_float(p.get("temperature_raw"))
        if hsm is None:
            hsm = _to_float(p.get("humidity_raw"))
        temp_sm.append(tsm)
        hum_sm.append(hsm)

    vpd_sm = []
    for i, p in enumerate(points):
        v = _to_float(p.get("vpd_smoothed"))
        if v is None:
            v = _calc_vpd_kpa(temp_sm[i], _to_float(p.get("leafOffsetC")) or 0.0, hum_sm[i])
        vpd_sm.append(v)

    if filter_spikes:
        temp_sm = _despike_series(temp_sm, rel_jump=0.35, abs_jump=8.0)
        hum_sm = _despike_series(hum_sm, rel_jump=0.50, abs_jump=25.0)
        vpd_sm = _despike_series(vpd_sm, rel_jump=0.80, abs_jump=1.2)
        ext_f = _despike_series([p.get("extTemp") for p in points], rel_jump=0.35, abs_jump=8.0)
    else:
        ext_f = [p.get("extTemp") for p in points]

    for i, p in enumerate(points):
        p["temperature_smoothed"] = temp_sm[i]
        p["humidity_smoothed"] = hum_sm[i]
        p["vpd_smoothed"] = vpd_sm[i]

        # Backward-compatible fields (existing frontend expects temp/hum/vpd)
        p["temperature"] = temp_sm[i]
        p["humidity"] = hum_sm[i]
        p["vpd"] = vpd_sm[i]
        p["temp"] = temp_sm[i]
        p["hum"] = hum_sm[i]
        p["extTemp"] = ext_f[i]

    return {"tent_id": tent_id, "minutes": minutes, "points": points, "filter_spikes": bool(filter_spikes)}


def _resolve_tent_id_by_device_id(device_id: str) -> int | None:
    did = (device_id or "").strip()
    if not did:
        return None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, source_url
                FROM tents
                ORDER BY id
                """
            )
            rows = cur.fetchall()
    for tid, name, source_url in rows:
        if did == str(tid):
            return int(tid)
        if (name or "").strip() == did:
            return int(tid)
        if did and did in (source_url or ""):
            return int(tid)
    return None


def _iso_utc_z(ts: str | None):
    if not ts:
        return None
    try:
        s = str(ts).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def api_history_for_device(device_id: str | None):
    if not device_id or not str(device_id).strip():
        LOGGER.warning("/api/history rejected: missing deviceId")
        raise HTTPException(status_code=400, detail="deviceId is required")

    cfg = load_auth_config()
    if not bool(cfg.get("history_api_enabled", True)):
        raise HTTPException(status_code=403, detail="API history access disabled")

    tid = _resolve_tent_id_by_device_id(str(device_id))
    if tid is None:
        LOGGER.info("/api/history no matching deviceId=%s", device_id)
        return {"deviceId": str(device_id), "limit": 50, "points": []}

    try:
        hist = history_state(tid, minutes=24 * 365 * 60, filter_spikes=0)
        points = []
        for p in (hist.get("points") or [])[-50:]:
            points.append({
                "timestamp": _iso_utc_z(p.get("t")),
                "temperature": p.get("temperature"),
                "humidity": p.get("humidity"),
                "vpd": p.get("vpd"),
                "temperature_raw": p.get("temperature_raw"),
                "humidity_raw": p.get("humidity_raw"),
                "vpd_raw": p.get("vpd_raw"),
                "temperature_smoothed": p.get("temperature_smoothed"),
                "humidity_smoothed": p.get("humidity_smoothed"),
                "vpd_smoothed": p.get("vpd_smoothed"),
                "effectiveAlphaTemp": p.get("effectiveAlfaTempC"),
                "effectiveAlphaHumidity": p.get("effectiveAlfaHumPct"),
            })
        LOGGER.info("/api/history ok: deviceId=%s tent_id=%s limit=%s count=%s", device_id, tid, 50, len(points))
        return {"deviceId": str(device_id), "limit": 50, "points": points}
    except HTTPException:
        raise
    except Exception:
        LOGGER.exception("/api/history failed for deviceId=%s", device_id)
        raise HTTPException(status_code=500, detail="Failed to read history")


def export_history_csv(tent_id: int, range_key: str = "24h"):
    range_key = (range_key or "24h").strip().lower()
    minutes = None
    if range_key in ("24h", "1d", "day"):
        minutes = 24 * 60
    elif range_key in ("7d", "7days", "week"):
        minutes = 7 * 24 * 60
    elif range_key in ("all", "full"):
        minutes = None
    else:
        try:
            m = int(range_key)
            minutes = max(5, m)
        except Exception:
            minutes = 24 * 60

    with get_conn() as conn:
        with conn.cursor() as cur:
            if minutes is None:
                cur.execute(
                    """
                    SELECT captured_at, payload
                    FROM tent_state
                    WHERE tent_id=%s
                    ORDER BY captured_at ASC
                    """,
                    (tent_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT captured_at, payload
                    FROM tent_state
                    WHERE tent_id=%s
                      AND captured_at >= NOW() - (%s || ' minutes')::interval
                    ORDER BY captured_at ASC
                    """,
                    (tent_id, minutes),
                )
            rows = cur.fetchall()

    timestamps = []
    leaf_offsets = []
    temp_raw = []
    hum_raw = []
    vpd_raw = []
    alpha_temp = []
    alpha_hum = []
    payloads_kept = []

    for ts, payload in rows:
        d = payload or {}
        leaf = _to_float(d.get("settings.grow.offsetLeafTemperature")) or 0.0

        tr = _to_float(d.get("sensors.cur.temperatureRawC"))
        hr = _to_float(d.get("sensors.cur.humidityRawPct"))
        vr = _to_float(d.get("sensors.cur.vpdRawKpa"))
        if tr is None:
            tr = _to_float(d.get("sensors.raw.temperatureC"))
        if hr is None:
            hr = _to_float(d.get("sensors.raw.humidityPct"))
        if vr is None:
            vr = _to_float(d.get("sensors.raw.vpdKpa"))
        if vr is None:
            vr = _calc_vpd_kpa(tr, leaf, hr)

        # Ignore invalid startup/noise samples in export pipeline.
        if not _sensor_values_valid(tr, hr, vr):
            continue

        timestamps.append(ts.isoformat())
        leaf_offsets.append(leaf)
        temp_raw.append(tr)
        hum_raw.append(hr)
        vpd_raw.append(vr)
        alpha_temp.append(_to_float(d.get("sensors.cur.effectiveAlfaTempC")))
        alpha_hum.append(_to_float(d.get("sensors.cur.effectiveAlfaHumPct")))
        payloads_kept.append(d)

    # Smoothed channels from source payload (no backend EMA re-smoothing).
    temp_sm = []
    hum_sm = []
    for i in range(len(timestamps)):
        d = payloads_kept[i] or {}
        tsm = _to_float(d.get("sensors.smoothed.temperatureC"))
        hsm = _to_float(d.get("sensors.smoothed.humidityPct"))
        if tsm is None:
            tsm = _to_float(d.get("sensors.cur.temperatureC"))
        if hsm is None:
            hsm = _to_float(d.get("sensors.cur.humidityPct"))
        if tsm is None:
            tsm = temp_raw[i]
        if hsm is None:
            hsm = hum_raw[i]
        temp_sm.append(tsm)
        hum_sm.append(hsm)

    vpd_sm = []
    for i in range(len(timestamps)):
        d = payloads_kept[i] or {}
        vv = _to_float(d.get("sensors.smoothed.vpdKpa"))
        if vv is None:
            vv = _calc_vpd_kpa(temp_sm[i], leaf_offsets[i], hum_sm[i])
        vpd_sm.append(vv)

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([
        "timestamp",
        "temperature",
        "humidity",
        "vpd",
        "temperature_raw",
        "humidity_raw",
        "vpd_raw",
        "temperature_smoothed",
        "humidity_smoothed",
        "vpd_smoothed",
        "effectiveAlfaTempC",
        "effectiveAlfaHumPct",
    ])
    for i in range(len(timestamps)):
        w.writerow([
            timestamps[i],
            temp_sm[i],
            hum_sm[i],
            vpd_sm[i],
            temp_raw[i],
            hum_raw[i],
            vpd_raw[i],
            temp_sm[i],
            hum_sm[i],
            vpd_sm[i],
            alpha_temp[i],
            alpha_hum[i],
        ])

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"tent_{tent_id}_history_{range_key}_{stamp}.csv"
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def get_tent_by_id(tent_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, source_url, rtsp_url, shelly_main_user, shelly_main_password FROM tents WHERE id=%s", (tent_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {"id": row[0], "name": row[1], "source_url": row[2], "rtsp_url": row[3], "shelly_main_user": row[4] or "", "shelly_main_password": row[5] or ""}


def derive_controller_base_url(source_url: str) -> str:
    u = urlsplit(source_url)
    return f"{u.scheme}://{u.netloc}"


def get_latest_payload_for_tent(tent_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT payload
                FROM tent_state
                WHERE tent_id=%s
                ORDER BY captured_at DESC
                LIMIT 1
                """,
                (tent_id,),
            )
            row = cur.fetchone()
            return row[0] if row else {}


def _get_shelly_direct_state_for_key(payload: dict, tent: dict | None, key: str) -> dict | None:
    ip = str((payload or {}).get(f"settings.shelly.{key}.ip") or "").strip()
    if not ip:
        return None
    gen = int((payload or {}).get(f"settings.shelly.{key}.gen") or 2)
    base = ip if ip.startswith("http://") or ip.startswith("https://") else f"http://{ip}"
    user = ((tent or {}).get("shelly_main_user") or "").strip() if tent else ""
    pw = ((tent or {}).get("shelly_main_password") or "").strip() if tent else ""
    auth_candidates = _shelly_auth_candidates(user, pw)
    with httpx.Client(timeout=4.0) as client:
        for a in auth_candidates:
            try:
                if gen >= 2:
                    r = client.get(f"{base}/rpc/Shelly.GetStatus", auth=a)
                    r.raise_for_status()
                    j = r.json() or {}
                    sw = (j.get("switch:0") or {})
                    return {
                        "isOn": bool(sw.get("output")),
                        "Watt": sw.get("apower"),
                        "Wh": (sw.get("aenergy") or {}).get("total"),
                        "ip": base,
                        "gen": gen,
                    }
                r = client.get(f"{base}/status", auth=a)
                r.raise_for_status()
                j = r.json() or {}
                relays = j.get("relays") or [{}]
                meters = j.get("meters") or [{}]
                return {
                    "isOn": bool((relays[0] or {}).get("ison")),
                    "Watt": (meters[0] or {}).get("power"),
                    "Wh": (meters[0] or {}).get("total"),
                    "ip": base,
                    "gen": gen,
                }
            except Exception:
                continue
    return None


def _extract_main_shelly_conn(tent_id: int):
    tent = get_tent_by_id(tent_id)
    if not tent:
        raise HTTPException(status_code=404, detail="tent not found")

    latest = get_latest_payload_for_tent(tent_id) or {}
    ip = str(latest.get("settings.shelly.main.ip") or "").strip()
    gen = int(latest.get("settings.shelly.main.gen") or 2)

    # Fallback: if latest cache does not contain Shelly main config,
    # fetch current controller state once and persist it.
    if not ip:
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(tent["source_url"])
                r.raise_for_status()
                fresh = r.json() or {}
                save_state(tent_id, fresh)
                latest = fresh
                ip = str(fresh.get("settings.shelly.main.ip") or "").strip()
                gen = int(fresh.get("settings.shelly.main.gen") or gen or 2)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"failed to fetch current controller state: {e}")

    if not ip:
        raise HTTPException(status_code=400, detail="main shelly ip missing in controller state")

    base = ip if ip.startswith("http://") or ip.startswith("https://") else f"http://{ip}"
    user = (tent.get("shelly_main_user") or "").strip()
    pw = (tent.get("shelly_main_password") or "").strip()
    auth = (user, pw) if user else None
    return base, gen, auth, latest


def get_main_shelly_direct_state(tent_id: int):
    base, gen, auth, latest = _extract_main_shelly_conn(tent_id)
    user = auth[0] if auth else ""
    pw = auth[1] if auth else ""
    auth_candidates = _shelly_auth_candidates(user, pw)
    with httpx.Client(timeout=5.0) as client:
        last_err = None
        for a in auth_candidates:
            try:
                if gen >= 2:
                    r = client.get(f"{base}/rpc/Shelly.GetStatus", auth=a)
                    r.raise_for_status()
                    j = r.json() or {}
                    sw = (j.get("switch:0") or {})
                    is_on = bool(sw.get("output"))
                    watt = sw.get("apower")
                    wh = (sw.get("aenergy") or {}).get("total")
                else:
                    r = client.get(f"{base}/status", auth=a)
                    r.raise_for_status()
                    j = r.json() or {}
                    relays = j.get("relays") or [{}]
                    meters = j.get("meters") or [{}]
                    is_on = bool((relays[0] or {}).get("ison"))
                    watt = (meters[0] or {}).get("power")
                    wh = (meters[0] or {}).get("total")
                break
            except Exception as e:
                last_err = e
                continue
        else:
            raise last_err if last_err else RuntimeError("main shelly direct read failed")

    try:
        wh_num = float(wh)
    except Exception:
        wh_num = None
    kwh = (wh_num / 1000.0) if wh_num is not None else None

    return {
        "tent_id": tent_id,
        "isOn": is_on,
        "Watt": watt,
        "Wh": wh_num,
        "kWh": kwh,
        "ip": base,
        "gen": gen,
        "cost": latest.get("cur.shelly.main.Cost"),
    }


def _toggle_shelly_direct_for_key(tent_id: int, key: str):
    tent = get_tent_by_id(tent_id)
    if not tent:
        raise HTTPException(status_code=404, detail="tent not found")

    latest = get_latest_payload_for_tent(tent_id) or {}
    ip = str((latest or {}).get(f"settings.shelly.{key}.ip") or "").strip()
    if not ip:
        raise HTTPException(status_code=400, detail=f"shelly {key} ip missing in controller state")

    gen = int((latest or {}).get(f"settings.shelly.{key}.gen") or 2)
    base = ip if ip.startswith("http://") or ip.startswith("https://") else f"http://{ip}"
    user = (tent.get("shelly_main_user") or "").strip()
    pw = (tent.get("shelly_main_password") or "").strip()
    auth_candidates = _shelly_auth_candidates(user, pw)

    with httpx.Client(timeout=5.0) as client:
        last_err = None
        for a in auth_candidates:
            try:
                if gen >= 2:
                    r = client.post(f"{base}/rpc/Switch.Toggle", json={"id": 0}, auth=a)
                    r.raise_for_status()
                else:
                    r = client.get(f"{base}/relay/0", params={"turn": "toggle"}, auth=a)
                    r.raise_for_status()
                break
            except Exception as e:
                last_err = e
                continue
        else:
            raise last_err if last_err else RuntimeError(f"{key} shelly toggle failed")

    state = _get_shelly_direct_state_for_key(get_latest_payload_for_tent(tent_id) or {}, tent, key)
    return {"tent_id": tent_id, "device": key, "direct": True, "state": state}


def toggle_main_shelly_direct(tent_id: int):
    base, gen, auth, _latest = _extract_main_shelly_conn(tent_id)
    user = auth[0] if auth else ""
    pw = auth[1] if auth else ""
    auth_candidates = _shelly_auth_candidates(user, pw)
    with httpx.Client(timeout=5.0) as client:
        last_err = None
        for a in auth_candidates:
            try:
                if gen >= 2:
                    r = client.post(f"{base}/rpc/Switch.Toggle", json={"id": 0}, auth=a)
                    r.raise_for_status()
                else:
                    r = client.get(f"{base}/relay/0", params={"turn": "toggle"}, auth=a)
                    r.raise_for_status()
                break
            except Exception as e:
                last_err = e
                continue
        else:
            raise last_err if last_err else RuntimeError("main shelly toggle failed")
    return get_main_shelly_direct_state(tent_id)


def proxy_post_to_tent_action(tent_id: int, path: str):
    tent = get_tent_by_id(tent_id)
    if not tent:
        raise HTTPException(status_code=404, detail="tent not found")

    controller_base = derive_controller_base_url(tent["source_url"])
    target_url = f"{controller_base}{path}"

    try:
        with httpx.Client(timeout=6.0, follow_redirects=True) as client:
            resp = client.post(target_url)
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}

            # After a successful action, fetch fresh state directly from the controller
            # and persist it immediately so dashboard status updates without poll delay.
            if resp.is_success:
                try:
                    fresh = client.get(tent["source_url"])
                    fresh.raise_for_status()
                    save_state(tent_id, fresh.json())
                except Exception as sync_err:
                    print(f"[action-sync] tent #{tent_id} state refresh failed: {sync_err}")

            return {
                "ok": resp.is_success,
                "tent_id": tent_id,
                "target_url": target_url,
                "status_code": resp.status_code,
                "response": body,
            }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"action request failed: {e}")


@app.get("/tents/{tent_id}/shelly/main/direct")
def shelly_main_direct_state(tent_id: int):
    try:
        return {"ok": True, "checked_at": datetime.now(timezone.utc).isoformat(), "state": get_main_shelly_direct_state(tent_id)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"main shelly direct read failed: {e}")


@app.get("/tents/{tent_id}/shelly/exhaust/direct")
def shelly_exhaust_direct_state(tent_id: int):
    tent = get_tent_by_id(tent_id)
    if not tent:
        raise HTTPException(status_code=404, detail="tent not found")

    latest = get_latest_payload_for_tent(tent_id) or {}
    ip = str((latest or {}).get("settings.shelly.exhaust.ip") or "").strip()
    if not ip:
        raise HTTPException(status_code=400, detail="exhaust shelly ip missing in latest state")

    try:
        st = _get_exhaust_shelly_direct_state_from_payload(latest, tent)
        if not st:
            raise HTTPException(status_code=502, detail="exhaust shelly direct read failed")
        return {"ok": True, "checked_at": datetime.now(timezone.utc).isoformat(), "state": st}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"exhaust shelly direct read failed: {e}")


@app.get("/tents/{tent_id}/shelly/direct-all")
def shelly_direct_all_state(tent_id: int):
    tent = get_tent_by_id(tent_id)
    if not tent:
        raise HTTPException(status_code=404, detail="tent not found")

    latest = get_latest_payload_for_tent(tent_id) or {}
    base = ["main", "light", "humidifier", "heater", "fan", "exhaust"]
    dynamic = []
    for k in (latest or {}).keys():
        m = re.match(r"^settings[.]shelly[.]([^.]+)[.]ip$", str(k))
        if m:
            dynamic.append(m.group(1))
    keys = sorted(set(base + dynamic))

    states = {}
    for k in keys:
        st = _get_shelly_direct_state_for_key(latest, tent, k)
        if st:
            states[k] = st

    return {"ok": True, "checked_at": datetime.now(timezone.utc).isoformat(), "states": states}


@app.post("/tents/{tent_id}/actions/shelly/{device}/toggle")
def toggle_shelly_device(tent_id: int, device: str):
    allowed = {"main", "light", "humidifier", "heater", "fan", "exhaust"}
    if device not in allowed:
        raise HTTPException(status_code=400, detail="unsupported shelly device")

    if device == "main":
        try:
            st = toggle_main_shelly_direct(tent_id)
            return {"ok": True, "tent_id": tent_id, "device": "main", "direct": True, "state": st}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"main shelly direct toggle failed: {e}")

    result = proxy_post_to_tent_action(tent_id, f"/shelly/{device}/toggle")
    result["device"] = device
    return result


@app.post("/tents/{tent_id}/actions/shelly/reset-energy")
def reset_shelly_energy(tent_id: int):
    return proxy_post_to_tent_action(tent_id, "/api/shelly/reset-energy")


@app.post("/tents/{tent_id}/actions/relay/{relay_idx}/toggle")
def toggle_relay(tent_id: int, relay_idx: int):
    if relay_idx < 1 or relay_idx > 5:
        raise HTTPException(status_code=400, detail="relay index must be 1..5")
    result = proxy_post_to_tent_action(tent_id, f"/relay/{relay_idx}/toggle")
    result["relay"] = relay_idx
    return result


@app.post("/tents/{tent_id}/actions/startWatering")
def start_watering(tent_id: int):
    latest_payload = get_latest_payload_for_tent(tent_id) or {}
    active_count = int(latest_payload.get("settings.active_relay_count") or 0)
    if active_count != 8:
        raise HTTPException(status_code=400, detail="startWatering only available for 8x relay tents")

    res = proxy_post_to_tent_action(tent_id, "/startWatering")
    if res.get("ok"):
        try:
            today = date.today()
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE tents SET irrigation_last_run_date=%s WHERE id=%s", (today, tent_id))
            res["irrigation_last_run_date"] = today.isoformat()
        except Exception as e:
            print(f"[startWatering] tent #{tent_id} last_run_date update failed: {e}")
    return res


@app.post("/tents/{tent_id}/actions/pump/{pump_idx}/trigger10s")
def trigger_pump_10s(tent_id: int, pump_idx: int):
    latest_payload = get_latest_payload_for_tent(tent_id) or {}
    active_count = int(latest_payload.get("settings.active_relay_count") or 0)
    if active_count != 8:
        raise HTTPException(status_code=400, detail="pump trigger only available for 8x relay tents")
    if pump_idx not in (6, 7, 8):
        raise HTTPException(status_code=400, detail="pump index must be 6, 7 or 8")
    return proxy_post_to_tent_action(tent_id, f"/pump/{pump_idx}/triggerPump10s")


@app.post("/tents/{tent_id}/actions/pingTank")
def ping_tank(tent_id: int):
    latest_payload = get_latest_payload_for_tent(tent_id) or {}
    active_count = int(latest_payload.get("settings.active_relay_count") or 0)
    if active_count != 8:
        raise HTTPException(status_code=400, detail="pingTank only available for 8x relay tents")
    return proxy_post_to_tent_action(tent_id, "/pingTank")


@app.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request):
    if request.query_params.get("embed") != "1":
        return RedirectResponse(url="/app?page=setup", status_code=302)
    return """
    <html>
      <head>
        <title>GrowTent Setup</title>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <style>
          :root {
            --bg:#0f172a;
            --text:#e2e8f0;
            --card:#1e293b;
            --muted:#94a3b8;
            --grid:rgba(148,163,184,.15);
            --link:#93c5fd;
          }
          :root[data-theme='light'] {
            --bg:#eef2f5;
            --text:#0f172a;
            --card:#f8fafc;
            --muted:#475569;
            --grid:rgba(51,65,85,.18);
            --link:#1d4ed8;
          }
          body { font-family: Arial, sans-serif; margin: 0; background:var(--bg); color:var(--text); }
          .layout { display:flex; min-height:100vh; }
          .sidebar { width:220px; background:var(--card); border-right:1px solid var(--grid); padding:16px; box-sizing:border-box; display:flex; flex-direction:column; }
          .content { flex:1; padding:1.2rem; }
          body.embed .layout { display:block; min-height:auto; }
          body.embed .sidebar { display:none; }
          body.embed .content { padding:.8rem; }
          .navlink { display:block; padding:8px 10px; margin-bottom:8px; border-radius:8px; color:var(--text); text-decoration:none; }
          .navlink.active { background:rgba(59,130,246,.2); }
          .card { background:var(--card); border-radius:12px; padding:14px; max-width:540px; border:1px solid var(--grid); box-shadow:0 8px 24px rgba(2,6,23,.12); }
          .setup-content { display:grid; grid-template-columns:repeat(4, minmax(240px, 1fr)); gap:12px; align-items:start; }
          .setup-content > h1 { grid-column:1 / -1; margin:0 0 2px 0; }
          .section-title { margin:8px 0 2px 0; font-size:.92rem; letter-spacing:.04em; text-transform:uppercase; color:var(--muted); }
          .setup-content .card { max-width:none !important; margin-bottom:0 !important; }
          #rubricAppearance { grid-column:1; grid-row:2; }
          #rubricAccess { grid-column:2; grid-row:2; }
          #rubricStatus { grid-column:3; grid-row:2; }
          #rubricBackup { grid-column:4; grid-row:2; }
          #appearanceCard { grid-column:1; grid-row:3; }
          #accessCard { grid-column:2; grid-row:3; }
          #twofaCard { grid-column:2; grid-row:4; }
          #recoveryCard { grid-column:2; grid-row:5; }
          #guestCard { grid-column:2; grid-row:6; }
          #pushoverCard { grid-column:3; grid-row:3; }
          #backupCard { grid-column:4; grid-row:3; }
          #rubricDevices { grid-column:1 / -1; grid-row:7; }
          #setupTentsCard { grid-column:1 / -1; grid-row:8; }
          @media (max-width: 1200px) {
            .setup-content { grid-template-columns:repeat(2, minmax(280px, 1fr)); }
            .section-title, #appearanceCard, #accessCard, #pushoverCard, #backupCard, #setupTentsCard, #guestCard, #twofaCard, #recoveryCard, #rubricDevices { grid-column:auto; grid-row:auto; }
          }
          @media (max-width: 780px) { .setup-content { grid-template-columns:1fr; } }
          .input-missing { border:1px solid #ef4444 !important; box-shadow:0 0 0 2px rgba(239,68,68,.18); }
          select, button { padding:8px 10px; border-radius:10px; }
          button {
            border:1px solid var(--grid);
            background:linear-gradient(180deg, rgba(59,130,246,.28), rgba(37,99,235,.22));
            color:var(--text);
            font-weight:700;
            cursor:pointer;
            transition:transform .08s ease, box-shadow .15s ease, filter .15s ease;
            box-shadow:0 2px 10px rgba(2,6,23,.22);
          }
          button:hover { filter:brightness(1.06); box-shadow:0 4px 14px rgba(2,6,23,.28); }
          button:active { transform:translateY(1px) scale(.99); }
          a { color:var(--link); }
        </style>
      </head>
      <body class=\"embed\">
        <div class=\"layout\">
          <aside class=\"sidebar\">
            <div id=\"setupNavTitle\" style=\"font-size:.8rem; color:#94a3b8; margin-bottom:10px;\">Navigation</div>
            <div id=\"tentNavSetup\"></div>
            <a class=\"navlink active\" href=\"/app?page=setup\" id=\"setupNavSetup\">Setup</a>
            <a class=\"navlink\" href=\"/app?page=changelog\" id=\"setupNavChangelog\">About</a>
            <!-- sidebar image removed -->
          </aside>
          <main class=\"content setup-content\">
            <h1 id=\"setupTitle\">Setup</h1>
            <div id=\"rubricAppearance\" class=\"section-title\">Appearance</div>
            <div class=\"card\" id=\"appearanceCard\" style=\"margin-bottom:12px;\">
              <div style=\"margin-bottom:8px;\"><strong id=\"appearanceTitle\">Appearance</strong></div>

              <div id=\"labelTheme\" style=\"margin-bottom:8px;\">Theme</div>
              <select id=\"themeSelect\" style=\"margin-bottom:10px;\">
                <option value=\"dark\">Dark</option>
                <option value=\"light\">Light</option>
              </select>

              <div id=\"labelLanguage\" style=\"margin-bottom:8px;\">Language</div>
              <select id=\"langSelect\" style=\"margin-bottom:10px;\">
                <option value=\"en\">English</option>
                <option value=\"de\">Deutsch</option>
              </select>

              <div id=\"labelTempUnit\" style=\"margin-bottom:8px;\">Temperature Unit</div>
              <select id=\"tempUnitSelect\" style=\"margin-bottom:10px;\">
                <option value=\"C\">°C</option>
                <option value=\"F\">°F</option>
              </select>

              <!-- history range moved to dashboard -->
              <!-- removed from setup -->

              <div>
                <button id=\"saveBtn\">Save</button>
              </div>
              <div id=\"msg\" style=\"margin-top:10px;\"></div>
            </div>


            <div id=\"rubricAccess\" class=\"section-title\">Access</div>
            <div id=\"rubricStatus\" class=\"section-title\">Status notifications</div>
            <div id=\"rubricBackup\" class=\"section-title\">Backup</div>
            <div class=\"card\" id=\"accessCard\" style=\"margin-bottom:12px; max-width:540px;\">
              <div style=\"margin-bottom:8px;\"><strong id=\"accessTitle\">Access</strong></div>
              <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:10px;\">
                <input type=\"checkbox\" id=\"authEnabled\" />
                <span id=\"authEnabledLabel\">Enable user authentication</span>
              </label>
              <form id=\"authForm\" onsubmit=\"return false;\" autocomplete=\"on\">
              <div id=\"authUserLabel\" style=\"margin-bottom:6px;\">Username</div>
              <input id=\"authUsername\" autocomplete=\"username\" placeholder=\"admin\" style=\"padding:8px 10px; border-radius:8px; width:220px; margin-bottom:10px;\" />
              <div id=\"authPassLabel\" style=\"margin-bottom:6px;\">Password (leave empty to keep unchanged)</div>
              <input id=\"authPassword\" autocomplete=\"current-password\" type=\"password\" placeholder=\"********\" style=\"padding:8px 10px; border-radius:8px; width:220px; margin-bottom:10px;\" />
              <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:10px;\">
                <input type=\"checkbox\" id=\"showAuthPassword\" />
                <span id=\"showAuthPasswordLabel\">Show password</span>
              </label>
              <!-- pushover fields moved to dedicated card -->
              <!-- 2FA toggle moved to dedicated card -->
              <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">
                <button type=\"button\" id=\"genAuthPassBtn\">Generate password</button>
                <button type=\"button\" id=\"saveAuthBtn\">Save</button>
              </div>
              </form>
              <div id=\"authMsg\" style=\"margin-top:10px;\"></div>
              <div id=\"auth2faInfo\" style=\"margin-top:10px; font-size:.9rem;\"></div>
            </div>

            <div class=\"card\" id=\"guestCard\" style=\"margin-bottom:12px; max-width:540px;\">
              <div style=\"margin-bottom:8px;\"><strong id=\"guestTitle\">Guest mode (read-only)</strong></div>
              <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:10px;\">
                <input type=\"checkbox\" id=\"guestEnabled\" />
                <span id=\"guestEnabledLabel\">Enable guest login (view-only)</span>
              </label>
              <div id=\"guestUserLabel\" style=\"margin-bottom:6px;\">Guest username</div>
              <input id=\"guestUsername\" placeholder=\"guest\" style=\"padding:8px 10px; border-radius:8px; width:220px; margin-bottom:10px;\" />
              <div id=\"guestPassLabel\" style=\"margin-bottom:6px;\">Guest password (leave empty to keep unchanged)</div>
              <input id=\"guestPassword\" type=\"password\" placeholder=\"********\" style=\"padding:8px 10px; border-radius:8px; width:220px; margin-bottom:10px;\" />
              <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:10px;\">
                <input type=\"checkbox\" id=\"showGuestPassword\" />
                <span id=\"showGuestPasswordLabel\">Show password</span>
              </label>
              <div id=\"guestExpLabel\" style=\"margin-bottom:6px;\">Guest expires at</div>
              <input id=\"guestExpiresAt\" type=\"datetime-local\" style=\"padding:8px 10px; border-radius:8px; width:260px; margin-bottom:10px;\" />
              <div style=\"display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px;\">
                <button type=\"button\" id=\"genGuestPassBtn\">Generate password</button>
                <button type=\"button\" id=\"saveGuestBtn\">Save guest</button>
              </div>
            </div>

            <div class=\"card\" id=\"pushoverCard\" style=\"margin-bottom:12px; max-width:540px;\">
              <div style=\"margin-bottom:8px;\"><strong id=\"pushoverTitle\">Pushover status notifications</strong></div>
              <div id=\"pushoverAppTokenLabel\" style=\"margin-bottom:6px;\">Pushover app token</div>
              <input id=\"pushoverAppToken\" placeholder=\"aPpToKen\" style=\"padding:8px 10px; border-radius:8px; width:300px; margin-bottom:10px;\" />
              <div id=\"pushoverUserKeyLabel\" style=\"margin-bottom:6px;\">Pushover user key</div>
              <input id=\"pushoverUserKey\" placeholder=\"uSeRkEy\" style=\"padding:8px 10px; border-radius:8px; width:300px; margin-bottom:10px;\" />
              <div id=\"pushoverDeviceLabel\" style=\"margin-bottom:6px;\">Pushover device (optional)</div>
              <input id=\"pushoverDevice\" placeholder=\"e.g. iphone\" style=\"padding:8px 10px; border-radius:8px; width:220px; margin-bottom:10px;\" />
              <div class=\"muted\">Status messages for online/offline transitions from poller.</div>
            </div>

            <div class=\"card\" id=\"apiHistoryCard\" style=\"margin-bottom:12px; max-width:540px;\">
              <div style=\"margin-bottom:8px;\"><strong id=\"apiHistoryTitle\">API Access</strong></div>
              <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:10px;\">
                <input type=\"checkbox\" id=\"historyApiEnabled\" checked />
                <span id=\"historyApiEnabledLabel\">Enable /api/history endpoint</span>
              </label>
              <button type=\"button\" id=\"saveApiAccessBtn\" style=\"margin-bottom:10px;\">Save API access</button>
              <div id=\"apiHistoryExampleLabel\" class=\"muted\">Example call:</div>
              <div id=\"apiHistoryExampleValue\" class=\"muted\" style=\"font-family:monospace; word-break:break-all;\">/api/history?deviceId=1</div>
            </div>

            <!-- rubricSecurity removed -->
            <div class=\"card\" id=\"twofaCard\" style=\"margin-bottom:12px; max-width:540px;\">
              <div style=\"margin-bottom:8px;\"><strong>2FA (TOTP)</strong></div>
              <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:10px;\">
                <input type=\"checkbox\" id=\"auth2faEnabled\" />
                <span id=\"auth2faEnabledLabel\">Enable 2FA (TOTP)</span>
              </label>
              <button type=\"button\" id=\"save2faBtn\">Save 2FA</button>
              <div id=\"twofaMsg\" style=\"margin-top:8px;\"></div>
              <div id=\"twofaInfo\" style=\"margin-top:10px; font-size:.9rem;\"></div>
              <div class=\"muted\" style=\"margin-top:8px;\">Click Save 2FA, then scan QR code and verify one app code.</div>
            </div>

            <div class=\"card\" id=\"recoveryCard\" style=\"margin-bottom:12px; max-width:540px;\">
              <div style=\"margin-bottom:8px;\"><strong id=\"recoveryTitle\">Backup and Restore</strong></div>
              <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:6px;\">
                <input type=\"checkbox\" id=\"regenRecoveryCodes\" />
                <span id=\"regenRecoveryCodesLabel\">Regenerate recovery codes</span>
              </label>
              <button type=\"button\" id=\"saveRecoveryBtn\">Save backup/restore</button>
              <div id=\"recoveryMsg\" style=\"margin-top:8px;\"></div>
              <div class=\"muted\">Generates new one-time recovery codes when enabled and saved.</div>
            </div>

            <div class=\"card\" id=\"backupCard\" style=\"margin-bottom:12px; max-width:540px;\">
              <div style=\"margin-bottom:8px;\"><strong id=\"backupTitle\">Backup</strong></div>
              <div style=\"display:flex; gap:8px; flex-wrap:wrap; align-items:center;\">
                <button type=\"button\" id=\"exportBackupBtn\">Export backup</button>
                <input type=\"file\" id=\"importBackupFile\" accept=\"application/json\" />
                <button type=\"button\" id=\"importBackupBtn\">Import backup</button>
              </div>
              <div id=\"backupMsg\" style=\"margin-top:8px;\"></div>
            </div>

            <div id=\"rubricDevices\" class=\"section-title\">Devices & Tents</div>
            <div class=\"card\" id=\"setupTentsCard\" style=\"margin-bottom:12px; max-width:900px;\">
              <div style=\"margin-bottom:8px;\"><strong id=\"tentsTitle\">Tents</strong></div>
              <div id=\"tentList\" style=\"margin-bottom:10px; font-size:.92rem;\"></div>
              <input id=\"tentName\" placeholder=\"Tent name (e.g. Tent 2)\" style=\"padding:8px 10px; border-radius:8px; width:220px;\" />
              <input id=\"tentUrl\" placeholder=\"Source URL (http://.../api/state)\" style=\"padding:8px 10px; border-radius:8px; width:min(520px, 90%); margin-left:6px;\" />
              <input id=\"tentRtsp\" placeholder=\"RTSP URL (rtsp://...)\" style=\"padding:8px 10px; border-radius:8px; width:min(520px, 90%); margin-left:6px; margin-top:6px;\" />
              <input id=\"tentMainUser\" placeholder=\"Shelly Main User (optional)\" style=\"padding:8px 10px; border-radius:8px; width:220px; margin-left:6px; margin-top:6px;\" />
              <input id=\"tentMainPass\" type=\"password\" placeholder=\"Shelly Main Password (optional)\" style=\"padding:8px 10px; border-radius:8px; width:260px; margin-left:6px; margin-top:6px;\" />
              <button id=\"addTentBtn\">Add tent</button>
              <div id=\"tentMsg\" style=\"margin-top:10px;\"></div>
            </div>

            <div id=\"irPlanModal\" style=\"display:none; position:fixed; inset:0; background:rgba(2,6,23,.65); z-index:1000; align-items:center; justify-content:center; padding:16px;\">
              <div class=\"card\" style=\"max-width:520px; width:100%;\">
                <div style=\"display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:10px;\">
                  <strong id=\"irPlanTitle\">Bewässerungsplan</strong>
                  <button type=\"button\" id=\"irPlanCloseBtn\">✕</button>
                </div>
                <div id=\"irPlanTentLabel\" class=\"small\" style=\"margin-bottom:10px;\">-</div>
                <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:10px;\">
                  <input type=\"checkbox\" id=\"irPlanEnabled\" />
                  <span id=\"irPlanEnabledLabel\">Aktiv</span>
                </label>
                <div id=\"irPlanEveryDaysLabel\" style=\"margin-bottom:6px;\">Alle N Tage</div>
                <input id=\"irPlanEveryDays\" type=\"number\" min=\"1\" step=\"1\" style=\"padding:8px 10px; border-radius:8px; width:160px; margin-bottom:10px;\" />
                <div id=\"irPlanOffsetLabel\" style=\"margin-bottom:6px;\">Minuten nach Licht an</div>
                <input id=\"irPlanOffset\" type=\"number\" min=\"0\" step=\"1\" style=\"padding:8px 10px; border-radius:8px; width:160px; margin-bottom:10px;\" />
                <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">
                  <button type=\"button\" id=\"irPlanSaveBtn\">Plan speichern</button>
                  <button type=\"button\" id=\"irPlanCancelBtn\">Abbrechen</button>
                </div>
                <div id=\"irPlanMsg\" style=\"margin-top:10px;\"></div>
              </div>
            </div>
          </main>
        </div>

        <script>
          const isEmbed = new URLSearchParams(window.location.search).get('embed') === '1';
          if (isEmbed) document.body.classList.add('embed');

          const sel = document.getElementById('themeSelect');
          const langSel = document.getElementById('langSelect');
          const unitSel = document.getElementById('tempUnitSelect');
          const msg = document.getElementById('msg');
          const authEnabledEl = document.getElementById('authEnabled');
          const authUsernameEl = document.getElementById('authUsername');
          const authPasswordEl = document.getElementById('authPassword');
          const auth2faEnabledEl = document.getElementById('auth2faEnabled');
          const regenRecoveryCodesEl = document.getElementById('regenRecoveryCodes');
          const authMsgEl = document.getElementById('authMsg');
          const auth2faInfoEl = document.getElementById('auth2faInfo');
          const twofaMsgEl = document.getElementById('twofaMsg');
          const twofaInfoEl = document.getElementById('twofaInfo');
          const recoveryMsgEl = document.getElementById('recoveryMsg');
          const authFormEl = document.getElementById('authForm');
          const guestEnabledEl = document.getElementById('guestEnabled');
          const guestUsernameEl = document.getElementById('guestUsername');
          const guestPasswordEl = document.getElementById('guestPassword');
          const guestExpiresAtEl = document.getElementById('guestExpiresAt');
          const pushoverAppTokenEl = document.getElementById('pushoverAppToken');
          const pushoverUserKeyEl = document.getElementById('pushoverUserKey');
          const pushoverDeviceEl = document.getElementById('pushoverDevice');
          const historyApiEnabledEl = document.getElementById('historyApiEnabled');
          let pending2faToken = '';
          let currentPlanTentId = 0;

          const I18N_SETUP = {
            en: {
              nav: 'Navigation',
              setup: 'Setup',
              appearance: 'Appearance',
              theme: 'Theme',
              language: 'Language',
              tempUnit: 'Temperature Unit',
              range: 'History range',
              tents: 'Tents',
              save: 'Save',
              access: 'Admin mode',
              enableAuth: 'Enable user authentication',
              username: 'Username',
              passwordHint: 'Password (leave empty to keep unchanged)',
              saveAccess: 'Save',
              genPassword: 'Generate password',
              showPassword: 'Show password',
              pushoverAppToken: 'Pushover app token',
              pushoverUserKey: 'Pushover user key',
              pushoverDevice: 'Pushover device (optional)',
              gromateApiPassword: 'API-History-Password',
              twofa: 'Enable 2FA (TOTP)',
              regenRecovery: 'Regenerate recovery codes',
              recoveryTitle: 'Backup and Restore',
              saveRecovery: 'Save backup/restore',
              irrigationPlan: 'Irrigation plan',
              everyDays: 'Every N days',
              offsetAfterLight: 'Minutes after light on',
              savePlan: 'Save plan',
              active: 'Active',
              guestTitle: 'Guest mode (read-only)',
              guestEnabled: 'Enable guest login (view-only)',
              guestUsername: 'Guest username',
              guestPassword: 'Guest password (leave empty to keep unchanged)',
              guestExpiresAt: 'Guest expires at',
              saveGuest: 'Save guest',
              backup: 'Backup',
              exportBackup: 'Export backup',
              importBackup: 'Import backup',
              rubricAppearance: 'Appearance',
              rubricAccess: 'Access',
              rubricStatus: 'Status notifications',
              rubricBackup: 'Backup',
              rubricDevices: 'Tents',
              pushoverTitle: 'Pushover status notifications',
              apiHistoryTitle: 'API Access',
              historyApiEnabled: 'Enable /api/history endpoint',
              saveApiAccess: 'Save API access',
              apiHistoryExampleLabel: 'Example call:',
              apiHistoryPerTent: 'API History'
            },
            de: {
              nav: 'Navigation',
              setup: 'Setup',
              appearance: 'Darstellung',
              theme: 'Theme',
              language: 'Sprache',
              tempUnit: 'Temperatureinheit',
              range: 'Zeitraum Historie',
              tents: 'Zelte',
              save: 'Speichern',
              access: 'Adminmodus',
              enableAuth: 'Benutzerauth aktivieren',
              username: 'Benutzername',
              passwordHint: 'Passwort (leer lassen = unverändert)',
              saveAccess: 'Speichern',
              genPassword: 'Passwort generieren',
              showPassword: 'Passwort anzeigen',
              pushoverAppToken: 'Pushover App-Token',
              pushoverUserKey: 'Pushover User-Key',
              pushoverDevice: 'Pushover-Gerät (optional)',
              gromateApiPassword: 'Passwort für Device-History-API',
              twofa: '2FA (TOTP) aktivieren',
              regenRecovery: 'Recovery-Codes neu erzeugen',
              recoveryTitle: 'Backup und Restore',
              saveRecovery: 'Backup/Restore speichern',
              irrigationPlan: 'Bewässerungsplan',
              everyDays: 'Alle N Tage',
              offsetAfterLight: 'Minuten nach Licht an',
              savePlan: 'Plan speichern',
              active: 'Aktiv',
              guestTitle: 'Gastmodus (nur lesen)',
              guestEnabled: 'Gast-Login aktivieren (nur Ansicht)',
              guestUsername: 'Gast-Benutzername',
              guestPassword: 'Gast-Passwort (leer = unverändert)',
              guestExpiresAt: 'Gast gültig bis',
              saveGuest: 'Gast speichern',
              backup: 'Backup',
              exportBackup: 'Backup exportieren',
              importBackup: 'Backup importieren',
              rubricAppearance: 'Darstellung',
              rubricAccess: 'Zugriff',
              rubricStatus: 'Statusmeldungen',
              rubricBackup: 'Backup',
              rubricDevices: 'Zelte',
              pushoverTitle: 'Pushover-Statusmeldungen',
              apiHistoryTitle: 'API-Zugriff',
              historyApiEnabled: '/api/history-Schnittstelle aktivieren',
              saveApiAccess: 'API-Zugriff speichern',
              apiHistoryExampleLabel: 'Beispielaufruf:',
              apiHistoryPerTent: 'API-History'
            }
          };

          function tSetup(key){
            const lang = (langSel?.value === 'de') ? 'de' : 'en';
            return (I18N_SETUP[lang] && I18N_SETUP[lang][key]) || I18N_SETUP.en[key] || key;
          }

          function applySetupI18n(){
            const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
            set('setupNavTitle', tSetup('nav'));
            set('setupNavSetup', tSetup('setup'));
            set('setupTitle', tSetup('setup'));
            set('rubricAppearance', tSetup('rubricAppearance'));
            set('rubricAccess', tSetup('rubricAccess'));
            set('rubricStatus', tSetup('rubricStatus'));
            set('rubricBackup', tSetup('rubricBackup'));
            set('rubricDevices', tSetup('rubricDevices'));
            set('appearanceTitle', tSetup('appearance'));
            set('labelTheme', tSetup('theme'));
            set('labelLanguage', tSetup('language'));
            set('labelTempUnit', tSetup('tempUnit'));
            set('tentsTitle', tSetup('tents'));
            set('saveBtn', tSetup('save'));
            set('accessTitle', tSetup('access'));
            set('authEnabledLabel', tSetup('enableAuth'));
            set('authUserLabel', tSetup('username'));
            set('authPassLabel', tSetup('passwordHint'));
            set('showAuthPasswordLabel', tSetup('showPassword'));
            set('showGuestPasswordLabel', tSetup('showPassword'));
            set('pushoverTitle', tSetup('pushoverTitle'));
            set('pushoverAppTokenLabel', tSetup('pushoverAppToken'));
            set('pushoverUserKeyLabel', tSetup('pushoverUserKey'));
            set('pushoverDeviceLabel', tSetup('pushoverDevice'));
            set('apiHistoryTitle', tSetup('apiHistoryTitle'));
            set('historyApiEnabledLabel', tSetup('historyApiEnabled'));
            set('saveApiAccessBtn', tSetup('saveApiAccess'));
            set('apiHistoryExampleLabel', tSetup('apiHistoryExampleLabel'));
            const ex = document.getElementById('apiHistoryExampleValue');
            if (ex) ex.textContent = '/api/history?deviceId=1';
            set('auth2faEnabledLabel', tSetup('twofa'));
            set('regenRecoveryCodesLabel', tSetup('regenRecovery'));
            set('recoveryTitle', tSetup('recoveryTitle'));
            set('saveRecoveryBtn', tSetup('saveRecovery'));
            set('genAuthPassBtn', tSetup('genPassword'));
            set('genGuestPassBtn', tSetup('genPassword'));
            set('saveAuthBtn', tSetup('saveAccess'));
            set('irPlanTitle', tSetup('irrigationPlan'));
            set('irPlanEnabledLabel', tSetup('active'));
            set('irPlanEveryDaysLabel', tSetup('everyDays'));
            set('irPlanOffsetLabel', tSetup('offsetAfterLight'));
            set('irPlanSaveBtn', tSetup('savePlan'));
            set('guestTitle', tSetup('guestTitle'));
            set('guestEnabledLabel', tSetup('guestEnabled'));
            set('guestUserLabel', tSetup('guestUsername'));
            set('guestPassLabel', tSetup('guestPassword'));
            set('guestExpLabel', tSetup('guestExpiresAt'));
            set('saveGuestBtn', tSetup('saveGuest'));
            set('backupTitle', tSetup('backup'));
            set('exportBackupBtn', tSetup('exportBackup'));
            set('importBackupBtn', tSetup('importBackup'));
          }

          function applyTheme(theme){
            const t = theme === 'light' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', t);
          }

          const initialTheme = (localStorage.getItem('gt_theme') || 'dark');
          const initialLang = (localStorage.getItem('gt_lang') || 'en');
          const initialUnit = (localStorage.getItem('gt_temp_unit') || 'C');

          sel.value = initialTheme;
          langSel.value = (initialLang === 'de') ? 'de' : 'en';
          unitSel.value = (initialUnit === 'F') ? 'F' : 'C';
          applyTheme(initialTheme);
          applySetupI18n();

          langSel.addEventListener('change', () => {
            applySetupI18n();
          });

          function closeIrrigationPlanModal(){
            const modal = document.getElementById('irPlanModal');
            if (modal) modal.style.display = 'none';
            currentPlanTentId = 0;
          }

          async function openIrrigationPlanModal(tent){
            const modal = document.getElementById('irPlanModal');
            const msg = document.getElementById('irPlanMsg');
            const title = document.getElementById('irPlanTentLabel');
            const enabledEl = document.getElementById('irPlanEnabled');
            const everyEl = document.getElementById('irPlanEveryDays');
            const offsetEl = document.getElementById('irPlanOffset');
            if (!modal || !enabledEl || !everyEl || !offsetEl) return;

            currentPlanTentId = Number(tent.id || 0);
            if (title) title.textContent = `#${tent.id} ${tent.name}`;
            if (msg) msg.textContent = '';
            modal.style.display = 'flex';

            try {
              const res = await fetch(`/tents/${currentPlanTentId}/irrigation-plan`, { cache: 'no-store' });
              const j = await res.json();
              const p = j?.plan || {};
              enabledEl.checked = !!p.enabled;
              everyEl.value = Number(p.every_n_days || 1);
              offsetEl.value = Number(p.offset_after_light_on_min || 0);
              if (msg && j?.last_run_date) msg.textContent = `Last run: ${j.last_run_date}`;
            } catch {
              enabledEl.checked = false;
              everyEl.value = 1;
              offsetEl.value = 0;
              if (msg) msg.textContent = 'Failed to load plan.';
            }
          }

          async function saveIrrigationPlan(){
            const msg = document.getElementById('irPlanMsg');
            const enabledEl = document.getElementById('irPlanEnabled');
            const everyEl = document.getElementById('irPlanEveryDays');
            const offsetEl = document.getElementById('irPlanOffset');
            if (!currentPlanTentId || !enabledEl || !everyEl || !offsetEl) return;

            const payload = {
              enabled: !!enabledEl.checked,
              every_n_days: Math.max(1, Number(everyEl.value || 1)),
              offset_after_light_on_min: Math.max(0, Number(offsetEl.value || 0)),
            };

            try {
              const res = await fetch(`/tents/${currentPlanTentId}/irrigation-plan`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
              });
              if (!res.ok) {
                const err = await res.text();
                if (msg) msg.textContent = `Save failed: ${err}`;
                return;
              }
              if (msg) msg.textContent = 'Plan saved.';
              await loadTents();
            } catch {
              if (msg) msg.textContent = 'Save failed.';
            }
          }

          document.getElementById('irPlanCloseBtn')?.addEventListener('click', closeIrrigationPlanModal);
          document.getElementById('irPlanCancelBtn')?.addEventListener('click', closeIrrigationPlanModal);
          document.getElementById('irPlanSaveBtn')?.addEventListener('click', saveIrrigationPlan);

          async function loadTents(){
            const list = document.getElementById('tentList');
            if (!list) return;
            try {
              const res = await fetch('/tents', { cache: 'no-store' });
              const tents = await res.json();
              if (!Array.isArray(tents) || tents.length === 0) {
                list.innerHTML = '<div>No tents configured.</div>';
                return;
              }
              list.innerHTML = tents.map(t => {
                const p = t.irrigation_plan || {};
                const planTxt = p.enabled
                  ? `${tSetup('everyDays')}: ${Number(p.every_n_days || 1)} · ${tSetup('offsetAfterLight')}: ${Number(p.offset_after_light_on_min || 0)}`
                  : '-';
                return `
                <div style="padding:6px 0; border-bottom:1px solid var(--grid);">
                  <strong>#${t.id} ${t.name}</strong><br>
                  <span style="opacity:.85">API: ${t.source_url}</span><br>
                  <span style="opacity:.85">RTSP: ${t.rtsp_url || '-'}</span><br>
                  <span style="opacity:.85">Shelly Main Auth: ${t.shelly_main_user ? 'set' : '-'}</span><br>
                  <span style="opacity:.85">${tSetup('irrigationPlan')}: ${planTxt}</span><br>
                  <span style="opacity:.85; font-family:monospace; word-break:break-all;">${tSetup('apiHistoryPerTent')}: /api/history?deviceId=${t.id}</span><br>
                  <button data-edit-tent="${t.id}" style="margin-top:6px;">Edit</button>
                  <button data-plan-tent="${t.id}" style="margin-top:6px; margin-left:6px;">${tSetup('irrigationPlan')}</button>
                  <button data-delete-tent="${t.id}" style="margin-top:6px; margin-left:6px; background:linear-gradient(180deg, rgba(239,68,68,.35), rgba(220,38,38,.28)); border-color:rgba(239,68,68,.45);">Delete</button>
                </div>
              `;
              }).join('');

              list.querySelectorAll('button[data-edit-tent]').forEach(btn => {
                btn.addEventListener('click', () => {
                  const id = Number(btn.getAttribute('data-edit-tent'));
                  const tent = tents.find(x => x.id === id);
                  if (!tent) return;
                  document.getElementById('tentName').value = tent.name;
                  document.getElementById('tentUrl').value = tent.source_url;
                  document.getElementById('tentRtsp').value = tent.rtsp_url || '';
                  document.getElementById('tentMainUser').value = tent.shelly_main_user || '';
                  document.getElementById('tentMainPass').value = tent.shelly_main_password || '';
                  document.getElementById('addTentBtn').setAttribute('data-edit-id', String(id));
                  document.getElementById('addTentBtn').textContent = 'Save tent';
                });
              });
              list.querySelectorAll('button[data-plan-tent]').forEach(btn => {
                btn.addEventListener('click', () => {
                  const id = Number(btn.getAttribute('data-plan-tent'));
                  const tent = tents.find(x => x.id === id);
                  if (!tent) return;
                  openIrrigationPlanModal(tent);
                });
              });

              list.querySelectorAll('button[data-delete-tent]').forEach(btn => {
                btn.addEventListener('click', async () => {
                  const id = Number(btn.getAttribute('data-delete-tent'));
                  const tent = tents.find(x => x.id === id);
                  if (!tent) return;
                  const ok = confirm(`Delete tent #${tent.id} ${tent.name}?`);
                  if (!ok) return;
                  try {
                    const res = await fetch(`/tents/${id}`, { method: 'DELETE' });
                    if (!res.ok) {
                      tentMsg.textContent = 'Delete failed.';
                      return;
                    }
                    tentMsg.textContent = 'Tent deleted.';
                    await loadTents();
                  } catch {
                    tentMsg.textContent = 'Delete failed.';
                  }
                });
              });
            } catch (e) {
              list.textContent = 'Failed to load tents.';
            }
          }

          document.getElementById('saveBtn').addEventListener('click', () => {
            const theme = sel.value === 'light' ? 'light' : 'dark';
            const lang = langSel.value === 'de' ? 'de' : 'en';
            const unit = unitSel.value === 'F' ? 'F' : 'C';
            localStorage.setItem('gt_theme', theme);
            localStorage.setItem('gt_lang', lang);
            localStorage.setItem('gt_temp_unit', unit);
            applyTheme(theme);
            msg.textContent = 'Saved.';
          });

          document.getElementById('exportBackupBtn')?.addEventListener('click', () => {
            window.location.href = '/config/backup/export';
          });

          document.getElementById('importBackupBtn')?.addEventListener('click', async () => {
            const fileEl = document.getElementById('importBackupFile');
            const msgEl = document.getElementById('backupMsg');
            const f = fileEl?.files?.[0];
            if (!f) {
              if (msgEl) msgEl.textContent = 'Please select a backup JSON file.';
              return;
            }
            try {
              const txt = await f.text();
              const data = JSON.parse(txt);
              const res = await fetch('/config/backup/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
              });
              const j = await res.json().catch(() => ({}));
              if (!res.ok) {
                if (msgEl) msgEl.textContent = `Import failed: ${j?.detail || res.status}`;
                return;
              }
              if (msgEl) msgEl.textContent = `Import ok. Tents: ${j?.imported_tents ?? 0}`;
              await loadTents();
              await loadAuthConfigUi();
            } catch (e) {
              if (msgEl) msgEl.textContent = 'Import failed.';
            }
          });

          async function loadAuthConfigUi(){
            if (!authEnabledEl || !authUsernameEl) return;
            try {
              const res = await fetch('/config/auth', { cache: 'no-store' });
              const cfg = await res.json();
              authEnabledEl.checked = !!cfg.enabled;
              authUsernameEl.value = cfg.username || 'admin';
              if (auth2faEnabledEl) auth2faEnabledEl.checked = !!cfg.twofa_enabled;
              if (guestEnabledEl) guestEnabledEl.checked = !!cfg.guest_enabled;
              if (guestUsernameEl) guestUsernameEl.value = cfg.guest_username || '';
              if (guestExpiresAtEl) {
                const iso = (cfg.guest_expires_at || '').toString();
                guestExpiresAtEl.value = iso ? iso.slice(0,16) : '';
              }
              if (pushoverAppTokenEl) pushoverAppTokenEl.value = cfg.pushover_app_token || '';
              if (pushoverUserKeyEl) pushoverUserKeyEl.value = cfg.pushover_user_key || '';
              if (pushoverDeviceEl) pushoverDeviceEl.value = cfg.pushover_device || '';
              if (historyApiEnabledEl) historyApiEnabledEl.checked = (cfg.history_api_enabled !== false);
              authUsernameEl.classList.remove('input-missing');
              authPasswordEl?.classList.remove('input-missing');
              if (twofaInfoEl) {
                const parts = [];
                parts.push(`Password set: ${cfg.has_password ? 'yes' : 'no'}.`);
                if (cfg.twofa_enabled) parts.push('2FA active.');
                auth2faInfoEl.innerHTML = parts.join('<br>');
              }
            } catch {
              if (authMsgEl) authMsgEl.textContent = 'Failed to load access settings.';
            }
          }

          document.getElementById('showAuthPassword')?.addEventListener('change', (ev) => {
            if (!authPasswordEl) return;
            authPasswordEl.type = ev.target.checked ? 'text' : 'password';
          });

          document.getElementById('showGuestPassword')?.addEventListener('change', (ev) => {
            if (!guestPasswordEl) return;
            guestPasswordEl.type = ev.target.checked ? 'text' : 'password';
          });

          authFormEl?.addEventListener('submit', (ev) => ev.preventDefault());

          auth2faEnabledEl?.addEventListener('change', () => {
            if (auth2faEnabledEl.checked && authEnabledEl) authEnabledEl.checked = true;
          });

          function generateStrongPassword(len = 20){
            const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@$%*+-_';
            let out = '';
            if (window.crypto && window.crypto.getRandomValues) {
              const arr = new Uint32Array(len);
              window.crypto.getRandomValues(arr);
              for (let i = 0; i < len; i++) out += alphabet[arr[i] % alphabet.length];
            } else {
              for (let i = 0; i < len; i++) out += alphabet[Math.floor(Math.random() * alphabet.length)];
            }
            return out;
          }

          document.getElementById('genAuthPassBtn')?.addEventListener('click', () => {
            if (!authPasswordEl) return;
            authPasswordEl.value = generateStrongPassword(20);
            if (authMsgEl) authMsgEl.textContent = 'Password generated. Please save access settings.';
          });

          document.getElementById('genGuestPassBtn')?.addEventListener('click', () => {
            if (!guestPasswordEl) return;
            guestPasswordEl.value = generateStrongPassword(20);
            if (authMsgEl) authMsgEl.textContent = 'Guest password generated. Please save access settings.';
          });

          document.getElementById('save2faBtn')?.addEventListener('click', async () => {
            try {
              const pre = await fetch('/config/auth');
              let pcfg = await pre.json().catch(() => ({}));
              if (!pcfg?.enabled || !pcfg?.has_password) {
                const u = (authUsernameEl?.value || '').trim();
                const p = (authPasswordEl?.value || '').trim();
                if (!u || !p) {
                  if (twofaMsgEl) twofaMsgEl.textContent = 'Bitte zuerst Username + Passwort eintragen (Access), dann Save 2FA.';
                  return;
                }
                const bootstrap = await fetch('/config/auth', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ enabled: true, username: u, password: p })
                });
                const bbody = await bootstrap.json().catch(() => ({}));
                if (!bootstrap.ok) {
                  if (twofaMsgEl) twofaMsgEl.textContent = bbody?.detail || 'Access setup failed.';
                  return;
                }
                pcfg = { enabled: true, username: u, has_password: true };
                authEnabledEl.checked = true;
              }

              const res = await fetch('/config/auth/2fa', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !!auth2faEnabledEl?.checked, regenerate_recovery_codes: false })
              });
              const body = await res.json().catch(() => ({}));
              if (!res.ok) {
                if (twofaMsgEl) twofaMsgEl.textContent = body?.detail || 'Failed to save 2FA settings.';
                return;
              }
              if (auth2faInfoEl) {
                const parts = [];
                if (body?.pending_2fa && (body?.qr_png_url || body?.otpauth_url)) {
                  pending2faToken = body?.verify_token || '';
                  const qr = body?.qr_png_url || `/auth/qr.png?u=${encodeURIComponent(body.otpauth_url)}`;
                  parts.push(`<div style="margin-bottom:8px;"><strong>2FA QR Code</strong><br><img src="${qr}" alt="2FA QR" style="width:180px;height:180px;border-radius:8px;border:1px solid rgba(148,163,184,.3);"/></div>`);
                  if (Array.isArray(body?.recovery_codes) && body.recovery_codes.length) {
                    parts.push(`<div><strong>Recovery Codes</strong><br><code style="white-space:pre-wrap;word-break:break-word;">${body.recovery_codes.join('\\n')}</code></div>`);
                  }
                  parts.push(`<div style="margin-top:8px;"><input id="verify2faCode" placeholder="2FA Code aus App" style="padding:8px 10px; border-radius:8px; width:220px;" /> <button id="verify2faBtn" style="margin-top:8px;">2FA verifizieren</button></div>`);
                  twofaInfoEl.innerHTML = parts.join('');
                  document.getElementById('verify2faBtn')?.addEventListener('click', async () => {
                    const code = (document.getElementById('verify2faCode')?.value || '').trim();
                    const vr = await fetch('/config/auth/2fa/verify', {
                      method:'POST', headers:{'Content-Type':'application/json'},
                      body: JSON.stringify({ token: pending2faToken, code })
                    });
                    const vb = await vr.json().catch(() => ({}));
                    if (!vr.ok) { if (twofaMsgEl) twofaMsgEl.textContent = vb?.detail || '2FA verify failed'; return; }
                    if (twofaMsgEl) twofaMsgEl.textContent = '2FA verified and enabled.';
                    await loadAuthConfigUi();
                  });
                  if (twofaMsgEl) twofaMsgEl.textContent = 'Scan QR, then enter app code to verify 2FA.';
                  return;
                }
                twofaInfoEl.innerHTML = '';
              }
              if (twofaMsgEl) twofaMsgEl.textContent = body?.twofa_enabled ? '2FA enabled.' : '2FA disabled.';
              await loadAuthConfigUi();
            } catch {
              if (twofaMsgEl) twofaMsgEl.textContent = 'Failed to save 2FA settings.';
            }
          });

          document.getElementById('saveRecoveryBtn')?.addEventListener('click', async () => {
            try {
              const res = await fetch('/config/auth/2fa', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !!auth2faEnabledEl?.checked, regenerate_recovery_codes: !!regenRecoveryCodesEl?.checked })
              });
              const body = await res.json().catch(() => ({}));
              if (!res.ok) {
                if (recoveryMsgEl) recoveryMsgEl.textContent = body?.detail || 'Failed to save recovery settings.';
                return;
              }
              if (Array.isArray(body?.recovery_codes) && body.recovery_codes.length && twofaInfoEl) {
                twofaInfoEl.innerHTML = `<div><strong>Recovery Codes</strong><br><code style="white-space:pre-wrap;word-break:break-word;">${body.recovery_codes.join('\\n')}</code></div>`;
              }
              if (regenRecoveryCodesEl) regenRecoveryCodesEl.checked = false;
              if (recoveryMsgEl) recoveryMsgEl.textContent = 'Recovery codes updated.';
            } catch {
              if (recoveryMsgEl) recoveryMsgEl.textContent = 'Failed to save recovery settings.';
            }
          });

          document.getElementById('saveGuestBtn')?.addEventListener('click', async () => {
            document.getElementById('saveAuthBtn')?.click();
          });

          document.getElementById('saveApiAccessBtn')?.addEventListener('click', async () => {
            document.getElementById('saveAuthBtn')?.click();
          });

          document.getElementById('saveAuthBtn')?.addEventListener('click', async () => {
            if (!authEnabledEl || !authUsernameEl || !authPasswordEl) return;

            authUsernameEl.classList.remove('input-missing');
            authPasswordEl.classList.remove('input-missing');

            // Validate required fields when auth is enabled.
            if (authEnabledEl.checked) {
              let hasError = false;
              if (!authUsernameEl.value.trim()) {
                authUsernameEl.classList.add('input-missing');
                hasError = true;
              }
              // Require password only for first setup: we cannot know first-setup state reliably here,
              // so we enforce when field is empty and let backend handle update cases.
              if (!authPasswordEl.value.trim()) {
                authPasswordEl.classList.add('input-missing');
              }
              if (hasError) {
                if (authMsgEl) authMsgEl.textContent = 'Bitte fehlende Pflichtfelder ausfüllen.';
                return;
              }
            }

            try {
              const guestExpiresIso = guestExpiresAtEl?.value ? new Date(guestExpiresAtEl.value).toISOString() : null;
              const res = await fetch('/config/auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  enabled: authEnabledEl.checked,
                  username: authUsernameEl.value.trim(),
                  password: authPasswordEl.value,
                  guest_enabled: !!guestEnabledEl?.checked,
                  guest_username: (guestUsernameEl?.value || '').trim(),
                  guest_password: guestPasswordEl?.value || '',
                  guest_expires_at: guestExpiresIso,
                  pushover_app_token: (pushoverAppTokenEl?.value || '').trim(),
                  pushover_user_key: (pushoverUserKeyEl?.value || '').trim(),
                  pushover_device: (pushoverDeviceEl?.value || '').trim(),
                  history_api_enabled: !!historyApiEnabledEl?.checked
                })
              });
              const body = await res.json().catch(() => ({}));
              if (!res.ok) {
                const detail = body?.detail || 'Failed to save access settings.';
                if (String(detail).toLowerCase().includes('username')) authUsernameEl.classList.add('input-missing');
                if (String(detail).toLowerCase().includes('password')) authPasswordEl.classList.add('input-missing');
                if (authMsgEl) authMsgEl.textContent = detail;
                return;
              }
              authPasswordEl.value = '';
              if (guestPasswordEl) guestPasswordEl.value = '';
              const persistedEnabled = !!body?.enabled;
              authEnabledEl.checked = persistedEnabled;
              authUsernameEl.value = body?.username || authUsernameEl.value;
              if (guestEnabledEl) guestEnabledEl.checked = !!body?.guest_enabled;
              if (guestUsernameEl) guestUsernameEl.value = body?.guest_username || guestUsernameEl.value;
              if (guestExpiresAtEl && body?.guest_expires_at) guestExpiresAtEl.value = String(body.guest_expires_at).slice(0,16);
              if (pushoverAppTokenEl) pushoverAppTokenEl.value = body?.pushover_app_token || pushoverAppTokenEl.value;
              if (pushoverUserKeyEl) pushoverUserKeyEl.value = body?.pushover_user_key || pushoverUserKeyEl.value;
              if (pushoverDeviceEl) pushoverDeviceEl.value = body?.pushover_device || pushoverDeviceEl.value;
              if (historyApiEnabledEl && typeof body?.history_api_enabled !== 'undefined') historyApiEnabledEl.checked = !!body.history_api_enabled;
              if (regenRecoveryCodesEl) regenRecoveryCodesEl.checked = false;

              if (auth2faInfoEl) {
                const parts = [];
                if (body?.pending_2fa && (body?.qr_png_url || body?.otpauth_url)) {
                  pending2faToken = body?.verify_token || '';
                  const qr = body?.qr_png_url || `/auth/qr.png?u=${encodeURIComponent(body.otpauth_url)}`;
                  parts.push(`<div style="margin-bottom:8px;"><strong>2FA QR Code</strong><br><img src="${qr}" alt="2FA QR" style="width:180px;height:180px;border-radius:8px;border:1px solid rgba(148,163,184,.3);"/></div>`);
                  if (Array.isArray(body?.recovery_codes) && body.recovery_codes.length) {
                    parts.push(`<div><strong>Recovery Codes</strong><br><code style="white-space:pre-wrap;word-break:break-word;">${body.recovery_codes.join('\\n')}</code></div>`);
                  }
                  parts.push(`<div style="margin-top:8px;"><input id="verify2faCode" placeholder="2FA Code aus App" style="padding:8px 10px; border-radius:8px; width:220px;" /> <button id="verify2faBtn" style="margin-top:8px;">2FA verifizieren</button></div>`);
                  auth2faInfoEl.innerHTML = parts.join('');
                  document.getElementById('verify2faBtn')?.addEventListener('click', async () => {
                    const code = (document.getElementById('verify2faCode')?.value || '').trim();
                    const vr = await fetch('/config/auth/2fa/verify', {
                      method:'POST', headers:{'Content-Type':'application/json'},
                      body: JSON.stringify({ token: pending2faToken, code })
                    });
                    const vb = await vr.json().catch(() => ({}));
                    if (!vr.ok) { if (authMsgEl) authMsgEl.textContent = vb?.detail || '2FA verify failed'; return; }
                    if (authMsgEl) authMsgEl.textContent = '2FA verified and enabled.';
                    await loadAuthConfigUi();
                  });
                } else {
                  auth2faInfoEl.innerHTML = '';
                }
              }

              if (body?.pending_2fa) {
                if (authMsgEl) authMsgEl.textContent = 'Scan QR, then enter app code to verify 2FA.';
                return;
              }

              if (persistedEnabled) {
                if (authMsgEl) authMsgEl.textContent = 'Saved. Authentication enabled. Reloading...';
                setTimeout(() => { window.top.location.href = '/app?page=setup'; }, 250);
                return;
              }

              if (authMsgEl) authMsgEl.textContent = `Saved. Authentication ${persistedEnabled ? 'enabled' : 'disabled'}. Password ${body?.has_password ? 'set' : 'not set'}.`;
            } catch {
              if (authMsgEl) authMsgEl.textContent = 'Failed to save access settings.';
            }
          });

          document.getElementById('addTentBtn')?.addEventListener('click', async () => {
            const tentMsg = document.getElementById('tentMsg');
            const btn = document.getElementById('addTentBtn');
            const editId = Number(btn.getAttribute('data-edit-id') || '0');
            const name = (document.getElementById('tentName')?.value || '').trim();
            const source_url = (document.getElementById('tentUrl')?.value || '').trim();
            const rtsp_url = (document.getElementById('tentRtsp')?.value || '').trim();
            const shelly_main_user = (document.getElementById('tentMainUser')?.value || '').trim();
            const shelly_main_password = (document.getElementById('tentMainPass')?.value || '').trim();

            if (!name || !source_url) {
              tentMsg.textContent = 'Please provide name and source URL.';
              return;
            }

            try {
              const url = editId > 0 ? `/tents/${editId}` : '/tents';
              const method = editId > 0 ? 'PUT' : 'POST';

              const res = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, source_url, rtsp_url, shelly_main_user, shelly_main_password })
              });

              if (!res.ok) {
                const err = await res.text();
                tentMsg.textContent = (editId > 0 ? 'Update failed: ' : 'Add failed: ') + err;
                return;
              }

              tentMsg.textContent = editId > 0 ? 'Tent updated.' : 'Tent added.';
              document.getElementById('tentName').value = '';
              document.getElementById('tentUrl').value = '';
              document.getElementById('tentRtsp').value = '';
              document.getElementById('tentMainUser').value = '';
              document.getElementById('tentMainPass').value = '';
              btn.removeAttribute('data-edit-id');
              btn.textContent = 'Add tent';
              await loadTents();
            } catch (e) {
              tentMsg.textContent = editId > 0 ? 'Update failed.' : 'Add failed.';
            }
          });

          async function loadSetupNavTents(){
            const nav = document.getElementById('tentNavSetup');
            if (!nav) return;
            try {
              const res = await fetch('/tents', { cache: 'no-store' });
              const tents = await res.json();
              if (!Array.isArray(tents) || tents.length === 0) {
                nav.innerHTML = '';
                return;
              }

              const enriched = await Promise.all(tents.map(async (t) => {
                try {
                  const lr = await fetch(`/tents/${t.id}/latest`, { cache: 'no-store' });
                  if (!lr.ok) return { ...t, navName: t.name };
                  const lj = await lr.json();
                  const boxName = (lj?.latest?.['settings.ui.boxName'] || '').toString().trim();
                  return { ...t, navName: boxName || t.name };
                } catch {
                  return { ...t, navName: t.name };
                }
              }));

              nav.innerHTML = enriched
                .map(t => `<a class="navlink" href="/app?page=dashboard&tent=${t.id}">${t.navName}</a>`)
                .join('');
            } catch (e) {
              nav.innerHTML = '';
            }
          }

          loadTents();
          loadSetupNavTents();
          loadAuthConfigUi();
        </script>
      </body>
    </html>
    """


@app.get("/download/project.zip")
def download_project_zip():
    project_root = PROJECT_ROOT
    out_path = os.path.join(tempfile.gettempdir(), "growtent-backend-poc.zip")

    skip_dirs = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
    skip_suffixes = {".pyc", ".pyo", ".log"}

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_root):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for name in files:
                if any(name.endswith(sfx) for sfx in skip_suffixes):
                    continue
                full = os.path.join(root, name)
                rel = os.path.relpath(full, project_root)
                zf.write(full, rel)

    return FileResponse(out_path, media_type="application/zip", filename="growtent-backend-poc.zip")


@app.get("/changelog", response_class=HTMLResponse)
def changelog_page():
    changelog_candidates = [
        os.path.join(PROJECT_ROOT, "CHANGELOG.md"),
        "/app/CHANGELOG.md",
    ]
    content = ""
    for changelog_path in changelog_candidates:
        try:
            with open(changelog_path, "r", encoding="utf-8") as f:
                content = (f.read() or "").strip()
            if content:
                break
        except Exception:
            continue

    if not content:
        content = (
            "# Changelog\n\n"
            "No local changelog file found in this deployment.\n\n"
            "- GitHub: https://github.com/syschelle/growtent-backend\n"
            "- Releases/Tags: https://github.com/syschelle/growtent-backend/tags\n"
        )

    def esc(x: str) -> str:
        return x.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = content.splitlines()
    cards = []
    current_title = ""
    current_body = []
    in_ul = False

    def add_line(html: str):
        nonlocal current_body
        current_body.append(html)

    def close_ul():
        nonlocal in_ul
        if in_ul:
            add_line("</ul>")
            in_ul = False

    def flush_card():
        nonlocal current_title, current_body
        close_ul()
        if current_title or current_body:
            title_html = f"<h2>{esc(current_title)}</h2>" if current_title else ""
            cards.append(f"<section class='entry-card'>{title_html}{''.join(current_body)}</section>")
        current_title = ""
        current_body = []

    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            close_ul()
            continue

        if line.startswith("# "):
            # title handled separately at page header
            continue

        if line.startswith("## "):
            flush_card()
            current_title = line[3:]
            continue

        if line.startswith("### "):
            close_ul()
            t = line[4:]
            cls = ""
            tl = t.lower()
            if "frage" in tl:
                cls = "section-question"
            elif "antwort" in tl:
                cls = "section-answer"
            elif "änderung" in tl or "aenderung" in tl or "changes" in tl:
                cls = "section-changes"
            add_line(f"<h3 class='{cls}'>{esc(t)}</h3>")
            continue

        if line.startswith("- "):
            if not in_ul:
                add_line("<ul>")
                in_ul = True
            add_line(f"<li>{esc(line[2:])}</li>")
            continue

        close_ul()
        add_line(f"<p>{esc(line)}</p>")

    flush_card()
    rendered_cards = "\n".join(cards)

    tent_links_html = ""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name FROM tents ORDER BY id")
                rows = cur.fetchall()
                tent_links_html = "".join(
                    [f'<a class="navlink" href="/app?page=dashboard&tent={int(r[0])}">{esc(str(r[1]))}</a>' for r in rows]
                )
    except Exception:
        tent_links_html = ""

    return f"""
    <html>
      <head>
        <title>GrowTent About</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <style>
          :root {{ --bg:#0f172a; --text:#e2e8f0; --card:#1e293b; --muted:#94a3b8; --grid:rgba(148,163,184,.15); }}
          :root[data-theme='light'] {{ --bg:#eef2f5; --text:#0f172a; --card:#f8fafc; --muted:#475569; --grid:rgba(51,65,85,.18); }}
          body {{ font-family: Arial, sans-serif; margin:0; background:var(--bg); color:var(--text); }}
          .layout {{ display:flex; min-height:100vh; }}
          .sidebar {{ width:220px; background:var(--card); border-right:1px solid var(--grid); padding:16px; box-sizing:border-box; display:flex; flex-direction:column; }}
          .content {{ flex:1; padding:1.2rem; }}
          body.embed .layout {{ display:block; min-height:auto; }}
          body.embed .sidebar {{ display:none; }}
          body.embed .content {{ padding:.8rem; }}
          .navlink {{ display:block; padding:8px 10px; margin-bottom:8px; border-radius:8px; color:var(--text); text-decoration:none; }}
          .navlink.active {{ background:rgba(59,130,246,.2); }}
          .download {{ display:inline-block; margin-bottom:12px; }}
          .md-root {{ display:grid; gap:12px; }}
          .entry-card {{ background:var(--card); border:1px solid var(--grid); border-radius:12px; padding:12px; box-shadow:0 2px 10px rgba(0,0,0,.12); }}
          .entry-card h2 {{ font-size:1.12rem; margin:.1rem 0 .5rem; color:#93c5fd; }}
          .entry-card h3 {{ font-size:1rem; margin:.8rem 0 .25rem; }}
          .entry-card p, .entry-card li {{ line-height:1.45; font-size:.95rem; }}
          .entry-card ul {{ margin:.2rem 0 .8rem 1.1rem; padding:0; }}
          .section-question {{ color:#facc15; }}
          .section-answer {{ color:#22d3ee; }}
          .section-changes {{ color:#34d399; }}
          @media (max-width: 1024px) {{
            .layout {{ display:block; }}
            .sidebar {{ width:100%; border-right:none; border-bottom:1px solid var(--grid); }}
          }}
        </style>
      </head>
      <body>
        <script>
          const theme = localStorage.getItem('gt_theme') || 'dark';
          document.documentElement.setAttribute('data-theme', theme === 'light' ? 'light' : 'dark');
          const isEmbed = new URLSearchParams(window.location.search).get('embed') === '1';
          if (isEmbed) document.body.classList.add('embed');
        </script>
        <div class="layout">
          <aside class="sidebar">
            <div style="font-size:.8rem; color:#94a3b8; margin-bottom:10px;">Navigation</div>
            {tent_links_html}
            <a class="navlink" href="/app?page=setup">Setup</a>
            <a class="navlink active" href="/app?page=changelog">About</a>
          </aside>
          <main class="content">
            <h1>About</h1>
            <a class="navlink active download" href="https://github.com/syschelle/growtent-backend" target="_blank" rel="noopener noreferrer">GitHub Repository</a>
            <a class="navlink active download" href="/download/project.zip">Projekt herunterladen (ZIP)</a>
            <div class="md-root">{rendered_cards}</div>
          </main>
        </div>
      </body>
    </html>
    """


@app.get("/app", response_class=HTMLResponse)
def app_shell_page():
    return """
    <html>
      <head>
        <title>CanopyOps</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
        <style>
          :root { --bg:#0f172a; --text:#e2e8f0; --card:#1e293b; --muted:#94a3b8; --grid:rgba(148,163,184,.15); }
          :root[data-theme='light'] { --bg:#eef2f5; --text:#0f172a; --card:#f8fafc; --muted:#475569; --grid:rgba(51,65,85,.18); }
          body { margin:0; font-family:Arial,sans-serif; background:var(--bg); color:var(--text); }
          .shell { display:grid; grid-template-columns:1fr; grid-template-rows:52px 1fr; min-height:100vh; }
          .header { position:relative; grid-column:1; display:flex; align-items:center; justify-content:space-between; padding:0 14px; background:var(--card); border-bottom:1px solid var(--grid); }
          .header-left { display:flex; align-items:center; gap:10px; }
          .menu-btn { display:inline-block; border:1px solid var(--grid); background:transparent; color:var(--text); border-radius:8px; padding:4px 8px; cursor:pointer; font-size:1.25rem; line-height:1; font-weight:700; }
          .sidebar {
            display:none;
            position:fixed;
            top:52px;
            left:0;
            width:min(320px, 92vw);
            height:calc(100vh - 52px);
            overflow:auto;
            padding:14px;
            background:var(--card);
            border-right:1px solid var(--grid);
            box-shadow:0 8px 24px rgba(0,0,0,.25);
            z-index:40;
            flex-direction:column;
          }
          .sidebar.open { display:flex; }
          .content { background:var(--bg); }
          .frame { width:100%; height:calc(100vh - 52px); border:0; display:block; }
          .navlink { display:block; padding:8px 10px; margin-bottom:8px; border-radius:8px; color:var(--text); text-decoration:none; }
          .navlink.active { background:rgba(59,130,246,.2); }
          .muted { color:var(--muted); font-size:.84rem; margin-bottom:10px; }
          .header-btn { border:1px solid var(--grid); background:linear-gradient(180deg, rgba(59,130,246,.28), rgba(37,99,235,.22)); color:var(--text); border-radius:10px; padding:4px 8px; cursor:pointer; box-shadow:0 2px 10px rgba(2,6,23,.22); }
          .guest-badge-center { position:absolute; left:50%; top:50%; transform:translate(-50%, -50%); padding:4px 10px; border-radius:999px; border:1px solid rgba(239,68,68,.55); background:rgba(220,38,38,.22); color:#fecaca; font-size:.82rem; font-weight:700; white-space:nowrap; }
          @media (max-width:1024px){
            .sidebar{
              width:100%;
              max-height:55vh;
              height:auto;
              border-right:none;
              border-bottom:1px solid var(--grid);
            }
          }
        </style>
      </head>
      <body>
        <script>
          const theme = localStorage.getItem('gt_theme') || 'dark';
          document.documentElement.setAttribute('data-theme', theme === 'light' ? 'light' : 'dark');
        </script>
        <div class="shell">
          <header class="header">
            <div class="header-left"><button class="menu-btn" id="menuBtn">☰</button><strong style="display:flex; align-items:center; gap:8px;"><img src="/favicon.svg" alt="CanopyOps" style="width:18px; height:18px;" />CanopyOps</strong></div>
            <span id="guestModeBadge" class="guest-badge-center" style="display:none;">Gastmodus aktiv</span>
            <div style="display:flex; align-items:center; gap:10px;">
              <button class="header-btn" id="shellViewModeBtn">Mobile Ansicht</button>
              <button class="header-btn" id="logoutBtn">Logout</button>
              <div class="muted" style="margin:0;">__APP_VERSION__</div>
            </div>
          </header>
          <aside class="sidebar">
            <div class="muted" id="navTitle">Navigation</div>
            <div id="tentNav"></div>
            <a class="navlink" data-page="setup" href="/app?page=setup">Setup</a>
            <a class="navlink" data-page="changelog" href="/app?page=changelog">About</a>
          </aside>
          <main class="content">
            <iframe id="contentFrame" class="frame" src="/dashboard?embed=1"></iframe>
          </main>
        </div>
        <script>
          const frame = document.getElementById('contentFrame');
          const sideNav = document.querySelector('.sidebar');
          const menuBtn = document.getElementById('menuBtn');
          const viewBtn = document.getElementById('shellViewModeBtn');
          const qp = new URLSearchParams(window.location.search);
          let page = (qp.get('page') || 'dashboard');
          const tent = qp.get('tent');
          let userRole = 'admin';

          function getLang(){ return (localStorage.getItem('gt_lang') || 'de') === 'de' ? 'de' : 'en'; }
          function updateViewBtnLabel(){
            if (!viewBtn) return;
            const mode = localStorage.getItem('gt_view_mode') || 'auto';
            const de = getLang() === 'de';
            viewBtn.textContent = mode === 'mobile'
              ? (de ? 'Desktop Ansicht' : 'Desktop view')
              : (de ? 'Mobile Ansicht' : 'Mobile view');
            const gb = document.getElementById('guestModeBadge');
            if (gb) gb.textContent = de ? 'Gastmodus aktiv' : 'Guest mode active';
          }

          function updateActive(){
            document.querySelectorAll('.sidebar .navlink[data-page]').forEach(a => {
              a.classList.toggle('active', a.dataset.page === page);
            });
          }

          function setFrame(){
            let src = '/dashboard?embed=1';
            if (userRole === 'guest' && page === 'setup') page = 'dashboard';
            if (page === 'setup') src = '/setup?embed=1';
            else if (page === 'changelog') src = '/changelog?embed=1';
            else if (tent) src = `/dashboard?embed=1&tent=${encodeURIComponent(tent)}`;
            if (frame.getAttribute('src') !== src) frame.setAttribute('src', src);
            updateActive();
            if (window.matchMedia('(max-width:1024px)').matches) sideNav?.classList.remove('open');
          }

          async function loadTentNav(){
            const nav = document.getElementById('tentNav');
            try {
              const res = await fetch('/tents', { cache:'no-store' });
              const tents = await res.json();
              if (!Array.isArray(tents) || tents.length === 0){ nav.innerHTML=''; return; }
              nav.innerHTML = tents.map(t => `<a class="navlink" href="/app?page=dashboard&tent=${t.id}">${t.name}</a>`).join('');
            } catch { nav.innerHTML=''; }
          }

          window.addEventListener('popstate', () => {
            const q = new URLSearchParams(window.location.search);
            page = (q.get('page') || 'dashboard');
            setFrame();
          });

          document.getElementById('logoutBtn')?.addEventListener('click', async () => {
            try { await fetch('/auth/logout', { method:'POST' }); } catch {}
            window.location.href = '/auth/login';
          });

          // CSV export moved to tent window (dashboard title actions).

          menuBtn?.addEventListener('click', () => {
            sideNav?.classList.toggle('open');
          });

          viewBtn?.addEventListener('click', () => {
            const cur = localStorage.getItem('gt_view_mode') || 'auto';
            const next = cur === 'mobile' ? 'desktop' : 'mobile';
            localStorage.setItem('gt_view_mode', next);
            updateViewBtnLabel();
            try { frame.contentWindow?.location.reload(); } catch { frame.setAttribute('src', frame.getAttribute('src') || '/dashboard?embed=1'); }
          });

          (async () => {
            try {
              const r = await fetch('/auth/whoami', { cache:'no-store' });
              const j = await r.json().catch(() => ({}));
              userRole = j?.role || 'admin';
              const guestBadge = document.getElementById('guestModeBadge');
              if (userRole === 'guest') {
                if (guestBadge) guestBadge.style.display = 'inline-block';
                const setupLink = document.querySelector('.sidebar .navlink[data-page="setup"], .sidebar a[href="/app?page=setup"]');
                if (setupLink) setupLink.style.display = 'none';
                if (page === 'setup') page = 'dashboard';
              } else {
                if (guestBadge) guestBadge.style.display = 'none';
              }
            } catch {}
            loadTentNav();
            updateViewBtnLabel();
            setFrame();
          })();
        </script>
      </body>
    </html>
    """.replace("__APP_VERSION__", APP_VERSION)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request):
    if request.query_params.get("embed") != "1":
        return RedirectResponse(url="/app?page=dashboard", status_code=302)
    return """
    <html>
      <head>
        <title>GrowTent Dashboard</title>
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <script src=\"/static/chart.umd.js\"></script>
        <style>
          :root {
            --bg:#0f172a;
            --text:#e2e8f0;
            --card:#1e293b;
            --muted:#94a3b8;
            --small:#cbd5e1;
            --grid:rgba(148,163,184,.15);
          }
          :root[data-theme='light'] {
            --bg:#eef2f5;
            --text:#0f172a;
            --card:#f8fafc;
            --muted:#475569;
            --small:#334155;
            --grid:rgba(51,65,85,.18);
          }
          body { font-family: Arial, sans-serif; margin: 0; background:var(--bg); color:var(--text); }
          .layout { display:flex; min-height:100vh; }
          .sidebar { width:220px; background:var(--card); border-right:1px solid var(--grid); padding:16px; box-sizing:border-box; display:flex; flex-direction:column; }
          .content { flex:1; padding:1.2rem; }
          body.embed .layout { display:block; min-height:auto; }
          body.embed .sidebar { display:none; }
          body.embed .content { padding:.8rem; }
          .navlink { display:block; padding:8px 10px; margin-bottom:8px; border-radius:8px; color:var(--text); text-decoration:none; background:transparent; }
          .navlink.active { background:rgba(59,130,246,.2); }
          .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 12px; }
          #tankCurrentCard { position:relative; }
          .card { background:var(--card); border-radius:10px; padding:12px; box-shadow: 0 2px 8px rgba(0,0,0,.15); margin-bottom:12px; }
          .stream-card { width: min(100%, 500px); max-width: 500px; }
          .phase-card { display:flex; flex-direction:column; justify-content:space-between; min-height:280px; }
          .phase-title { font-size:.85rem; color:var(--muted); margin-bottom:6px; }
          .phase-main { font-size:2rem; font-weight:800; line-height:1.1; margin-bottom:10px; }
          .phase-veg { color:#22c55e; }
          .phase-flower { color:#ef4444; }
          .phase-dry { color:#9ca3af; }
          .phase-stats { display:grid; grid-template-columns:1fr; gap:10px; margin-bottom:12px; }
          .phase-chip { background:rgba(148,163,184,.12); border:1px solid var(--grid); border-radius:10px; padding:10px 12px; font-size:1.08rem; font-weight:600; line-height:1.25; }
          .phase-cost-label { font-size:.85rem; color:var(--muted); margin-top:8px; }
          .phase-cost { font-size:2rem; font-weight:800; line-height:1.1; }
          .card-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:4px; }
          .status-badge { padding:2px 8px; border-radius:999px; font-size:.75rem; font-weight:700; }
          .stream-open-btn { display:inline-block; padding:6px 9px; border-radius:10px; border:1px solid var(--grid); background:linear-gradient(180deg, rgba(59,130,246,.28), rgba(37,99,235,.22)); color:var(--text); text-decoration:none; font-size:.82rem; font-weight:800; box-shadow:0 2px 10px rgba(2,6,23,.22); transition:transform .08s ease, box-shadow .15s ease, filter .15s ease; }
          #espOpenBtn, #espStatsBtn { font-weight:400; }
          .mobile-nav-toggle { display:none; }
          .title-row { display:flex; align-items:center; justify-content:space-between; gap:10px; }
          .title-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; justify-content:flex-end; }
          .stream-open-btn:hover { filter:brightness(1.06); box-shadow:0 4px 14px rgba(2,6,23,.28); }
          .stream-open-btn:active { transform:translateY(1px) scale(.99); }
          button { padding:7px 11px; border-radius:9px; border:1px solid rgba(14,165,233,.45); background:linear-gradient(180deg, rgba(14,165,233,.22), rgba(2,132,199,.18)); color:var(--text); font-size:.8rem; font-weight:700; box-shadow:0 2px 8px rgba(2,6,23,.2); transition:transform .08s ease, box-shadow .15s ease, filter .15s ease; cursor:pointer; }
          body.role-pending button:not(#viewModeBtn):not(#mobileNavToggle),
          body.role-guest button:not(#viewModeBtn):not(#mobileNavToggle) {
            pointer-events:none; opacity:.55; cursor:not-allowed;
          }
          body.role-pending #espOpenBtn, body.role-pending #espStatsBtn, body.role-pending #streamOpenBtn,
          body.role-guest #espOpenBtn, body.role-guest #espStatsBtn, body.role-guest #streamOpenBtn,
          body.role-pending .shelly-open-btn, body.role-guest .shelly-open-btn {
            pointer-events:none; opacity:.55; cursor:not-allowed;
          }
          button:hover { filter:brightness(1.06); box-shadow:0 4px 12px rgba(2,6,23,.26); }
          button:active { transform:translateY(1px) scale(.99); }
          .shelly-open-btn { display:inline-block; padding:7px 11px; border-radius:9px; border:1px solid rgba(14,165,233,.45); background:linear-gradient(180deg, rgba(14,165,233,.22), rgba(2,132,199,.18)); color:var(--text); text-decoration:none; font-size:.8rem; font-weight:700; box-shadow:0 2px 8px rgba(2,6,23,.2); transition:transform .08s ease, box-shadow .15s ease, filter .15s ease; }
          .shelly-open-btn:hover { filter:brightness(1.06); box-shadow:0 4px 12px rgba(2,6,23,.26); }
          .shelly-open-btn:active { transform:translateY(1px) scale(.99); }
          .shelly-actions { display:flex; justify-content:space-between; align-items:center; gap:8px; margin-top:auto; padding-top:10px; }
          .status-on { background:#14532d; color:#bbf7d0; }
          .status-off { background:#7f1d1d; color:#fecaca; }
          .shelly-card-on { border:1px solid #16a34a; background:rgba(22,163,74,.18); }
          .shelly-card-off { border:1px solid #dc2626; background:rgba(220,38,38,.14); }
          #shellyDevices { display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:12px; }
          #shellyDevices .card { min-width:0; display:flex; flex-direction:column; }
          #shellyDevices .small { word-break:break-word; }
          .label { font-size:.8rem; color:var(--muted); }
          .value { font-size:1.4rem; font-weight:700; margin-top:4px; }
          .small { font-size:.85rem; color:var(--small); }
          h1 { margin-top:0; }
          .row { display:flex; gap:8px; flex-wrap:wrap; }
          .top-cards { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; margin-bottom:12px; align-items:stretch; }
          .top-cards > .card { min-width:0; overflow:hidden; box-sizing:border-box; margin-bottom:0; min-height:clamp(280px, 30vw, 420px); }
          .top-cards .stream-card { width:100%; max-width:none; }
          .meta-card { width:100%; max-width:none; }
          .phase-card { min-height:0; height:auto; }
          #streamCard { display:flex; flex-direction:column; }
          #streamFrame { width:100%; max-width:100%; display:block; height:auto !important; aspect-ratio:16/9; }
          @media (max-width: 1400px){
            .top-cards { grid-template-columns: repeat(2, minmax(0,1fr)); }
          }

          @media (max-width: 1024px){
            .layout { display:block; }
            .sidebar {
              width:100%;
              border-right:none;
              border-bottom:1px solid var(--grid);
              padding:8px;
              max-height:52px;
              overflow:hidden;
              white-space:normal;
              transition:max-height .2s ease;
            }
            .sidebar.expanded { max-height:280px; overflow:auto; }
            .mobile-nav-toggle { display:inline-block; width:auto; padding:4px 8px; }
            .sidebar .navlink { display:block; margin:6px 0 0 0; }
            .content { padding:0.8rem; }
            .top-cards { grid-template-columns: 1fr; }
            .grid { grid-template-columns: repeat(2, minmax(0,1fr)); }
            #shellyDevices { grid-template-columns: repeat(2, minmax(0,1fr)); }
            #exportCsvBtn, #espOpenBtn, #espStatsBtn { display:none !important; }
          }

          @media (max-width: 640px){
            h1 { font-size:1.2rem; }
            .card { padding:10px; border-radius:9px; }
            .phase-main { font-size:1.6rem; }
            .phase-chip { font-size:.95rem; padding:8px 10px; }
            .value { font-size:1.15rem; }
            .grid { grid-template-columns: 1fr; }
            #shellyDevices { grid-template-columns: 1fr; }
            .row { gap:6px; }
            button, .stream-open-btn { width:100%; text-align:center; }
          }

          body.force-mobile .layout { display:block; }
          body.force-mobile .sidebar { width:100%; border-right:none; border-bottom:1px solid var(--grid); padding:8px; max-height:52px; overflow:hidden; white-space:normal; transition:max-height .2s ease; }
          body.force-mobile .sidebar.expanded { max-height:280px; overflow:auto; }
          body.force-mobile .mobile-nav-toggle { display:inline-block; width:auto; padding:4px 8px; }
          body.force-mobile .sidebar .navlink { display:block; margin:6px 0 0 0; }
          body.force-mobile .content { padding:0.8rem; }
          body.force-mobile .top-cards { grid-template-columns: 1fr; }
          body.force-mobile .grid { grid-template-columns: 1fr; }
          body.force-mobile #shellyDevices { grid-template-columns: 1fr; }

          button {
            border:1px solid var(--grid);
            background:linear-gradient(180deg, rgba(59,130,246,.28), rgba(37,99,235,.22));
            color:var(--text);
            font-weight:700;
            border-radius:10px;
            padding:6px 9px;
            cursor:pointer;
            transition:transform .08s ease, box-shadow .15s ease, filter .15s ease;
            box-shadow:0 2px 10px rgba(2,6,23,.22);
          }
          button:hover { filter:brightness(1.06); box-shadow:0 4px 14px rgba(2,6,23,.28); }
          button:active { transform:translateY(1px) scale(.99); }
          .relay {
            padding:8px 10px;
            border-radius:10px;
            font-size:.86rem;
            border:1px solid var(--grid);
            color:var(--text);
            font-weight:700;
            cursor:pointer;
            transition:transform .08s ease, box-shadow .15s ease, filter .15s ease;
            box-shadow:0 2px 10px rgba(2,6,23,.22);
            background:linear-gradient(180deg, rgba(239,68,68,.35), rgba(220,38,38,.28));
          }
          .relay:hover { filter:brightness(1.06); box-shadow:0 4px 14px rgba(2,6,23,.28); }
          .relay:active { transform:translateY(1px) scale(.99); }
          .on { background:linear-gradient(180deg, rgba(34,197,94,.35), rgba(22,163,74,.28)); color:var(--text); }
          .off { background:linear-gradient(180deg, rgba(239,68,68,.35), rgba(220,38,38,.28)); color:var(--text); }
          .status-online { color:#22c55e; font-weight:700; }
          .status-offline { color:#ef4444; font-weight:700; }
          .alpha-led { width:10px; height:10px; border-radius:50%; display:inline-block; margin-left:6px; box-shadow:0 0 6px rgba(0,0,0,.35) inset, 0 0 5px rgba(255,255,255,.15); vertical-align:middle; }
          .alpha-led-green { background:#22c55e; }
          .alpha-led-yellow { background:#facc15; }
          .alpha-led-red { background:#ef4444; }
          .alpha-led-off { background:#64748b; opacity:.55; }
          .status-meta { color:var(--muted); font-size:.92rem; font-weight:500; margin-left:8px; }
          /* Current value colors aligned with history line colors */
          #temp { color:#22d3ee; }
          #hum { color:#a78bfa; }
          #vpd { color:#f59e0b; }
          #extTemp { color:#10b981; }
          /* gauges removed */
          canvas { width:100%; max-height:320px; }
          .history-card { position:relative; }
          .history-overlay {
            position:absolute; inset:0; display:none;
            align-items:center; justify-content:center;
            pointer-events:none; text-align:center; padding:16px;
            color:#ef4444; font-weight:700; font-size:1rem;
          }
          .range-hint-error { color:#ef4444; font-weight:400; }
        </style>
      </head>
      <body>
        <div class=\"layout\">
          <aside class=\"sidebar\" id=\"sideNav\">
            <button id=\"mobileNavToggle\" type=\"button\" class=\"mobile-nav-toggle\">Menü</button>
            <div class=\"label\" style=\"margin-bottom:10px;\" id=\"navTitle\">Navigation</div>
            <div id=\"tentNav\"></div>
            <a class=\"navlink\" href=\"/app?page=setup\" id=\"navSetup\">Setup</a>
            <a class=\"navlink\" href=\"/app?page=changelog\" id=\"navChangelog\">About</a>
          </aside>
          <main class=\"content\">
        <div class=\"title-row\">
          <h1 id=\"titleMain\">GrowTent Dashboard</h1>
          <div class=\"title-actions\">
            <span id=\"uptimeBadge\" class=\"small\" style=\"display:none;\">-</span>
            <button id=\"exportCsvBtn\" type=\"button\">Export CSV</button>
            <a id=\"espOpenBtn\" class=\"stream-open-btn\" href=\"#\" target=\"_blank\" rel=\"noopener noreferrer\" style=\"display:none;\">Open ESP</a>
            <a id=\"espStatsBtn\" class=\"stream-open-btn\" href=\"#\" target=\"_blank\" rel=\"noopener noreferrer\" style=\"display:none;\">Open stats</a>
          </div>
        </div>
        <div class=\"small\" id=\"sourceText\">Source: -</div>
        <!-- language moved to setup -->
        <!-- temperature unit moved to setup -->
        <div id=\"status\" class=\"small\">Loading…</div>

        <div class=\"top-cards\">
          <div class=\"card stream-card\" id=\"streamCard\" style=\"margin-bottom:0;\">
            <div class=\"card-head\">
              <div class=\"label\" id=\"lblStream\">Camera Stream</div>
              <a id=\"streamOpenBtn\" class=\"stream-open-btn\" href=\"#\" target=\"_blank\" rel=\"noopener\" style=\"display:none;\">Open Player</a>
            </div>
            <div class=\"small\" id=\"streamInfo\">No RTSP configured for this tent.</div>
            <img id=\"streamPreview\" alt=\"Stream preview\" style=\"width:100%; height:280px; border:0; margin-top:8px; display:none; border-radius:8px; object-fit:cover; background:#000;\" />
            <iframe id=\"streamFrame\" style=\"width:100%; height:280px; border:0; margin-top:8px; display:none;\" allow=\"autoplay; fullscreen\"></iframe>
          </div>

          <div class=\"card stream-card meta-card phase-card\" style=\"margin-bottom:0;\">
            <div>
              <div class=\"phase-title\" id=\"lblGrowPhase\">Grow Phase</div>
              <div class=\"phase-main\" id=\"growPhaseValue\">-</div>
              <div class=\"phase-stats\">
                <div class=\"phase-chip\" id=\"growTotals\">-</div>
                <div class=\"phase-chip\" id=\"growPhaseStats\">-</div>
              </div>
            </div>
            <div>
              <div class=\"phase-cost-label\" id=\"lblMainEnergy\">Energie</div>
              <div class=\"phase-chip\" id=\"mainEnergyValue\">-</div>
              <div class=\"phase-cost-label\" id=\"lblMainKwhToday\">Verbrauch heute (0-24)</div>
              <div class=\"phase-chip\" id=\"mainKwhTodayValue\">-</div>
              <div class=\"phase-cost-label\" id=\"lblMainCost\">Gesamtkosten</div>
              <div class=\"phase-chip\" id=\"mainCostValue\">-</div>
              <div class=\"row\" id=\"phaseActions\" style=\"margin-top:10px;\"></div>
            </div>
          </div>

          <div class=\"card stream-card meta-card phase-card\" id=\"irrigationCard\" style=\"margin-bottom:0; display:none;\">
            <div>
              <div class=\"phase-title\" id=\"lblIrrigationCardWrap\"><span id=\"lblIrrigationCard\">Bewässerung</span> <span id=\"irActiveBadge\" style=\"display:none; color:#ef4444; font-weight:700;\">aktiv</span></div>
              <div class=\"phase-stats\">
                <div class=\"phase-chip\" id=\"irNextRun\">Next irrigation: -</div>
                <div class=\"phase-chip\" id=\"irRunsLeft\">Runs left: -</div>
                <div class=\"phase-chip\" id=\"irTimeLine\">Time left: - · End time: -</div>
                <div class=\"phase-chip\" id=\"irAmount\">Amount: -</div>
                <div class=\"phase-chip\" id=\"irTimePerTask\">Time/task: -</div>
                <div class=\"phase-chip\" id=\"irBetweenTasks\">Between tasks: -</div>
                <div class=\"phase-chip\" id=\"irAmountTotal\">Amount total: -</div>
              </div>
              <div class=\"row\" id=\"irrigationCardActions\" style=\"margin-top:10px;\"></div>
            </div>
          </div>
        </div>

        <div class=\"grid\" id=\"currentValuesGrid\">
          <div class=\"card\">
            <div class=\"card-head\">
              <div class=\"label\"><span>🌡️</span> <span id=\"lblTemp\">Temperature</span><span id=\"tempAlphaLed\" class=\"alpha-led alpha-led-off\"></span></div>
              <div class=\"small\" id=\"tempLastChange\">Last change: -</div>
            </div>
            <div class=\"value\" id=\"temp\">-</div>
            <div class=\"small\" id=\"tempRaw\">Raw: -</div>
            <div class=\"small\" id=\"tempTarget\">Target: -</div>
            <!-- gauge removed -->
          </div>
          <div class=\"card\"><div class=\"card-head\"><div class=\"label\"><span>💧</span> <span id=\"lblHum\">Humidity</span><span id=\"humAlphaLed\" class=\"alpha-led alpha-led-off\"></span></div><div class=\"small\" id=\"humLastChange\">Last change: -</div></div><div class=\"value\" id=\"hum\">-</div><div class=\"small\" id=\"humRaw\">Raw: -</div><!-- gauge removed --></div>
          <div class=\"card\">
            <div class=\"card-head\">
              <div class=\"label\"><span>🫧</span> <span id=\"lblVpd\">VPD</span></div>
              <div class=\"small\" id=\"vpdLastChange\">Last change: -</div>
            </div>
            <div class=\"value\" id=\"vpd\">-</div>
            <div class=\"small\" id=\"vpdTarget\">Target: -</div>
            <!-- gauge removed -->
          </div>
          <div class=\"card\">
            <div class=\"card-head\">
              <div class=\"label\"><span>🌡️</span> <span id=\"lblExtTemp\">DS18B20</span></div>
              <div class=\"small\" id=\"extTempLastChange\">Last change: -</div>
            </div>
            <div class=\"value\" id=\"extTemp\">-</div>
          </div>
          <div class=\"card\" id=\"tankCurrentCard\" style=\"display:none;\">
            <div class=\"card-head\">
              <div class=\"label\"><span>🛢️</span> <span id=\"lblTankLevel\">Tank level</span></div>
              <div class=\"small\" id=\"tankLastChange\">Last change: -</div>
            </div>
            <div class=\"value\" id=\"tankPercent\">- %</div>
            <div class=\"small\" id=\"tankLevelSub\" style=\"position:absolute; left:12px; bottom:12px;\">Distance: - cm</div>
            <div class=\"row\" id=\"tankCurrentActions\" style=\"position:absolute; right:12px; bottom:8px; margin-top:0;\"></div>
          </div>
          <!-- main power tile removed (covered by Main Switch tile) -->
        </div>

        <div class=\"card\">
          <div class=\"label\" id=\"lblRelays\">Relays</div>
          <div class=\"row\" id=\"relays\"></div>
        </div>

        <div class=\"card\" id=\"relaysExtraCard\" style=\"display:none;\">
          <div class=\"label\" id=\"lblRelaysExtra\">Irrigation relays 6-8</div>
          <div class=\"row\" id=\"relaysExtra\"></div>
        </div>

        <div class=\"card\">
          <div class=\"label\" id=\"lblShelly\">Shelly Devices</div>
          <div id=\"shellyDevices\" class=\"grid\"></div>
        </div>

        <div class=\"small\" style=\"margin:4px 0 8px 0; display:flex; align-items:center; gap:8px; flex-wrap:wrap;\">
          <span id=\"rangeLabelLive\">Range for history:</span>
          <select id=\"rangeSelectLive\" style=\"padding:4px 8px; border-radius:8px;\">
            <option value=\"60\">1h</option>
            <option value=\"1440\">24h</option>
            <option value=\"2880\">48h</option>
          </select>
          <span id=\"rangeHintLive\"></span>
        </div>

        <div class=\"card history-card\">
          <div class=\"label\" id=\"lblTempHistory\">Temperature History</div>
          <canvas id=\"tempChart\"></canvas>
          <div id=\"historyOverlayTemp\" class=\"history-overlay\"></div>
        </div>

        <div class=\"card history-card\">
          <div class=\"label\" id=\"lblHumHistory\">Humidity History</div>
          <canvas id=\"humChart\"></canvas>
          <div id=\"historyOverlayHum\" class=\"history-overlay\"></div>
        </div>

        <div class=\"card history-card\">
          <div class=\"label\" id=\"lblVpdHistory\">VPD History</div>
          <canvas id=\"vpdChart\"></canvas>
          <div id=\"historyOverlayVpd\" class=\"history-overlay\"></div>
        </div>

        <div class=\"card history-card\">
          <div class=\"label\" id=\"lblExtTempHistory\">DS18B20 History</div>
          <canvas id=\"extTempChart\"></canvas>
          <div id=\"historyOverlayExtTemp\" class=\"history-overlay\"></div>
        </div>

        <div class=\"card history-card\">
          <div class=\"label\" id=\"lblAlphaHistory\"><span id=\"lblAlphaHistoryText\">Alpha History</span> <span id=\"alphaHistoryHint\" style=\"cursor:help; opacity:.9;\" aria-label=\"hint\" title=\"\">ℹ️</span></div>
          <canvas id=\"alphaChart\"></canvas>
          <div id=\"historyOverlayAlpha\" class=\"history-overlay\"></div>
        </div>

        <div class=\"card history-card\">
          <div class=\"label\" id=\"lblMainWHistory\">Total consumption</div>
          <canvas id=\"mainWChart\"></canvas>
          <div id=\"historyOverlayMainW\" class=\"history-overlay\"></div>
        </div>

        <div id=\"dbIrPlanModal\" style=\"display:none; position:fixed; inset:0; background:rgba(2,6,23,.65); z-index:1200; align-items:center; justify-content:center; padding:16px;\">
          <div class=\"card\" style=\"max-width:520px; width:100%; margin-bottom:0;\">
            <div style=\"display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:10px;\">
              <strong id=\"dbIrPlanTitle\">Irrigation plan</strong>
              <button type=\"button\" id=\"dbIrPlanCloseBtn\">✕</button>
            </div>
            <div id=\"dbIrPlanTentLabel\" class=\"small\" style=\"margin-bottom:10px;\">-</div>
            <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:10px;\">
              <input type=\"checkbox\" id=\"dbIrPlanEnabled\" />
              <span id=\"dbIrPlanEnabledLabel\">Active</span>
            </label>
            <div id=\"dbIrPlanEveryDaysLabel\" style=\"margin-bottom:6px;\">Every N days</div>
            <input id=\"dbIrPlanEveryDays\" type=\"number\" min=\"1\" step=\"1\" style=\"padding:8px 10px; border-radius:8px; width:160px; margin-bottom:10px;\" />
            <div id=\"dbIrPlanOffsetLabel\" style=\"margin-bottom:6px;\">Minutes after light on</div>
            <input id=\"dbIrPlanOffset\" type=\"number\" min=\"0\" step=\"1\" style=\"padding:8px 10px; border-radius:8px; width:160px; margin-bottom:10px;\" />
            <div style=\"display:flex; gap:8px; flex-wrap:wrap;\">
              <button type=\"button\" id=\"dbIrPlanSaveBtn\">Save plan</button>
              <button type=\"button\" id=\"dbIrPlanCancelBtn\">Cancel</button>
            </div>
            <div id=\"dbIrPlanMsg\" style=\"margin-top:10px;\"></div>
          </div>
        </div>

        <div id=\"dbExhPlanModal\" style=\"display:none; position:fixed; inset:0; background:rgba(2,6,23,.65); z-index:1200; align-items:center; justify-content:center; padding:16px;\">
          <div class=\"card\" style=\"max-width:520px; width:100%; margin-bottom:0;\">
            <div style=\"display:flex; justify-content:space-between; align-items:center; gap:10px; margin-bottom:10px;\">
              <strong id=\"dbExhPlanTitle\">Exhaust VPD plan</strong>
              <button type=\"button\" id=\"dbExhPlanCloseBtn\">✕</button>
            </div>
            <div id=\"dbExhPlanTentLabel\" class=\"small\" style=\"margin-bottom:10px;\">-</div>
            <label style=\"display:flex; align-items:center; gap:8px; margin-bottom:10px;\">
              <input type=\"checkbox\" id=\"dbExhPlanEnabled\" />
              <span id=\"dbExhPlanEnabledLabel\">Active</span>
            </label>
            <div id=\"dbExhPlanMinVpdLabel\" style=\"margin-bottom:6px;\">Min VPD (kPa)</div>
            <input id=\"dbExhPlanMinVpd\" type=\"number\" min=\"0.1\" step=\"0.05\" style=\"padding:8px 10px; border-radius:8px; width:160px; margin-bottom:10px;\" />
            <div id=\"dbExhPlanHystLabel\" style=\"margin-bottom:6px;\">Hysteresis (kPa)</div>
            <input id=\"dbExhPlanHyst\" type=\"number\" min=\"0\" step=\"0.01\" style=\"padding:8px 10px; border-radius:8px; width:160px; margin-bottom:10px;\" />
            <div style=\"display:flex; gap:8px; justify-content:flex-end;\">
              <button type=\"button\" id=\"dbExhPlanSaveBtn\">Save plan</button>
              <button type=\"button\" id=\"dbExhPlanCancelBtn\">Cancel</button>
            </div>
            <div id=\"dbExhPlanMsg\" style=\"margin-top:10px;\"></div>
          </div>
        </div>
          </main>
        </div>

        <script>
          const isEmbed = new URLSearchParams(window.location.search).get('embed') === '1';
          if (isEmbed) document.body.classList.add('embed');
          document.body.classList.add('role-pending');

          const I18N = {
            en: {
              title: 'Dashboard',
              openPlayer: 'Open Player',
              openPreview: 'Open fullscreen',
              openEsp: 'Open ESP',
              openEspStats: 'Open stats',
              uptime: 'Uptime',
              uptimeDay: 'd',
              uptimeHour: 'h',
              uptimeMinute: 'min',
              uptimeSecond: 's',
              viewMobile: 'Mobile view',
              viewDesktop: 'Desktop view',
              navOpen: 'Menu',
              navClose: 'Close',
              source: 'Source',
              setup: 'Setup',
              nav: 'Navigation',
              tents: 'Tents',
              language: 'Language:',
              range: 'Range:',
              tempUnit: 'Temperature Unit:',
              temperature: 'Temperature',
              humidity: 'Humidity',
              rawValue: 'Raw',
              vpd: 'VPD',
              extTemp: 'Tank temperature',
              extTempSensor: 'Sensor',
              // mainPower removed
              target: 'Target',
              relays: 'Relays',
              relaysExtra: 'Irrigation relays 6-8',
              shelly: 'Shelly Devices',
              tempHistory: 'Temperature History',
              humHistory: 'Humidity History',
              vpdHistory: 'VPD History',
              alphaHistory: 'Alpha History',
              alphaHint: 'Adaptive alpha of smoothing: lower α = stronger smoothing (slower), higher α = faster reaction (more sensitive). α Temp applies to temperature smoothing, α Hum to humidity smoothing.',
              extTempHistory: 'Tank Temperature History',
              totalConsumption: 'Total consumption',
              totalConsumptionHistory: 'Total consumption history',
              exportCsv: 'Export CSV',
              consumptionToday: 'Consumption / cost today (0-24)',
              tankLevel: 'Tank level',
              tankDistance: 'Distance',
              updated: 'Updated',
              apiOk: 'API: OK',
              online: 'online',
              offline: 'offline',
              lastSuccess: 'Last successful GET',
              lastUpdate: 'Last update',
              relay: 'Relay',
              on: 'ON',
              off: 'OFF',
              loadFailed: 'Load failed',
              noShelly: 'No Shelly devices with configured IP found.',
              cameraStream: 'Camera Stream',
              noRtsp: 'No stream configured for this tent.',
              streamReady: 'Stream ready.',
              streamUpdate: 'Stream update',
              historyBuilding: 'History is still building up…',
              lblIp: 'IP',
              lblGen: 'Gen',
              lblState: 'State',
              lblEnergy: 'Energy',
              lblCost: 'Cost',
              openShelly: 'Open Shelly',
              lastChange: 'Update',
              agoMinute: 'min',
              agoHour: 'h',
              agoDay: 'd',
              agoPrefix: 'ago',
              shellyMain: 'Main Switch',
              shellyLight: 'Light',
              shellyHumidifier: 'Humidifier',
              shellyHeater: 'Heater',
              shellyFan: 'Fan',
              shellyExhaust: 'Exhaust',
              growPhase: 'Grow Phase',
              mainSwitchCost: 'Total Cost',
              mainEnergy: 'Energy',
              resetCounter: 'Reset counter',
              confirmResetCounter: 'Really reset energy counters?',
              exhaustVpdPlan: 'min. VPD monitoring',
              minVpd: 'Min VPD',
              minShort: 'min',
              hysteresis: 'Hysteresis (kPa)',
              leafOffset: 'Leaf offset',
              irrigationCard: 'Irrigation',
              irNextRun: 'Next',
              irRunsLeft: 'Runs left',
              irTimeLeft: 'Time left',
              irEndAt: 'End time',
              irLastRun: 'Last irrigation',
              lastShort: 'Last',
              irAmount: 'Amount per task',
              irTimePerTask: 'Time/task',
              irBetweenTasks: 'Between tasks',
              irAmountTotal: 'Amount per pot',
              active: 'active',
              growSince: 'Grow since',
              day: 'Day',
              week: 'Week',
              phaseVegetative: 'Vegetative',
              phaseFlower: 'Flower',
              phaseDry: 'Dry',
              toggle: 'Toggle',
              actionFailed: 'Action failed',
              relayToggle: 'Toggle relay',
              startWatering: 'Start watering',
              pingTank: 'Ping tank',
              irrigationPlan: 'Irrigation plan',
              everyDays: 'Every N days',
              offsetAfterLight: 'Minutes after light on',
              savePlan: 'Save plan',
              cancel: 'Cancel',
              active: 'Active',
              scheduleOn: 'ON',
              scheduleOff: 'OFF'
            },
            de: {
              title: 'Dashboard',
              openPlayer: 'Player öffnen',
              openPreview: 'Vollbild öffnen',
              openEsp: 'ESP öffnen',
              openEspStats: 'Stats öffnen',
              uptime: 'Laufzeit',
              uptimeDay: 'Tg',
              uptimeHour: 'Std',
              uptimeMinute: 'Min',
              uptimeSecond: 'Sek',
              viewMobile: 'Mobile Ansicht',
              viewDesktop: 'Desktop Ansicht',
              navOpen: 'Menü',
              navClose: 'Schließen',
              source: 'Quelle',
              setup: 'Setup',
              nav: 'Navigation',
              tents: 'Zelte',
              language: 'Sprache:',
              range: 'Zeitraum:',
              tempUnit: 'Temperatureinheit:',
              temperature: 'Temperatur',
              humidity: 'Luftfeuchte',
              rawValue: 'Rohwert',
              vpd: 'VPD',
              extTemp: 'Wassertanktemperatur',
              extTempSensor: 'Sensor',
              // mainPower removed
              target: 'Sollwert',
              relays: 'Relais',
              relaysExtra: 'Bewässerungsrelais 6-8',
              shelly: 'Shelly-Geräte',
              tempHistory: 'Temperaturverlauf',
              humHistory: 'Luftfeuchteverlauf',
              vpdHistory: 'VPD-Verlauf',
              alphaHistory: 'Alpha-Verlauf',
              alphaHint: 'Adaptives Alpha der Glättung: kleineres α = stärkere Glättung (träge), größeres α = schnellere Reaktion (empfindlicher). α Temp gilt für Temperatur-Glättung, α Hum für Luftfeuchte-Glättung.',
              extTempHistory: 'Wassertank-Temperaturverlauf',
              totalConsumption: 'Gesamtverbrauch',
              totalConsumptionHistory: 'Gesamtverbrauchsverlauf',
              exportCsv: 'CSV exportieren',
              consumptionToday: 'Verbrauch / Kosten heute (0-24)',
              tankLevel: 'Tankfüllstand',
              tankDistance: 'Abstand',
              updated: 'Aktualisiert',
              apiOk: 'API: OK',
              online: 'online',
              offline: 'offline',
              lastSuccess: 'Letzter erfolgreicher GET',
              lastUpdate: 'Letztes Update',
              relay: 'Relais',
              on: 'AN',
              off: 'AUS',
              loadFailed: 'Laden fehlgeschlagen',
              noShelly: 'Keine Shelly-Geräte mit konfigurierter IP gefunden.',
              cameraStream: 'Kamera-Stream',
              noRtsp: 'Kein Stream für dieses Zelt konfiguriert.',
              streamReady: 'Stream bereit.',
              streamUpdate: 'Stream update',
              historyBuilding: 'Historie wird noch aufgebaut…',
              lblIp: 'IP',
              lblGen: 'Gen',
              lblState: 'Status',
              lblEnergy: 'Energie',
              lblCost: 'Kosten',
              openShelly: 'Shelly öffnen',
              lastChange: 'Update',
              agoMinute: 'Min',
              agoHour: 'Std',
              agoDay: 'Tg',
              agoPrefix: 'vor',
              shellyMain: 'Hauptschalter',
              shellyLight: 'Licht',
              shellyHumidifier: 'Luftbefeuchter',
              shellyHeater: 'Heizung',
              shellyFan: 'Lüfter',
              shellyExhaust: 'Abluft',
              growPhase: 'Growphase',
              mainSwitchCost: 'Gesamtkosten',
              mainEnergy: 'Energie',
              resetCounter: 'Zähler zurücksetzen',
              confirmResetCounter: 'Energiezähler wirklich zurücksetzen?',
              exhaustVpdPlan: 'min. VPD Überwachung',
              minVpd: 'Min. VPD',
              minShort: 'min',
              hysteresis: 'Hysterese (kPa)',
              leafOffset: 'Blatt-Offset',
              irrigationCard: 'Bewässerung',
              irNextRun: 'Nächste',
              irRunsLeft: 'Durchläufe übrig',
              irTimeLeft: 'Restzeit',
              irEndAt: 'Endzeit',
              irLastRun: 'Letzte Bewässerung',
              lastShort: 'Letzte',
              irAmount: 'Menge pro Task',
              irTimePerTask: 'Zeit/Task',
              irBetweenTasks: 'Pause zwischen Tasks',
              irAmountTotal: 'Menge pro Topf',
              active: 'aktiv',
              growSince: 'Grow seit',
              day: 'Tag',
              week: 'Woche',
              phaseVegetative: 'Vegetativ',
              phaseFlower: 'Blüte',
              phaseDry: 'Trocknung',
              toggle: 'Umschalten',
              actionFailed: 'Aktion fehlgeschlagen',
              relayToggle: 'Relais schalten',
              startWatering: 'Bewässerung starten',
              pingTank: 'Tank anpingen',
              irrigationPlan: 'Bewässerungsplan',
              everyDays: 'Alle N Tage',
              offsetAfterLight: 'Minuten nach Licht an',
              savePlan: 'Plan speichern',
              cancel: 'Abbrechen',
              active: 'Aktiv',
              scheduleOn: 'AN',
              scheduleOff: 'AUS'
            }
          };

          let currentLang = localStorage.getItem('gt_lang') || 'en';
          let currentTempUnit = localStorage.getItem('gt_temp_unit') || 'C';
          const qTent = Number(new URLSearchParams(window.location.search).get('tent') || '0');
          let currentTentId = Number.isFinite(qTent) && qTent > 0 ? qTent : Number(localStorage.getItem('gt_tent_id') || '1');
          let currentTentMeta = null;
          let shellyLastSwitches = {};
          let shellyMainDirectTs = null;
          let currentIrPlan = null;
          let currentIrLastRunDate = null;
          let currentExhPlan = null;
          let isGuestMode = false;
          let viewMode = localStorage.getItem('gt_view_mode') || 'auto';
          let mobileNavExpanded = false;

          function applyThemeFromStorage(){
            const theme = localStorage.getItem('gt_theme') || 'dark';
            document.documentElement.setAttribute('data-theme', theme === 'light' ? 'light' : 'dark');
          }

          function syncMobileNavUi(){
            const side = document.getElementById('sideNav');
            const btn = document.getElementById('mobileNavToggle');
            if (!side || !btn) return;
            const forcedMobile = document.body.classList.contains('force-mobile');
            const narrow = window.matchMedia('(max-width: 1024px)').matches;
            const mobileActive = forcedMobile || narrow;
            if (!mobileActive) {
              side.classList.remove('expanded');
              btn.style.display = 'none';
              return;
            }
            btn.style.display = 'inline-block';
            side.classList.toggle('expanded', mobileNavExpanded);
            btn.textContent = mobileNavExpanded ? tr('navClose') : tr('navOpen');
          }

          function applyViewMode(){
            document.body.classList.remove('force-mobile', 'force-desktop');
            if (viewMode === 'mobile') document.body.classList.add('force-mobile');
            if (viewMode === 'desktop') document.body.classList.add('force-desktop');
            const btn = document.getElementById('viewModeBtn');
            if (btn) btn.textContent = viewMode === 'mobile' ? tr('viewDesktop') : tr('viewMobile');
            if (viewMode !== 'mobile') mobileNavExpanded = false;
            syncMobileNavUi();
          }

          function tr(key){
            return (I18N[currentLang] && I18N[currentLang][key]) || I18N.en[key] || key;
          }

          function applyI18n(){
            txt('titleMain', tr('title'));
            txt('sourceText', '');
            txt('navTitle', tr('nav'));
            txt('navSetup', tr('setup'));
            txt('langLabel', tr('language'));
            txt('rangeLabel', tr('range'));
            txt('rangeLabelLive', currentLang === 'de' ? 'Zeitraum für Verläufe:' : 'Range for history:');
            txt('rangeHintLive', '');
            txt('tempUnitLabel', tr('tempUnit'));
            txt('lblTemp', tr('temperature'));
            txt('lblHum', tr('humidity'));
            txt('lblVpd', tr('vpd'));
            txt('lblExtTemp', 'DS18B20');
            txt('lblTankLevel', tr('tankLevel'));
            txt('tankLevelSub', `${tr('tankDistance')}: - cm`);
            txt('tankPercent', '- %');
            // main power label removed
            txt('tempTarget', `${tr('target')}: -`);
            txt('tempRaw', `${tr('rawValue')}: -`);
            txt('humRaw', `${tr('rawValue')}: -`);
            html('vpdTarget', `<span style="display:flex; justify-content:space-between; gap:8px;"><span style="display:flex; flex-direction:column; gap:2px;"><span>${tr('target')}: -</span><span>${tr('minShort')}: -</span></span><span>${tr('leafOffset')}: -</span></span>`);
            txt('lblRelays', tr('relays'));
            txt('lblRelaysExtra', tr('relaysExtra'));
            txt('lblShelly', tr('shelly'));
            txt('lblTempHistory', tr('tempHistory'));
            txt('lblHumHistory', tr('humHistory'));
            txt('lblVpdHistory', tr('vpdHistory'));
            txt('lblAlphaHistoryText', tr('alphaHistory'));
            const alphaHintEl = document.getElementById('alphaHistoryHint');
            if (alphaHintEl) {
              const hint = tr('alphaHint');
              alphaHintEl.title = hint;
              alphaHintEl.setAttribute('aria-label', hint);
            }
            txt('lblExtTempHistory', `${extTempLabelBase()} ${currentLang === 'de' ? 'Verlauf' : 'History'}`);
            txt('lblMainWHistory', tr('totalConsumptionHistory'));
            txt('lblStream', tr('cameraStream'));
            txt('streamInfo', tr('noRtsp'));
            txt('streamOpenBtn', tr('openPreview'));
            txt('exportCsvBtn', tr('exportCsv'));
            txt('espOpenBtn', tr('openEsp'));
            txt('espStatsBtn', tr('openEspStats'));
            txt('uptimeBadge', `${tr('uptime')}: -`);
            applyViewMode();
            txt('lblGrowPhase', tr('growPhase'));
            txt('lblMainEnergy', tr('mainEnergy'));
            txt('lblMainCost', tr('mainSwitchCost'));
            txt('lblMainKwhToday', tr('consumptionToday'));
            txt('lblIrrigationCard', tr('irrigationCard'));
            txt('irActiveBadge', tr('active'));
            txt('irNextRun', `${tr('irNextRun')}: -`);
            txt('dbIrPlanTitle', tr('irrigationPlan'));
            txt('dbIrPlanEnabledLabel', tr('active'));
            txt('dbIrPlanEveryDaysLabel', tr('everyDays'));
            txt('dbIrPlanOffsetLabel', tr('offsetAfterLight'));
            txt('dbIrPlanSaveBtn', tr('savePlan'));
            txt('dbIrPlanCancelBtn', tr('cancel'));
            txt('dbExhPlanTitle', tr('exhaustVpdPlan'));
            txt('dbExhPlanEnabledLabel', tr('active'));
            txt('dbExhPlanMinVpdLabel', tr('minVpd'));
            txt('dbExhPlanHystLabel', tr('hysteresis'));
            txt('dbExhPlanSaveBtn', tr('savePlan'));
            txt('dbExhPlanCancelBtn', tr('cancel'));
            const irActiveBadge = document.getElementById('irActiveBadge');
            if (irActiveBadge) irActiveBadge.style.display = 'none';
            txt('mainKwhTodayValue', '- kWh / - €');
            const phaseActions = document.getElementById('phaseActions');
            if (phaseActions) {
              phaseActions.innerHTML = `<button id="resetEnergyBtn" type="button">${tr('resetCounter')}</button><button id="openExhVpdPlanBtn" type="button">${tr('exhaustVpdPlan')}</button>`;
              document.getElementById('resetEnergyBtn')?.addEventListener('click', async () => {
                if (!window.confirm(tr('confirmResetCounter'))) return;
                await resetShellyEnergy();
              });
              document.getElementById('openExhVpdPlanBtn')?.addEventListener('click', async () => {
                await openDashboardExhPlanModal();
              });
            }
            txt('tempLastChange', `${tr('lastChange')} -`);
            txt('humLastChange', `${tr('lastChange')} -`);
            txt('vpdLastChange', `${tr('lastChange')} -`);
            txt('extTempLastChange', `${tr('lastChange')} -`);
            txt('tankLastChange', `${tr('lastChange')} -`);
            renderTentHeader();
          }

          function txt(id, val){ const el=document.getElementById(id); if(el) el.textContent=val; }
          function html(id, val){ const el=document.getElementById(id); if(el) el.innerHTML=val; }
          function escHtml(v){ return String(v ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;'); }

          function getTentOnlineState(capturedAt){
            if (!capturedAt) return false;
            const ts = Date.parse(capturedAt);
            if (!Number.isFinite(ts)) return false;
            // Mark tent as offline if last successful poll is older than 2 minutes.
            return (Date.now() - ts) <= 120000;
          }

          function formatLastSuccess(capturedAt){
            return formatShellyChangeTime(capturedAt);
          }

          function formatShellyChangeTime(ts){
            if (!ts) return '-';
            const d = new Date(ts);
            if (Number.isNaN(d.getTime())) return '-';

            const diffMs = Date.now() - d.getTime();
            if (!Number.isFinite(diffMs) || diffMs < 0) return '-';

            const diffMin = Math.floor(diffMs / 60000);
            if (diffMin < 1) return `${tr('agoPrefix')} 1 ${tr('agoMinute')}`;
            if (diffMin < 60) return `${tr('agoPrefix')} ${diffMin} ${tr('agoMinute')}`;

            const diffHour = Math.floor(diffMin / 60);
            if (diffHour < 24) return `${tr('agoPrefix')} ${diffHour} ${tr('agoHour')}`;

            const diffDay = Math.floor(diffHour / 24);
            return `${tr('agoPrefix')} ${diffDay} ${tr('agoDay')}`;
          }

          function formatUptimeSingleUnit(secondsRaw){
            const s = Number(secondsRaw);
            if (!Number.isFinite(s) || s < 0) return '-';
            const days = Math.floor(s / 86400);
            if (days >= 1) return `${days} ${tr('uptimeDay')}`;
            const hours = Math.floor(s / 3600);
            if (hours >= 1) return `${hours} ${tr('uptimeHour')}`;
            const minutes = Math.floor(s / 60);
            if (minutes >= 1) return `${minutes} ${tr('uptimeMinute')}`;
            return `${Math.floor(s)} ${tr('uptimeSecond')}`;
          }

          function getLastMetricChangeTimestamp(points, key){
            if (!Array.isArray(points) || points.length < 2) return null;
            let prev = null;
            let lastTs = null;
            for (const p of points) {
              const cur = Number(p?.[key]);
              if (!Number.isFinite(cur)) continue;
              if (prev === null) {
                prev = cur;
                continue;
              }
              if (Math.abs(cur - prev) > 1e-9) {
                lastTs = p.t || null;
              }
              prev = cur;
            }
            return lastTs;
          }

          function getControllerBaseUrl(sourceUrl){
            try {
              const u = new URL(String(sourceUrl || ''), window.location.origin);
              return `${u.protocol}//${u.host}`;
            } catch {
              return null;
            }
          }

          function renderTentHeader(){
            const espBtn = document.getElementById('espOpenBtn');
            const espStatsBtn = document.getElementById('espStatsBtn');
            const uptimeEl = document.getElementById('uptimeBadge');
            if (!currentTentMeta) {
              if (espBtn) { espBtn.style.display = 'none'; espBtn.removeAttribute('href'); }
              if (espStatsBtn) { espStatsBtn.style.display = 'none'; espStatsBtn.removeAttribute('href'); }
              if (uptimeEl) { uptimeEl.style.display = 'none'; uptimeEl.textContent = `${tr('uptime')}: -`; }
              return;
            }
            const online = getTentOnlineState(currentTentMeta.capturedAt);
            const statusLabel = online ? tr('online') : tr('offline');
            const statusClass = online ? 'status-online' : 'status-offline';
            const last = formatLastSuccess(currentTentMeta.capturedAt);
            html('titleMain', `${escHtml(currentTentMeta.navName)} <span class="${statusClass}">${escHtml(statusLabel)}</span><span class="status-meta">${tr('lastChange')} ${escHtml(last)}</span>`);
            html('sourceText', '');

            const espUrl = getControllerBaseUrl(currentTentMeta.source_url);
            if (espBtn && espUrl) {
              espBtn.href = espUrl;
              espBtn.style.display = 'inline-block';
            } else if (espBtn) {
              espBtn.style.display = 'none';
              espBtn.removeAttribute('href');
            }
            if (espStatsBtn && espUrl) {
              const base = espUrl.endsWith('/') ? espUrl.slice(0, -1) : espUrl;
              espStatsBtn.href = `${base}/api/state`;
              espStatsBtn.style.display = 'inline-block';
            } else if (espStatsBtn) {
              espStatsBtn.style.display = 'none';
              espStatsBtn.removeAttribute('href');
            }
          }

          function fmtNum(value, decimals){
            const n = Number(value);
            return Number.isFinite(n) ? n.toFixed(decimals) : '-';
          }

          function setAlphaLed(id, alphaVal){
            const el = document.getElementById(id);
            if (!el) return;
            el.classList.remove('alpha-led-green', 'alpha-led-yellow', 'alpha-led-red', 'alpha-led-off');
            const a = Number(alphaVal);
            if (!Number.isFinite(a)) {
              el.classList.add('alpha-led-off');
              el.title = 'α: -';
              return;
            }
            if (a < 0.10) el.classList.add('alpha-led-green');
            else if (a <= 0.20) el.classList.add('alpha-led-yellow');
            else el.classList.add('alpha-led-red');
            el.title = `α: ${a.toFixed(2)}`;
          }

          function setHistoryOverlays(message){
            const ids = [
              'historyOverlayTemp', 'historyOverlayHum', 'historyOverlayVpd',
              'historyOverlayAlpha', 'historyOverlayExtTemp', 'historyOverlayMainW'
            ];
            ids.forEach((id) => {
              const el = document.getElementById(id);
              if (!el) return;
              if (message) {
                el.textContent = message;
                el.style.display = 'flex';
              } else {
                el.textContent = '';
                el.style.display = 'none';
              }
            });
          }

          function arcPath(cx, cy, r){
            return `M ${cx-r} ${cy} A ${r} ${r} 0 0 1 ${cx+r} ${cy}`;
          }

          function pointOnSemi(cx, cy, r, p){
            const clamped = Math.max(0, Math.min(1, Number.isFinite(p) ? p : 0));
            const angle = Math.PI - (Math.PI * clamped);
            return { x: cx + Math.cos(angle) * r, y: cy - Math.sin(angle) * r };
          }

          function renderSemiGauge(wrapId, fillClass, value, min, max, targetValue = null, valueLabel = ''){
            const wrap = document.getElementById(wrapId);
            if (!wrap) return;

            const cx = 80, cy = 76, r = 56;
            const p = (Number(value) - min) / (max - min);
            const valPoint = pointOnSemi(cx, cy, r, p);
            const basePath = arcPath(cx, cy, r);
            const pClamped = Math.max(0, Math.min(1, Number.isFinite(p) ? p : 0));
            const fillPath = `M ${cx-r} ${cy} A ${r} ${r} 0 0 1 ${valPoint.x} ${valPoint.y}`;

            let targetDot = '';
            if (Number.isFinite(Number(targetValue))) {
              const tp = (Number(targetValue) - min) / (max - min);
              const tPoint = pointOnSemi(cx, cy, r, tp);
              targetDot = `<circle class="g-target" cx="${tPoint.x}" cy="${tPoint.y}" r="4"></circle>`;
            }

            wrap.innerHTML = `
              <svg viewBox="0 0 160 92" role="img" aria-label="gauge">
                <path class="g-track" d="${basePath}"></path>
                <path class="${fillClass}" d="${fillPath}"></path>
                ${targetDot}
                <text class="g-value" x="80" y="88">${valueLabel}</text>
              </svg>
            `;
          }

          function updateCurrentGauges(tempValue, humValue, vpdValue, tempTarget, vpdTarget){
            const tMin = currentTempUnit === 'F' ? 32 : 0;
            const tMax = currentTempUnit === 'F' ? 104 : 40;
            const tempLabel = Number.isFinite(Number(tempValue)) ? `${Number(tempValue).toFixed(1)}°${currentTempUnit}` : '-';
            const humLabel = Number.isFinite(Number(humValue)) ? `${Number(humValue).toFixed(1)}%` : '-';
            const vpdLabel = Number.isFinite(Number(vpdValue)) ? `${Number(vpdValue).toFixed(2)} kPa` : '-';
            renderSemiGauge('gaugeTempWrap', 'g-fill-temp', tempValue, tMin, tMax, tempTarget, tempLabel);
            renderSemiGauge('gaugeHumWrap', 'g-fill-hum', humValue, 0, 100, null, humLabel);
            renderSemiGauge('gaugeVpdWrap', 'g-fill-vpd', vpdValue, 0, 3, vpdTarget, vpdLabel);
          }

          function firstNum(obj, keys){
            for (const k of keys) {
              const n = Number(obj?.[k]);
              if (Number.isFinite(n)) return n;
            }
            return null;
          }

          function cToF(c){
            const n = Number(c);
            return Number.isFinite(n) ? (n * 9/5) + 32 : null;
          }

          function convertTempFromC(c){
            if (currentTempUnit === 'F') return cToF(c);
            return Number(c);
          }

          function parseDurationToSeconds(v){
            const s = String(v || '').trim();
            if (!s) return null;
            const p = s.split(':').map(x => Number(x));
            if (p.some(n => !Number.isFinite(n))) return null;
            if (p.length === 2) {
              // Firmware value is interpreted as h:mm (e.g. 0:22 = 22 minutes).
              return (p[0] * 3600) + (p[1] * 60);
            }
            if (p.length === 3) {
              return (p[0] * 3600) + (p[1] * 60) + p[2];
            }
            return null;
          }

          function calcEndTimeLabel(timeLeft){
            const sec = parseDurationToSeconds(timeLeft);
            if (!Number.isFinite(sec)) return '-';
            const end = new Date(Date.now() + (sec * 1000));
            // Display as h:min (hour without forced leading zero).
            return end.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
          }

          function parseLightOnMinFromLine(line){
            const s = String(line || '');
            const m = /ON\\s*(\\d{1,2}):(\\d{2})/i.exec(s);
            if (!m) return null;
            const h = Number(m[1]);
            const mi = Number(m[2]);
            if (!Number.isFinite(h) || !Number.isFinite(mi) || h < 0 || h > 23 || mi < 0 || mi > 59) return null;
            return (h * 60) + mi;
          }

          function formatNextRunDate(dt){
            if (!(dt instanceof Date) || Number.isNaN(dt.getTime())) return '-';
            return dt.toLocaleString(currentLang === 'de' ? 'de-DE' : 'en-GB', {
              weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
            });
          }

          function formatLastRunDate(isoDate){
            if (!isoDate) return '-';
            const dt = new Date(`${isoDate}T00:00:00`);
            if (Number.isNaN(dt.getTime())) return '-';
            return dt.toLocaleDateString(currentLang === 'de' ? 'de-DE' : 'en-GB', {
              weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit'
            });
          }

          function computeNextIrrigationDate(plan, lastRunDate, lightLine){
            if (!plan?.enabled) return null;
            const onMin = parseLightOnMinFromLine(lightLine);
            if (onMin === null) return null;
            const now = new Date();
            const everyDays = Math.max(1, Number(plan.every_n_days || 1));
            const offset = Math.max(0, Number(plan.offset_after_light_on_min || 0));
            const runMin = onMin + offset;

            const mkLocal = (d) => {
              const dd = new Date(d);
              dd.setHours(0,0,0,0);
              const h = Math.floor(runMin / 60) % 24;
              const m = runMin % 60;
              dd.setHours(h, m, 0, 0);
              return dd;
            };

            let next;
            if (lastRunDate) {
              const last = new Date(`${lastRunDate}T00:00:00`);
              if (!Number.isNaN(last.getTime())) {
                next = mkLocal(last);
                next.setDate(next.getDate() + everyDays);
                while (next <= now) next.setDate(next.getDate() + everyDays);
              }
            }

            if (!next) {
              next = mkLocal(now);
              if (next <= now) next.setDate(next.getDate() + everyDays);
            }
            return next;
          }

          function phaseLabel(phase){
            const p = Number(phase);
            if (p === 1) return tr('phaseVegetative');
            if (p === 2) return tr('phaseFlower');
            if (p === 3) return tr('phaseDry');
            return '-';
          }

          function phaseClass(phase){
            const p = Number(phase);
            if (p === 1) return 'phase-veg';
            if (p === 2) return 'phase-flower';
            if (p === 3) return 'phase-dry';
            return '';
          }

          function normalizeShellyDeviceFromPayload(d, key){
            const ip = d[`settings.shelly.${key}.ip`];
            if (!ip || String(ip).trim() === '') return null;

            return {
              key,
              ip: String(ip),
              gen: d[`settings.shelly.${key}.gen`] ?? '-',
              line: d[`settings.shelly.${key}.line`] ?? '',
              isOn: d[`cur.shelly.${key}.isOn`],
              watt: d[`cur.shelly.${key}.Watt`],
              wh: d[`cur.shelly.${key}.Wh`],
              cost: d[`cur.shelly.${key}.Cost`]
            };
          }

          function shellyIcon(key){
            switch(key){
              case 'main': return '🔌';
              case 'light': return '💡';
              case 'humidifier': return '💧';
              case 'heater': return '🔥';
              case 'fan': return '🌀';
              case 'exhaust': return '🌬️';
              default: return '🔘';
            }
          }

          function shellyName(key){
            const map = {
              main: tr('shellyMain'),
              light: tr('shellyLight'),
              humidifier: tr('shellyHumidifier'),
              heater: tr('shellyHeater'),
              fan: tr('shellyFan'),
              exhaust: tr('shellyExhaust')
            };
            return map[key] || (key.charAt(0).toUpperCase() + key.slice(1));
          }

          async function runPostAction(url){
            try {
              const r = await fetch(url, { method: 'POST' });
              let body = null;
              try { body = await r.json(); } catch {}

              if (!r.ok || (body && body.ok === false)) {
                const detail = body?.detail || body?.status_code || r.status;
                alert(`${tr('actionFailed')}: ${detail}`);
                return false;
              }
              // Avoid full-page data refresh to keep stream iframe stable.
              await loadLatest();
              return true;
            } catch (e) {
              alert(`${tr('actionFailed')}: ${e}`);
              return false;
            }
          }

          function closeDashboardIrPlanModal(){
            const modal = document.getElementById('dbIrPlanModal');
            if (modal) modal.style.display = 'none';
          }

          async function openDashboardIrPlanModal(){
            const modal = document.getElementById('dbIrPlanModal');
            const msg = document.getElementById('dbIrPlanMsg');
            const title = document.getElementById('dbIrPlanTentLabel');
            const enabledEl = document.getElementById('dbIrPlanEnabled');
            const everyEl = document.getElementById('dbIrPlanEveryDays');
            const offsetEl = document.getElementById('dbIrPlanOffset');
            if (!modal || !enabledEl || !everyEl || !offsetEl || !currentTentId) return;

            if (title) title.textContent = `#${currentTentId}`;
            if (msg) msg.textContent = '';
            modal.style.display = 'flex';

            try {
              const res = await fetch(`/tents/${currentTentId}/irrigation-plan`, { cache: 'no-store' });
              const j = await res.json();
              const p = j?.plan || {};
              enabledEl.checked = !!p.enabled;
              everyEl.value = Number(p.every_n_days || 1);
              offsetEl.value = Number(p.offset_after_light_on_min || 0);
              if (msg && j?.last_run_date) msg.textContent = `Last run: ${j.last_run_date}`;
            } catch {
              enabledEl.checked = false;
              everyEl.value = 1;
              offsetEl.value = 0;
              if (msg) msg.textContent = tr('loadFailed');
            }
          }

          async function saveDashboardIrPlan(){
            const msg = document.getElementById('dbIrPlanMsg');
            const enabledEl = document.getElementById('dbIrPlanEnabled');
            const everyEl = document.getElementById('dbIrPlanEveryDays');
            const offsetEl = document.getElementById('dbIrPlanOffset');
            if (!currentTentId || !enabledEl || !everyEl || !offsetEl) return;

            const payload = {
              enabled: !!enabledEl.checked,
              every_n_days: Math.max(1, Number(everyEl.value || 1)),
              offset_after_light_on_min: Math.max(0, Number(offsetEl.value || 0)),
            };

            try {
              const res = await fetch(`/tents/${currentTentId}/irrigation-plan`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
              });
              if (!res.ok) {
                if (msg) msg.textContent = tr('actionFailed');
                return;
              }
              const j = await res.json().catch(() => ({}));
              currentIrPlan = j?.plan || payload;
              currentIrLastRunDate = j?.last_run_date || currentIrLastRunDate;
              if (msg) msg.textContent = currentLang === 'de' ? 'Plan gespeichert.' : 'Plan saved.';
              await loadLatest();
            } catch {
              if (msg) msg.textContent = tr('actionFailed');
            }
          }

          document.getElementById('dbIrPlanCloseBtn')?.addEventListener('click', closeDashboardIrPlanModal);
          document.getElementById('dbIrPlanCancelBtn')?.addEventListener('click', closeDashboardIrPlanModal);
          document.getElementById('dbIrPlanSaveBtn')?.addEventListener('click', saveDashboardIrPlan);

          function closeDashboardExhPlanModal(){
            const modal = document.getElementById('dbExhPlanModal');
            if (modal) modal.style.display = 'none';
          }

          async function openDashboardExhPlanModal(){
            const modal = document.getElementById('dbExhPlanModal');
            const msg = document.getElementById('dbExhPlanMsg');
            const title = document.getElementById('dbExhPlanTentLabel');
            const enabledEl = document.getElementById('dbExhPlanEnabled');
            const minVpdEl = document.getElementById('dbExhPlanMinVpd');
            const hystEl = document.getElementById('dbExhPlanHyst');
            if (!modal || !enabledEl || !minVpdEl || !hystEl || !currentTentId) return;

            if (title) title.textContent = `#${currentTentId}`;
            if (msg) msg.textContent = '';
            modal.style.display = 'flex';

            try {
              const res = await fetch(`/tents/${currentTentId}/exhaust-vpd-plan`, { cache: 'no-store' });
              const j = await res.json();
              const p = j?.plan || {};
              enabledEl.checked = !!p.enabled;
              minVpdEl.value = Number(p.min_vpd_kpa || 0.6).toFixed(2);
              hystEl.value = Number(p.hysteresis_kpa ?? 0.05).toFixed(2);
            } catch {
              enabledEl.checked = false;
              minVpdEl.value = '0.60';
              hystEl.value = '0.05';
              if (msg) msg.textContent = tr('loadFailed');
            }
          }

          async function saveDashboardExhPlan(){
            const msg = document.getElementById('dbExhPlanMsg');
            const enabledEl = document.getElementById('dbExhPlanEnabled');
            const minVpdEl = document.getElementById('dbExhPlanMinVpd');
            const hystEl = document.getElementById('dbExhPlanHyst');
            if (!currentTentId || !enabledEl || !minVpdEl || !hystEl) return;

            const payload = {
              enabled: !!enabledEl.checked,
              min_vpd_kpa: Math.max(0.1, Number(minVpdEl.value || 0.6)),
              hysteresis_kpa: Math.max(0, Number(hystEl.value || 0.05)),
            };

            try {
              const res = await fetch(`/tents/${currentTentId}/exhaust-vpd-plan`, {
                method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
              });
              if (!res.ok) {
                if (msg) msg.textContent = tr('actionFailed');
                return;
              }
              const j = await res.json().catch(() => ({}));
              currentExhPlan = j?.plan || payload;
              if (msg) msg.textContent = currentLang === 'de' ? 'Plan gespeichert.' : 'Plan saved.';
            } catch {
              if (msg) msg.textContent = tr('actionFailed');
            }
          }

          document.getElementById('dbExhPlanCloseBtn')?.addEventListener('click', closeDashboardExhPlanModal);
          document.getElementById('dbExhPlanCancelBtn')?.addEventListener('click', closeDashboardExhPlanModal);
          document.getElementById('dbExhPlanSaveBtn')?.addEventListener('click', saveDashboardExhPlan);

          async function refreshPlanButtonStates(){
            const irBtn = document.getElementById('openIrPlanBtn');
            const exBtn = document.getElementById('openExhVpdPlanBtn');
            const activeStyle = 'linear-gradient(180deg, rgba(34,197,94,.35), rgba(22,163,74,.28))';
            const inactiveStyle = 'linear-gradient(180deg, rgba(239,68,68,.35), rgba(220,38,38,.28))';
            currentIrPlan = null;
            currentIrLastRunDate = null;
            currentExhPlan = null;
            if (!currentTentId) return;

            try {
              const r = await fetch(`/tents/${currentTentId}/irrigation-plan`, { cache:'no-store' });
              const j = await r.json().catch(() => ({}));
              if (r.ok) {
                currentIrPlan = j?.plan || null;
                currentIrLastRunDate = j?.last_run_date || null;
                if (irBtn) irBtn.style.background = j?.plan?.enabled ? activeStyle : inactiveStyle;
              }
            } catch {}

            try {
              const r = await fetch(`/tents/${currentTentId}/exhaust-vpd-plan`, { cache:'no-store' });
              const j = await r.json().catch(() => ({}));
              if (r.ok) currentExhPlan = j?.plan || null;
              if (exBtn && r.ok) exBtn.style.background = j?.plan?.enabled ? activeStyle : inactiveStyle;
            } catch {}
          }

          async function toggleShelly(deviceKey){
            const allowed = ['main', 'light', 'humidifier', 'heater', 'fan', 'exhaust'];
            if (!allowed.includes(deviceKey)) return;
            await runPostAction(`/tents/${currentTentId}/actions/shelly/${deviceKey}/toggle`);
          }

          async function toggleRelay(idx){
            await runPostAction(`/tents/${currentTentId}/actions/relay/${idx}/toggle`);
          }

          async function startWatering(){
            await runPostAction(`/tents/${currentTentId}/actions/startWatering`);
          }

          async function triggerPump10s(idx){
            await runPostAction(`/tents/${currentTentId}/actions/pump/${idx}/trigger10s`);
          }

          async function pingTank(){
            await runPostAction(`/tents/${currentTentId}/actions/pingTank`);
          }

          async function resetShellyEnergy(){
            await runPostAction(`/tents/${currentTentId}/actions/shelly/reset-energy`);
          }

          function ensureMutedPlayerUrl(url){
            if (!url) return url;
            try {
              const u = new URL(url, window.location.origin);
              const rawSrc = u.searchParams.get('src') || '';
              if (rawSrc) {
                let decoded = rawSrc;
                try { decoded = decodeURIComponent(rawSrc); } catch {}
                if (!decoded.includes('#media=video')) decoded += '#media=video';
                u.searchParams.set('src', decoded);
              }
              u.searchParams.set('muted', '1');
              u.searchParams.set('volume', '0');
              u.searchParams.set('audio', '0');
              u.searchParams.set('media', 'video');
              u.searchParams.set('defaultMute', '1');
              return u.toString();
            } catch {
              const sep = url.includes('?') ? '&' : '?';
              const withVideo = url.includes('#media=video') ? url : `${url}#media=video`;
              return `${withVideo}${sep}muted=1&volume=0&audio=0&media=video&defaultMute=1`;
            }
          }

          function renderStream(rtspUrl, webrtcUrl, playerUrl, previewUrl){
            const info = document.getElementById('streamInfo');
            const openBtn = document.getElementById('streamOpenBtn');
            const frame = document.getElementById('streamFrame');
            const preview = document.getElementById('streamPreview');
            if (!info || !openBtn || !frame || !preview) return;

            if (previewTimer) {
              clearInterval(previewTimer);
              previewTimer = null;
            }

            const basePreview = String(previewUrl || '').trim();
            const withPreviewParams = (url, w, h, q) => {
              const sep = url.includes('?') ? '&' : '?';
              return `${url}${sep}w=${w}&h=${h}&q=${q}`;
            };
            const inlinePreviewBase = basePreview ? withPreviewParams(basePreview, 1280, 720, 80) : '';
            const fullPreviewBase = basePreview ? withPreviewParams(basePreview, 1920, 1080, 90) : '';
            if (!basePreview) {
              info.textContent = tr('noRtsp');
              currentPreviewBase = '';
              openBtn.style.display = 'none';
              openBtn.removeAttribute('href');
              openBtn.onclick = null;
              preview.style.display = 'none';
              preview.removeAttribute('src');
              frame.style.display = 'none';
              frame.removeAttribute('src');
              return;
            }

            let lastPreviewOkTs = 0;
            const updateStreamInfo = () => {
              if (!lastPreviewOkTs) {
                info.textContent = `${tr('streamUpdate')}: -`;
                return;
              }
              info.textContent = `${tr('streamUpdate')}: ${new Date(lastPreviewOkTs).toLocaleTimeString()}`;
            };
            updateStreamInfo();
            currentPreviewBase = fullPreviewBase;
            openBtn.href = '#';
            openBtn.style.display = 'inline-block';
            openBtn.onclick = (ev) => {
              ev.preventDefault();
              if (!currentPreviewBase) return;

              const w = window.open('about:blank', '_blank', 'width=1200,height=800');
              if (!w) return;

              w.document.title = 'CanopyOps Preview';
              const doc = w.document;
              const theme = (localStorage.getItem('gt_theme') || 'dark') === 'light' ? 'light' : 'dark';
              const colors = theme === 'light'
                ? {
                    bodyBg: '#eef2f5', bodyText: '#0f172a', headerBg: '#f8fafc',
                    border: 'rgba(51,65,85,.2)', muted: '#475569', stageBg: '#e2e8f0',
                    btnBorder: 'rgba(51,65,85,.35)', btnBg: 'rgba(29,78,216,.12)', btnText: '#0f172a'
                  }
                : {
                    bodyBg: '#0f172a', bodyText: '#e2e8f0', headerBg: '#1e293b',
                    border: 'rgba(148,163,184,.2)', muted: '#94a3b8', stageBg: '#020617',
                    btnBorder: 'rgba(148,163,184,.35)', btnBg: 'rgba(59,130,246,.25)', btnText: '#e2e8f0'
                  };

              doc.body.style.margin = '0';
              doc.body.style.background = colors.bodyBg;
              doc.body.style.color = colors.bodyText;
              doc.body.style.fontFamily = 'Arial, sans-serif';
              doc.body.style.height = '100vh';
              doc.body.style.display = 'grid';
              doc.body.style.gridTemplateRows = '48px 1fr';

              const header = doc.createElement('div');
              header.style.display = 'flex';
              header.style.alignItems = 'center';
              header.style.justifyContent = 'space-between';
              header.style.padding = '0 12px';
              header.style.background = colors.headerBg;
              header.style.borderBottom = `1px solid ${colors.border}`;

              const title = doc.createElement('div');
              title.textContent = currentLang === 'de' ? 'CanopyOps · Vorschau' : 'CanopyOps · Preview';
              title.style.fontWeight = '700';

              const stamp = doc.createElement('div');
              stamp.style.fontSize = '.82rem';
              stamp.style.color = colors.muted;
              stamp.textContent = `${tr('streamUpdate')}: -`;

              const closeBtn = doc.createElement('button');
              closeBtn.textContent = currentLang === 'de' ? 'Schließen' : 'Close';
              closeBtn.style.marginLeft = '10px';
              closeBtn.style.padding = '5px 9px';
              closeBtn.style.borderRadius = '8px';
              closeBtn.style.border = `1px solid ${colors.btnBorder}`;
              closeBtn.style.background = colors.btnBg;
              closeBtn.style.color = colors.btnText;
              closeBtn.style.cursor = 'pointer';
              closeBtn.onclick = () => w.close();

              const right = doc.createElement('div');
              right.style.display = 'flex';
              right.style.alignItems = 'center';
              right.appendChild(stamp);
              right.appendChild(closeBtn);

              header.appendChild(title);
              header.appendChild(right);

              const stage = doc.createElement('div');
              stage.style.display = 'flex';
              stage.style.alignItems = 'center';
              stage.style.justifyContent = 'center';
              stage.style.background = colors.stageBg;

              const img = doc.createElement('img');
              img.alt = 'Preview';
              img.style.maxWidth = '100vw';
              img.style.maxHeight = 'calc(100vh - 48px)';
              img.style.objectFit = 'contain';

              stage.appendChild(img);
              doc.body.appendChild(header);
              doc.body.appendChild(stage);

              let popupLastOkTs = 0;
              const tick = () => {
                const sep = currentPreviewBase.includes('?') ? '&' : '?';
                const nextSrc = `${currentPreviewBase}${sep}t=${Date.now()}`;
                const pre = new w.Image();
                pre.onload = () => {
                  img.src = nextSrc;
                  popupLastOkTs = Date.now();
                  stamp.textContent = `${tr('streamUpdate')}: ${new Date(popupLastOkTs).toLocaleTimeString()}`;
                };
                pre.onerror = () => {
                  // Keep last good image, retry on next tick.
                };
                pre.src = nextSrc;
              };
              tick();
              w.setInterval(tick, 2500);
            };

            // Dashboard uses low-frame JPEG preview to save bandwidth/CPU.
            const refreshPreview = () => {
              if (!inlinePreviewBase) return;
              const stamp = `t=${Date.now()}`;
              const sep = inlinePreviewBase.includes('?') ? '&' : '?';
              const nextSrc = `${inlinePreviewBase}${sep}${stamp}`;
              const pre = new Image();
              pre.onload = () => {
                preview.src = nextSrc;
                lastPreviewOkTs = Date.now();
                updateStreamInfo();
              };
              pre.onerror = () => {
                // Keep last good image, retry on next cycle.
              };
              pre.src = nextSrc;
            };
            refreshPreview();
            previewTimer = setInterval(refreshPreview, 2500);
            preview.style.display = inlinePreviewBase ? 'block' : 'none';

            // Keep iframe disabled in dashboard; full stream only via "Open Player".
            frame.style.display = 'none';
            frame.removeAttribute('src');
          }

          function renderShellyDevices(d){
            const container = document.getElementById('shellyDevices');
            if (!container) return;

            const shellyUrl = (ip) => {
              const raw = String(ip || '').trim();
              if (!raw || raw === '-') return null;
              if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
              return `http://${raw}`;
            };

            const base = ['main', 'light', 'humidifier', 'heater', 'fan', 'exhaust'];
            const dynamic = Object.keys(d || {})
              .map(k => {
                const m = /^settings[.]shelly[.]([^.]+)[.]ip$/.exec(k);
                return m ? m[1] : null;
              })
              .filter(Boolean);
            const candidates = Array.from(new Set([...base, ...dynamic]));
            const devices = candidates
              .map(k => normalizeShellyDeviceFromPayload(d, k))
              .filter(Boolean);

            if (!devices.length) {
              container.innerHTML = `<div class="small">${tr('noShelly')}</div>`;
              return;
            }

            const cards = devices.map(dev => {
              const state = dev.isOn ? tr('on') : tr('off');
              const watt = Number.isFinite(Number(dev.watt)) ? Number(dev.watt).toFixed(1) + ' W' : '-';
              const kwh = Number.isFinite(Number(dev.wh)) ? (Number(dev.wh) / 1000).toFixed(3) + ' kWh' : '-';
              const eur = Number.isFinite(Number(dev.cost)) ? Number(dev.cost).toFixed(2) + ' €' : '-';
              const cardStateClass = dev.isOn ? 'shelly-card-on' : 'shelly-card-off';

              const canToggle = ['main', 'light', 'humidifier', 'heater', 'fan', 'exhaust'].includes(dev.key);
              const url = shellyUrl(dev.ip);
              const rawLine = String(dev.line || '').trim();
              const onMatch = /(?:^|[|])[ ]*ON[ ]*([^|]+)/i.exec(rawLine);
              const offMatch = /(?:^|[|])[ ]*OFF[ ]*([^|]+)/i.exec(rawLine);
              const scheduleText = (onMatch || offMatch)
                ? `${onMatch ? `${tr('scheduleOn')} ${onMatch[1].trim()}` : ''}${(onMatch && offMatch) ? ' | ' : ''}${offMatch ? `${tr('scheduleOff')} ${offMatch[1].trim()}` : ''}`
                : '';
              const scheduleRight = (dev.key === 'light' && scheduleText)
                ? `<span class="small" style="white-space:nowrap; font-weight:400;">${scheduleText}</span>`
                : '';
              const changeTs = (dev.key === 'main' && shellyMainDirectTs) ? shellyMainDirectTs : shellyLastSwitches?.[dev.key];
              return `
                <div class="card ${cardStateClass}" style="margin-bottom:0;">
                  <div class="card-head">
                    <div class="label">${shellyIcon(dev.key)} ${shellyName(dev.key)}</div>
                    <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                      <span class="small">${tr('lastChange')} ${formatShellyChangeTime(changeTs)}</span>
                      <span class="status-badge ${dev.isOn ? 'status-on' : 'status-off'}">${state}</span>
                    </div>
                  </div>
                  <div class="value" style="font-size:1.1rem; display:flex; align-items:baseline; justify-content:space-between; gap:8px;"><span>${watt}</span>${scheduleRight}</div>
                  <div class="small">${tr('lblIp')}: ${dev.ip}</div>
                  <div class="small">${tr('lblGen')}: ${dev.gen}</div>
                  <div class="small">${tr('lblEnergy')}: ${kwh}</div>
                  <div class="small">${tr('lblCost')}: ${eur}</div>
                  <div class="shelly-actions">
                    ${canToggle ? `<button data-shelly-toggle="${dev.key}">${tr('toggle')}</button>` : '<span></span>'}
                    ${url ? `<button data-open-shelly="${url}">${tr('openShelly')}</button>` : '<span></span>'}
                  </div>
                </div>
              `;
            });

            container.innerHTML = cards.join('');
            container.querySelectorAll('button[data-shelly-toggle]').forEach(btn => {
              btn.addEventListener('click', async () => {
                const key = btn.getAttribute('data-shelly-toggle');
                await toggleShelly(String(key || ''));
              });
            });
            container.querySelectorAll('button[data-open-shelly]').forEach(btn => {
              btn.addEventListener('click', () => {
                const url = btn.getAttribute('data-open-shelly') || '';
                if (!url) return;
                window.open(url, '_blank', 'noopener,noreferrer');
              });
            });
          }

          let tempChart;
          let humChart;
          let vpdChart;
          let alphaChart;
          let extTempChart;
          let mainWChart;
          let previewTimer = null;
          let currentPreviewBase = '';
          let extTempSensorName = 'DS18B20';
          let targetTempCChart = NaN;
          let targetVpdChart = NaN;
          let lastGoodLatestPayload = null;
          let lastGoodCapturedAt = null;

          function buildSingleChart(canvasId, labels, datasetLabel, values, color, unitLabel, lineTension = 0.25){
            const ctx = document.getElementById(canvasId);
            if (!ctx || typeof Chart === 'undefined') return null;

            return new Chart(ctx, {
              type: 'line',
              data: {
                labels,
                datasets: [
                  { label: datasetLabel, data: values, borderColor: color, tension: lineTension, pointRadius: 0, pointHoverRadius: 5, pointHitRadius: 18, yAxisID: 'y' },
                  { label: '', data: values, borderColor: 'rgba(0,0,0,0)', backgroundColor: 'rgba(0,0,0,0)', tension: lineTension, pointRadius: 0, pointHoverRadius: 0, pointHitRadius: 0, yAxisID: 'yR' }
                ]
              },
              options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'nearest', intersect: false },
                scales: {
                  x: { ticks: { color:'#94a3b8' }, grid:{ color:'rgba(148,163,184,.15)' } },
                  y: {
                    position: 'left',
                    ticks:{ color: color },
                    grid:{ color:'rgba(148,163,184,.15)' },
                    title: { display: true, text: unitLabel, color:'#cbd5e1' },
                    afterFit: (scale) => { scale.width = 56; }
                  },
                  yR: {
                    position: 'right',
                    ticks:{ color: color },
                    grid:{ drawOnChartArea: false },
                    title: { display: true, text: unitLabel, color:'#cbd5e1' },
                    afterFit: (scale) => { scale.width = 56; }
                  }
                },
                plugins: { legend: { labels: legendLabelsWithCurrent() } }
              }
            });
          }

          function extTempLabelBase(){
            const base = (extTempSensorName || 'DS18B20').toString().trim() || 'DS18B20';
            return `${base} ${tr('temperature')}`;
          }

          function targetLineColor(){
            return document.documentElement.getAttribute('data-theme') === 'light' ? '#64748b' : '#94a3b8';
          }

          function chartLegendColor(){
            return document.documentElement.getAttribute('data-theme') === 'light' ? '#0f172a' : '#e2e8f0';
          }

          function legendLabelsWithCurrent(){
            if (typeof Chart === 'undefined' || !Chart?.defaults?.plugins?.legend?.labels?.generateLabels) {
              return { color: chartLegendColor(), filter: (item) => !!item.text };
            }
            return {
              color: chartLegendColor(),
              filter: (item) => !!item.text,
              generateLabels: (chart) => {
                const base = Chart.defaults.plugins.legend.labels.generateLabels(chart) || [];
                return base.map((it) => {
                  const ds = chart?.data?.datasets?.[it.datasetIndex];
                  if (!ds || !Array.isArray(ds.data) || !it.text) return it;
                  let last = null;
                  for (let i = ds.data.length - 1; i >= 0; i--) {
                    const n = Number(ds.data[i]);
                    if (Number.isFinite(n)) { last = n; break; }
                  }
                  if (Number.isFinite(last)) {
                    const abs = Math.abs(last);
                    const decimals = abs >= 100 ? 0 : (abs >= 10 ? 1 : 2);
                    it.text = `${it.text}: ${last.toFixed(decimals)}`;
                  }
                  return it;
                });
              }
            };
          }

          function buildCharts(labels, temp, hum, vpd, extTemp, mainW, alphaTemp, alphaHum, tempRawSeries, humRawSeries){
            if (typeof Chart === 'undefined') {
              txt('status', currentLang === 'de' ? 'Charts konnten nicht geladen werden (Chart.js fehlt).' : 'Charts could not be loaded (Chart.js missing).');
              return;
            }
            if (tempChart) tempChart.destroy();
            if (humChart) humChart.destroy();
            if (vpdChart) vpdChart.destroy();
            if (extTempChart) extTempChart.destroy();
            if (mainWChart) mainWChart.destroy();
            if (alphaChart) alphaChart.destroy();

            const tempUnitLabel = currentTempUnit === 'F' ? '°F' : '°C';

            const tempCtx = document.getElementById('tempChart');
            if (tempCtx) {
              const tTarget = Number.isFinite(targetTempCChart) ? convertTempFromC(targetTempCChart) : null;
              const tempTargetLine = labels.map(() => (Number.isFinite(tTarget) ? Number(tTarget.toFixed(1)) : null));
              tempChart = new Chart(tempCtx, {
                type: 'line',
                data: {
                  labels,
                  datasets: [
                    { label: `${tr('temperature')} ${tempUnitLabel}`, data: temp, borderColor: '#22d3ee', tension: 0.25, pointRadius: 0, pointHoverRadius: 5, pointHitRadius: 18, yAxisID: 'y' },
                    { label: `${tr('rawValue')} ${tr('temperature')} ${tempUnitLabel}`, data: tempRawSeries, borderColor: '#67e8f9', borderDash: [6,4], tension: 0.2, pointRadius: 0, pointHoverRadius: 4, pointHitRadius: 12, yAxisID: 'y' },
                    { label: '', data: temp, borderColor: 'rgba(0,0,0,0)', backgroundColor: 'rgba(0,0,0,0)', tension: 0.25, pointRadius: 0, pointHoverRadius: 0, pointHitRadius: 0, yAxisID: 'yR' },
                    { label: `${tr('target')} ${tempUnitLabel}`, data: tempTargetLine, borderColor: targetLineColor(), borderDash: [6,4], tension: 0, pointRadius: 0, pointHoverRadius: 0, yAxisID: 'y' }
                  ]
                },
                options: {
                  responsive: true,
                  maintainAspectRatio: false,
                  interaction: { mode: 'nearest', intersect: false },
                  scales: {
                    x: { ticks: { color:'#94a3b8' }, grid:{ color:'rgba(148,163,184,.15)' } },
                    y: { position:'left', ticks:{ color:'#22d3ee' }, grid:{ color:'rgba(148,163,184,.15)' }, title: { display: true, text: tempUnitLabel, color:'#cbd5e1' }, afterFit: (scale) => { scale.width = 56; } },
                    yR: { position:'right', ticks:{ color:'#22d3ee' }, grid:{ drawOnChartArea:false }, title: { display:true, text: tempUnitLabel, color:'#cbd5e1' }, afterFit: (scale) => { scale.width = 56; } }
                  },
                  plugins: { legend: { labels: legendLabelsWithCurrent() } }
                }
              });
            }

            const humCtx = document.getElementById('humChart');
            if (humCtx) {
              humChart = new Chart(humCtx, {
                type: 'line',
                data: {
                  labels,
                  datasets: [
                    { label: `${tr('humidity')} %`, data: hum, borderColor: '#a78bfa', tension: 0.25, pointRadius: 0, pointHoverRadius: 5, pointHitRadius: 18, yAxisID: 'y' },
                    { label: `${tr('rawValue')} ${tr('humidity')} %`, data: humRawSeries, borderColor: '#c4b5fd', borderDash: [6,4], tension: 0.2, pointRadius: 0, pointHoverRadius: 4, pointHitRadius: 12, yAxisID: 'y' },
                    { label: '', data: hum, borderColor: 'rgba(0,0,0,0)', backgroundColor: 'rgba(0,0,0,0)', tension: 0.25, pointRadius: 0, pointHoverRadius: 0, pointHitRadius: 0, yAxisID: 'yR' }
                  ]
                },
                options: {
                  responsive: true,
                  maintainAspectRatio: false,
                  interaction: { mode: 'nearest', intersect: false },
                  scales: {
                    x: { ticks: { color:'#94a3b8' }, grid:{ color:'rgba(148,163,184,.15)' } },
                    y: { position:'left', ticks:{ color:'#a78bfa' }, grid:{ color:'rgba(148,163,184,.15)' }, title: { display: true, text: '%', color:'#cbd5e1' }, afterFit: (scale) => { scale.width = 56; } },
                    yR: { position:'right', ticks:{ color:'#a78bfa' }, grid:{ drawOnChartArea:false }, title: { display:true, text: '%', color:'#cbd5e1' }, afterFit: (scale) => { scale.width = 56; } }
                  },
                  plugins: { legend: { labels: legendLabelsWithCurrent() } }
                }
              });
            }

            const vpdCtx = document.getElementById('vpdChart');
            if (vpdCtx) {
              const vpdTargetLine = labels.map(() => (Number.isFinite(targetVpdChart) ? Number(targetVpdChart.toFixed(2)) : null));
              vpdChart = new Chart(vpdCtx, {
                type: 'line',
                data: {
                  labels,
                  datasets: [
                    { label: `${tr('vpd')} kPa`, data: vpd, borderColor: '#f59e0b', tension: 0.25, pointRadius: 0, pointHoverRadius: 5, pointHitRadius: 18, yAxisID: 'y' },
                    { label: '', data: vpd, borderColor: 'rgba(0,0,0,0)', backgroundColor: 'rgba(0,0,0,0)', tension: 0.25, pointRadius: 0, pointHoverRadius: 0, pointHitRadius: 0, yAxisID: 'yR' },
                    { label: `${tr('target')} kPa`, data: vpdTargetLine, borderColor: targetLineColor(), borderDash: [6,4], tension: 0, pointRadius: 0, pointHoverRadius: 0, yAxisID: 'y' }
                  ]
                },
                options: {
                  responsive: true,
                  maintainAspectRatio: false,
                  interaction: { mode: 'nearest', intersect: false },
                  scales: {
                    x: { ticks: { color:'#94a3b8' }, grid:{ color:'rgba(148,163,184,.15)' } },
                    y: { position:'left', ticks:{ color:'#f59e0b' }, grid:{ color:'rgba(148,163,184,.15)' }, title: { display: true, text: 'kPa', color:'#cbd5e1' }, afterFit: (scale) => { scale.width = 56; } },
                    yR: { position:'right', ticks:{ color:'#f59e0b' }, grid:{ drawOnChartArea:false }, title: { display:true, text: 'kPa', color:'#cbd5e1' }, afterFit: (scale) => { scale.width = 56; } }
                  },
                  plugins: { legend: { labels: legendLabelsWithCurrent() } }
                }
              });
            }

            const alphaCtx = document.getElementById('alphaChart');
            if (alphaCtx) {
              alphaChart = new Chart(alphaCtx, {
                type: 'line',
                data: {
                  labels,
                  datasets: [
                    { label: 'α Temp', data: alphaTemp, borderColor: '#84cc16', tension: 0, pointRadius: 0, pointHoverRadius: 4, pointHitRadius: 12, yAxisID: 'y' },
                    { label: 'α Hum', data: alphaHum, borderColor: '#eab308', tension: 0, pointRadius: 0, pointHoverRadius: 4, pointHitRadius: 12, yAxisID: 'yR' }
                  ]
                },
                options: {
                  responsive: true,
                  maintainAspectRatio: false,
                  interaction: { mode: 'nearest', intersect: false },
                  scales: {
                    x: { ticks: { color:'#94a3b8' }, grid:{ color:'rgba(148,163,184,.15)' } },
                    y: { position:'left', min:0, max:0.4, ticks:{ color:'#84cc16' }, grid:{ color:'rgba(148,163,184,.15)' }, title: { display: true, text: 'α Temp', color:'#cbd5e1' }, afterFit: (scale) => { scale.width = 56; } },
                    yR: { position:'right', min:0, max:0.4, ticks:{ color:'#eab308' }, grid:{ drawOnChartArea:false }, title: { display: true, text: 'α Hum', color:'#cbd5e1' }, afterFit: (scale) => { scale.width = 56; } }
                  },
                  plugins: { legend: { labels: legendLabelsWithCurrent() } }
                }
              });
            }
            extTempChart = buildSingleChart('extTempChart', labels, `${extTempLabelBase()} ${tempUnitLabel}`, extTemp, '#10b981', tempUnitLabel);
            mainWChart = buildSingleChart('mainWChart', labels, `${tr('totalConsumption')} W`, mainW, '#ef4444', 'W', 0);
          }

          async function loadLatest(){
            const r = await fetch(`/tents/${currentTentId}/latest`, { cache:'no-store' });
            const j = await r.json();
            let d = j.latest || {};
            if (!shellyMainDirectTs && j?.captured_at) shellyMainDirectTs = j.captured_at;

            if ((!d || Object.keys(d).length === 0) && lastGoodLatestPayload) {
              d = { ...lastGoodLatestPayload };
              if (!j?.captured_at && lastGoodCapturedAt) j.captured_at = lastGoodCapturedAt;
            }

            // Read configured Shelly devices directly, but do not block initial UI render.
            // Slow/unreachable Shelly calls must not delay first values on page load.
            (async () => {
              try {
                const ctrl = new AbortController();
                const to = setTimeout(() => ctrl.abort(), 1200);
                const dr = await fetch(`/tents/${currentTentId}/shelly/direct-all`, { cache:'no-store', signal: ctrl.signal });
                clearTimeout(to);
                const dj = await dr.json().catch(() => ({}));
                if (dr.ok && dj?.ok && dj?.states) {
                  Object.entries(dj.states).forEach(([k, st]) => {
                    d[`cur.shelly.${k}.isOn`] = st?.isOn;
                    if (Number.isFinite(Number(st?.Watt))) d[`cur.shelly.${k}.Watt`] = st.Watt;
                    if (Number.isFinite(Number(st?.Wh))) d[`cur.shelly.${k}.Wh`] = st.Wh;
                  });
                  if (dj?.states?.main) shellyMainDirectTs = dj?.checked_at || new Date().toISOString();
                }
              } catch {}
            })();

            renderStream(j.rtsp_url, j.webrtc_url, j.player_url, j.preview_url);
            txt('status', '');
            if (j?.captured_at) {
              const ageMs = Date.now() - new Date(j.captured_at).getTime();
              if (Number.isFinite(ageMs) && ageMs > (15 * 60 * 1000)) {
                txt('status', currentLang === 'de' ? 'Zeige letzte bekannte Werte (Quelle verzögert/nicht erreichbar).' : 'Showing last known values (source delayed/unreachable).');
              }
            }
            try {
              const sr = await fetch(`/tents/${currentTentId}/shelly/last-switches`, { cache:'no-store' });
              const sj = await sr.json();
              shellyLastSwitches = sj?.last_switches || {};
            } catch {
              shellyLastSwitches = {};
            }

            const boxName = (d['settings.ui.boxName'] || '').toString().trim();
            if (currentTentMeta) {
              currentTentMeta = { ...currentTentMeta, navName: boxName || currentTentMeta.navName, capturedAt: j.captured_at || currentTentMeta.capturedAt };
              renderTentHeader();
            } else {
              txt('titleMain', boxName || tr('title'));
            }
            const tempCur = firstNum(d, ['sensors.cur.temperatureC', 'curTemperature']);
            const humCur  = firstNum(d, ['sensors.cur.humidityPct', 'curHumidity']);
            const vpdRaw  = firstNum(d, ['sensors.cur.vpdKpa', 'curVpd']);
            const extTempRaw = firstNum(d, ['sensors.cur.extTempC']);
            const alphaTemp = firstNum(d, ['sensors.cur.effectiveAlfaTempC']);
            const alphaHum = firstNum(d, ['sensors.cur.effectiveAlfaHumPct']);
            const tempRaw = firstNum(d, ['sensors.cur.temperatureRawC', 'sensors.raw.temperatureC', 'sensors.cur.temperatureC', 'curTemperature']);
            const humRaw = firstNum(d, ['sensors.cur.humidityRawPct', 'sensors.raw.humidityPct', 'sensors.cur.humidityPct', 'curHumidity']);

            const tempNow = convertTempFromC(tempCur);
            const tempRawNow = convertTempFromC(tempRaw);
            const tempUnitLabel = currentTempUnit === 'F' ? '°F' : '°C';
            txt('temp', fmtNum(tempNow, 1) + ' ' + tempUnitLabel);
            txt('hum',  fmtNum(humCur, 1) + ' %');
            txt('vpd',  fmtNum(vpdRaw, 2) + ' kPa');
            if (Object.keys(d || {}).length > 0) {
              const hasCore = Number.isFinite(Number(tempCur)) || Number.isFinite(Number(humCur)) || Number.isFinite(Number(vpdRaw));
              if (hasCore) {
                lastGoodLatestPayload = { ...d };
                lastGoodCapturedAt = j?.captured_at || lastGoodCapturedAt;
                // no local cache persistence in v0.170 mode
              }
            }
            txt('tempRaw', `${tr('rawValue')}: ${fmtNum(tempRawNow, 1)} ${tempUnitLabel}`);
            txt('humRaw', `${tr('rawValue')}: ${fmtNum(humRaw, 1)} %`);
            setAlphaLed('tempAlphaLed', alphaTemp);
            setAlphaLed('humAlphaLed', alphaHum);
            const extTempNow = convertTempFromC(extTempRaw);
            txt('extTemp', fmtNum(extTempNow, 1) + ' ' + tempUnitLabel);
            const latestTs = j.captured_at ? new Date(j.captured_at).getTime() : null;
            txt('tankLastChange', `${tr('lastChange')} ${formatShellyChangeTime(latestTs)}`);
            const extName = (d['sensors.cur.ds18b20Name'] || '').toString().trim();
            extTempSensorName = extName || 'DS18B20';
            txt('lblExtTemp', extTempSensorName);
            txt('lblExtTempHistory', `${extTempLabelBase()} ${currentLang === 'de' ? 'Verlauf' : 'History'}`);
            // main power tile removed

            const tgtTempC = firstNum(d, ['settings.grow.targetTemperature', 'settings.targetTemperature', 'target.targetTempC']);
            targetTempCChart = Number.isFinite(Number(tgtTempC)) ? Number(tgtTempC) : NaN;
            const tgtTemp = Number.isFinite(Number(tgtTempC)) ? convertTempFromC(Number(tgtTempC)) : null;
            txt('tempTarget', `${tr('target')}: ${fmtNum(tgtTemp, 1)} ${tempUnitLabel}`);

            const tgtVpd = firstNum(d, ['settings.grow.targetVPD', 'settings.targetVPD', 'target.targetVpdKpa']);
            targetVpdChart = Number.isFinite(Number(tgtVpd)) ? Number(tgtVpd) : NaN;
            const leafOffset = firstNum(d, ['settings.grow.offsetLeafTemperature']);
            const leafOffsetTxt = Number.isFinite(Number(leafOffset)) ? `${Number(leafOffset).toFixed(2)}°C` : '-';
            const minVpdTxt = (currentExhPlan && Number.isFinite(Number(currentExhPlan.min_vpd_kpa)))
              ? `${Number(currentExhPlan.min_vpd_kpa).toFixed(2)} kPa`
              : '-';
            html('vpdTarget', `<span style="display:flex; justify-content:space-between; gap:8px;"><span style="display:flex; flex-direction:column; gap:2px;"><span>${tr('target')}: ${Number.isFinite(Number(tgtVpd)) ? Number(tgtVpd).toFixed(2) : '-'} kPa</span><span>${tr('minShort')}: ${minVpdTxt}</span></span><span>${tr('leafOffset')}: ${leafOffsetTxt}</span></span>`);
            // gauges disabled by request

            const phase = firstNum(d, ['settings.grow.currentPhase', 'settings.currentPhase', 'grow.currentPhase', 'curPhase']);
            txt('growPhaseValue', phaseLabel(phase));
            const phaseEl = document.getElementById('growPhaseValue');
            if (phaseEl) {
              phaseEl.classList.remove('phase-veg', 'phase-flower', 'phase-dry');
              const cls = phaseClass(phase);
              if (cls) phaseEl.classList.add(cls);
            }

            const growDay = firstNum(d, ['settings.grow.currentGrowDay']);
            const growWeek = firstNum(d, ['settings.grow.currentGrowWeek']);
            const phaseDay = firstNum(d, ['settings.grow.currentPhaseDay']);
            const phaseWeek = firstNum(d, ['settings.grow.currentPhaseWeek']);
            txt('growTotals', `${tr('growSince')}: ${tr('day')} ${Number.isFinite(growDay) ? Number(growDay) : '-'} / ${tr('week')} ${Number.isFinite(growWeek) ? Number(growWeek) : '-'}`);
            const phaseName = phaseLabel(phase);
            txt('growPhaseStats', `${phaseName !== '-' ? phaseName : 'Phase'}: ${tr('day')} ${Number.isFinite(phaseDay) ? Number(phaseDay) : '-'} / ${tr('week')} ${Number.isFinite(phaseWeek) ? Number(phaseWeek) : '-'}`);

            const mainWh = firstNum(d, ['cur.shelly.main.Wh', 'shelly.main.wh']);
            txt('mainEnergyValue', Number.isFinite(Number(mainWh)) ? `${(Number(mainWh) / 1000).toFixed(3)} kWh` : '-');

            const mainCost = firstNum(d, ['cur.shelly.main.Cost', 'shelly.main.cost']);
            txt('mainCostValue', Number.isFinite(Number(mainCost)) ? `${Number(mainCost).toFixed(2)} €` : '-');

            const uptimeEl = document.getElementById('uptimeBadge');
            const uptimeS = firstNum(d, ['sys.uptimeS']);
            if (uptimeEl) {
              if (Number.isFinite(Number(uptimeS))) {
                uptimeEl.style.display = 'inline-block';
                uptimeEl.textContent = `${tr('uptime')}: ${formatUptimeSingleUnit(uptimeS)}`;
              } else {
                uptimeEl.style.display = 'none';
                uptimeEl.textContent = `${tr('uptime')}: -`;
              }
            }

            const rawCount = Number(d['settings.active_relay_count']);
            const c = Number.isFinite(rawCount) ? rawCount : 8;
            const tankCurrentCard = document.getElementById('tankCurrentCard');
            if (tankCurrentCard) tankCurrentCard.style.display = (c === 8) ? 'block' : 'none';
            const rel = document.getElementById('relays');
            const relExtra = document.getElementById('relaysExtra');
            const relaysExtraCard = document.getElementById('relaysExtraCard');
            const irrigationCardActions = document.getElementById('irrigationCardActions');
            const tankCurrentActions = document.getElementById('tankCurrentActions');
            const irrigationCard = document.getElementById('irrigationCard');
            const exhPlanBtn = document.getElementById('openExhVpdPlanBtn');
            rel.innerHTML = '';
            if (relExtra) relExtra.innerHTML = '';
            if (relaysExtraCard) relaysExtraCard.style.display = (c === 8) ? 'block' : 'none';
            if (irrigationCardActions) irrigationCardActions.innerHTML = '';
            if (tankCurrentActions) tankCurrentActions.innerHTML = '';

            if (irrigationCard) irrigationCard.style.display = (c === 8) ? 'block' : 'none';
            if (exhPlanBtn) exhPlanBtn.style.display = (c === 8) ? 'inline-block' : 'none';
            if (c === 8) {
              const runsLeft = firstNum(d, ['irrigation.runsLeft']);
              const timeLeft = d['irrigation.timeLeft'];
              const amount = firstNum(d, ['irrigation.amount']);
              const timePerTask = firstNum(d, ['irrigation.timePerTask']);
              const betweenTasks = firstNum(d, ['irrigation.betweenTasks']);
              const amountTotal = firstNum(d, ['irrigation.amountTotal']);
              const tankLevelCm = firstNum(d, ['irrigation.tankLevelCm']);
              const tankLevelPercent = firstNum(d, ['irrigation.tankLevelPercent']);

              txt('irRunsLeft', `${tr('irRunsLeft')}: ${Number.isFinite(runsLeft) ? Number(runsLeft) : '-'}`);
              const irActiveBadge = document.getElementById('irActiveBadge');
              if (irActiveBadge) irActiveBadge.style.display = (Number.isFinite(runsLeft) && Number(runsLeft) > 0) ? 'inline' : 'none';
              const leftSec = parseDurationToSeconds(timeLeft);
              const finished = (Number.isFinite(leftSec) && leftSec <= 0) || (Number.isFinite(runsLeft) && Number(runsLeft) <= 0);
              const endLabel = finished ? '00:00' : calcEndTimeLabel(timeLeft);
              txt('irTimeLine', `${tr('irTimeLeft')}: ${timeLeft || '-'} · ${tr('irEndAt')}: ${endLabel}`);
              txt('irAmount', `${tr('irAmount')}: ${Number.isFinite(amount) ? Number(amount).toFixed(1) : '-'} ml`);
              txt('irTimePerTask', `${tr('irTimePerTask')}: ${Number.isFinite(timePerTask) ? Number(timePerTask) : '-'} s`);
              txt('irBetweenTasks', `${tr('irBetweenTasks')}: ${Number.isFinite(betweenTasks) ? Number(betweenTasks) : '-'} min`);
              txt('irAmountTotal', `${tr('irAmountTotal')}: ${Number.isFinite(amountTotal) ? Number(amountTotal).toFixed(1) : '-'} ml`);
              txt('tankPercent', `${Number.isFinite(tankLevelPercent) ? Number(tankLevelPercent).toFixed(1) : '-'} %`);
              txt('tankLevelSub', `${tr('tankDistance')}: ${Number.isFinite(tankLevelCm) ? Number(tankLevelCm).toFixed(1) : '-'} cm`);
            } else {
              txt('tankPercent', '- %');
              txt('tankLevelSub', `${tr('tankDistance')}: - cm`);
              const irActiveBadge = document.getElementById('irActiveBadge');
              if (irActiveBadge) irActiveBadge.style.display = 'none';
            }

            // Combined status + toggle in one line for relay 1..5 only.
            const relayControlCount = Math.min(Math.max(c, 0), 5);
            for (let i = 0; i < relayControlCount; i++) {
              const relayIdx = i + 1;
              const rawState = d[`relays[${i}].state`];
              const st = (rawState === true || rawState === 1 || rawState === '1' || String(rawState).toLowerCase() === 'true');
              const name = d[`relays[${i}].name`] || `${tr('relay')} ${relayIdx}`;
              const btn = document.createElement('button');
              btn.className = 'relay ' + (st ? 'on' : 'off');
              btn.textContent = `${name}: ${st ? tr('on') : tr('off')}`;
              btn.addEventListener('click', async () => {
                await toggleRelay(relayIdx);
              });
              rel.appendChild(btn);
            }

            // Extra relays 6..8 for 8x boards in a separate card with same layout.
            if (c === 8 && relExtra) {
              for (let i = 5; i < 8; i++) {
                const relayIdx = i + 1;
                const rawState = d[`relays[${i}].state`];
                const st = (rawState === true || rawState === 1 || rawState === '1' || String(rawState).toLowerCase() === 'true');
                const name = d[`relays[${i}].name`] || `${tr('relay')} ${relayIdx}`;
                const btn = document.createElement('button');
                btn.className = 'relay ' + (st ? 'on' : 'off');
                btn.textContent = `${name}: ${st ? tr('on') : tr('off')}`;
                btn.addEventListener('click', async () => {
                  await triggerPump10s(relayIdx);
                });
                relExtra.appendChild(btn);
              }
            }

            // Irrigation actions only for 8x relay setup.
            if (c === 8) {
              const startBtn = document.createElement('button');
              startBtn.textContent = tr('startWatering');
              startBtn.addEventListener('click', async () => {
                await startWatering();
              });
              if (irrigationCardActions) irrigationCardActions.appendChild(startBtn);

              const planBtn = document.createElement('button');
              planBtn.id = 'openIrPlanBtn';
              planBtn.textContent = tr('irrigationPlan');
              planBtn.addEventListener('click', async () => {
                await openDashboardIrPlanModal();
              });
              if (irrigationCardActions) irrigationCardActions.appendChild(planBtn);

              const pingBtn = document.createElement('button');
              pingBtn.textContent = tr('pingTank');
              pingBtn.addEventListener('click', async () => {
                await pingTank();
              });
              if (tankCurrentActions) tankCurrentActions.appendChild(pingBtn);
            }

            await refreshPlanButtonStates();
            if (c === 8) {
              const nextDt = computeNextIrrigationDate(currentIrPlan, currentIrLastRunDate, d['settings.shelly.light.line']);
              const lastRunLabel = formatLastRunDate(currentIrLastRunDate);
              txt('irNextRun', `${tr('irNextRun')}: ${formatNextRunDate(nextDt)} · ${tr('lastShort')}: ${lastRunLabel}`);
            } else {
              txt('irNextRun', `${tr('irNextRun')}: -`);
            }
            renderShellyDevices(d);
          }

          async function loadHistory(){
            const minutes = Number(localStorage.getItem('gt_range_minutes') || '60');

            const fetchHistory = async (m) => {
              const r = await fetch(`/tents/${currentTentId}/history?minutes=${m}`, { cache:'no-store' });
              if (!r.ok) throw new Error(`history ${r.status}`);
              return r.json();
            };

            let usedMinutes = minutes;
            let j = await fetchHistory(usedMinutes);
            let points = j.points || [];

            // Robust fallback: if no points in selected window, use the widest window.
            if (!points.length && usedMinutes < 10080) {
              usedMinutes = 10080;
              j = await fetchHistory(usedMinutes);
              points = j.points || [];
            }

            const nowLocal = new Date();
            const startLocal = new Date(nowLocal);
            startLocal.setHours(0, 0, 0, 0);
            const minutesSinceMidnight = Math.max(5, Math.ceil((nowLocal - startLocal) / 60000) + 1);

            // For "today" consumption, always use data since 00:00 local time,
            // independent from the currently selected chart range.
            let pointsToday = points;
            if (usedMinutes < minutesSinceMidnight) {
              try {
                const jToday = await fetchHistory(minutesSinceMidnight);
                pointsToday = jToday.points || [];
              } catch {
                pointsToday = points;
              }
            }

            const isSameLocalDay = (isoTs) => {
              const d = new Date(isoTs);
              return d.getFullYear() === nowLocal.getFullYear()
                && d.getMonth() === nowLocal.getMonth()
                && d.getDate() === nowLocal.getDate();
            };
            const todayPoints = pointsToday
              .filter(p => p && p.t && isSameLocalDay(p.t));
            const todayWh = todayPoints
              .map(p => Number(p.mainWh))
              .filter(v => Number.isFinite(v));
            const todayCost = todayPoints
              .map(p => Number(p.mainCost))
              .filter(v => Number.isFinite(v));
            if (todayWh.length >= 2) {
              const startWh = todayWh[0];
              const endWh = todayWh[todayWh.length - 1];
              const deltaWh = endWh - startWh;
              let costPart = '- €';
              if (todayCost.length >= 2) {
                const deltaCost = todayCost[todayCost.length - 1] - todayCost[0];
                costPart = Number.isFinite(deltaCost) && deltaCost >= 0 ? `${deltaCost.toFixed(2)} €` : '- €';
              }
              const energyPart = Number.isFinite(deltaWh) && deltaWh >= 0 ? `${(deltaWh / 1000).toFixed(3)} kWh` : '- kWh';
              txt('mainKwhTodayValue', `${energyPart} / ${costPart}`);
            } else {
              txt('mainKwhTodayValue', '- kWh / - €');
            }

            const tempChangeTs = getLastMetricChangeTimestamp(points, 'temp');
            const humChangeTs = getLastMetricChangeTimestamp(points, 'hum');
            const vpdChangeTs = getLastMetricChangeTimestamp(points, 'vpd');
            const extTempChangeTs = getLastMetricChangeTimestamp(points, 'extTemp');
            txt('tempLastChange', `${tr('lastChange')} ${formatShellyChangeTime(tempChangeTs)}`);
            txt('humLastChange', `${tr('lastChange')} ${formatShellyChangeTime(humChangeTs)}`);
            txt('vpdLastChange', `${tr('lastChange')} ${formatShellyChangeTime(vpdChangeTs)}`);
            txt('extTempLastChange', `${tr('lastChange')} ${formatShellyChangeTime(extTempChangeTs)}`);

            if (!points.length) {
              txt('status', currentLang === 'de' ? 'Keine Verlaufsdaten verfügbar.' : 'No history data available.');
              setHistoryOverlays('');
              buildCharts([], [], [], [], [], [], [], [], [], []);
              return;
            }
            const historyWarmup = points.length < 30;
            if (historyWarmup) {
              txt('status', '');
              const remaining = Math.max(0, 30 - points.length);
              const warmupMsg = currentLang === 'de'
                ? `${tr('historyBuilding')} (${remaining} Messpunkt${remaining === 1 ? '' : 'e'} verbleibend)`
                : `${tr('historyBuilding')} (${remaining} data point${remaining === 1 ? '' : 's'} remaining)`;
              setHistoryOverlays(warmupMsg);
            } else {
              setHistoryOverlays('');
              txt('status', usedMinutes !== minutes ? (currentLang === 'de' ? 'Keine aktuellen Daten im gewählten Zeitraum, zeige letzte verfügbare Daten.' : 'No recent data in selected range, showing last available data.') : '');
            }

            const labels = points.map(p => {
              const d = new Date(p.t);
              return usedMinutes > 1440
                ? d.toLocaleDateString([], { day:'2-digit', month:'2-digit' }) + ' ' + d.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' })
                : d.toLocaleTimeString([], { hour:'2-digit', minute:'2-digit' });
            });
            const temp = points.map(p => {
              const c = Number(p.temp);
              if (!Number.isFinite(c)) return null;
              const converted = convertTempFromC(c);
              return Number.isFinite(converted) ? Number(converted.toFixed(1)) : null;
            });
            const hum  = points.map(p => {
              const h = Number(p.hum);
              return Number.isFinite(h) ? Number(h.toFixed(1)) : null;
            });
            const tempRawSeries = points.map(p => {
              const c = Number(p.temperature_raw);
              if (!Number.isFinite(c)) return null;
              const converted = convertTempFromC(c);
              return Number.isFinite(converted) ? Number(converted.toFixed(1)) : null;
            });
            const humRawSeries = points.map(p => {
              const h = Number(p.humidity_raw);
              return Number.isFinite(h) ? Number(h.toFixed(1)) : null;
            });
            const vpd  = points.map(p => {
              const v = Number(p.vpd);
              return Number.isFinite(v) ? Number(v.toFixed(2)) : null;
            });
            const extTemp = points.map(p => {
              const c = Number(p.extTemp);
              if (!Number.isFinite(c)) return null;
              const converted = convertTempFromC(c);
              return Number.isFinite(converted) ? Number(converted.toFixed(1)) : null;
            });
            const mainW = points.map(p => {
              const w = Number(p.mainW);
              return Number.isFinite(w) ? Number(w.toFixed(1)) : null;
            });
            const alphaTemp = points.map(p => {
              const a = Number(p.effectiveAlfaTempC);
              return Number.isFinite(a) ? Number(a.toFixed(3)) : null;
            });
            const alphaHum = points.map(p => {
              const a = Number(p.effectiveAlfaHumPct);
              return Number.isFinite(a) ? Number(a.toFixed(3)) : null;
            });
            buildCharts(labels, temp, hum, vpd, extTemp, mainW, alphaTemp, alphaHum, tempRawSeries, humRawSeries);
          }

          async function loadTentNav(){
            const nav = document.getElementById('tentNav');
            if (!nav) return;

            try {
              const res = await fetch('/tents', { cache: 'no-store' });
              const tents = await res.json();
              if (!Array.isArray(tents) || tents.length === 0) {
                nav.innerHTML = `<div class="small">${tr('tents')}: -</div>`;
                return;
              }

              const hasCurrent = tents.some(t => Number(t.id) === Number(currentTentId));
              if (!hasCurrent) currentTentId = Number(tents[0].id);
              localStorage.setItem('gt_tent_id', String(currentTentId));

              // Enrich nav labels with box name and last successful capture from /latest payload.
              const enriched = await Promise.all(tents.map(async (t) => {
                try {
                  const lr = await fetch(`/tents/${t.id}/latest`, { cache: 'no-store' });
                  if (!lr.ok) return { ...t, navName: t.name, capturedAt: null };
                  const lj = await lr.json();
                  const boxName = (lj?.latest?.['settings.ui.boxName'] || '').toString().trim();
                  return { ...t, navName: boxName || t.name, capturedAt: lj?.captured_at || null };
                } catch {
                  return { ...t, navName: t.name, capturedAt: null };
                }
              }));

              const nextNavHtml = enriched.map(t => {
                const active = Number(t.id) === Number(currentTentId);
                const online = getTentOnlineState(t.capturedAt);
                const statusLabel = online ? tr('online') : tr('offline');
                const statusClass = online ? 'status-online' : 'status-offline';
                return `<a class="navlink ${active ? 'active' : ''}" href="/app?page=dashboard&tent=${t.id}">${escHtml(t.navName)} <span class="${statusClass}">${escHtml(statusLabel)}</span></a>`;
              }).join('');
              if (nav.innerHTML !== nextNavHtml) nav.innerHTML = nextNavHtml;

              const active = enriched.find(t => Number(t.id) === Number(currentTentId));
              if (active) {
                currentTentMeta = active;
                renderTentHeader();
              }
            } catch (e) {
              // ignore nav errors in UI and keep previous state
            }
          }

          async function refresh(){
            try {
              await loadTentNav();
              await loadLatest();
              await loadHistory();
            } catch(e){
              txt('status', `${tr('loadFailed')}: ` + (e?.message || e));
            }
          }

          const langEl = document.getElementById('langSelect');
          if (langEl) {
            langEl.value = currentLang;
            langEl.addEventListener('change', async (ev) => {
              currentLang = ev.target.value === 'de' ? 'de' : 'en';
              localStorage.setItem('gt_lang', currentLang);
              applyI18n();
              await refresh();
            });
          }

          const unitEl = document.getElementById('tempUnitSelect');
          if (unitEl) {
            unitEl.value = (currentTempUnit === 'F') ? 'F' : 'C';
            unitEl.addEventListener('change', async (ev) => {
              currentTempUnit = ev.target.value === 'F' ? 'F' : 'C';
              localStorage.setItem('gt_temp_unit', currentTempUnit);
              await refresh();
            });
          }

          const rangeLiveEl = document.getElementById('rangeSelectLive');
          const rangeHintLiveEl = document.getElementById('rangeHintLive');
          const setRangeHint = (msg = '') => {
            if (!rangeHintLiveEl) return;
            rangeHintLiveEl.textContent = msg;
            if (msg) rangeHintLiveEl.classList.add('range-hint-error');
            else rangeHintLiveEl.classList.remove('range-hint-error');
          };
          if (rangeLiveEl) {
            // Always start dashboard history on 24h at page load.
            let activeRange = '60';
            localStorage.setItem('gt_range_minutes', activeRange);
            rangeLiveEl.value = activeRange;
            rangeLiveEl.addEventListener('change', async (ev) => {
              const nextRange = ['60','1440','2880'].includes(ev.target.value) ? ev.target.value : '1440';
              try {
                const r = await fetch(`/tents/${currentTentId}/history?minutes=${encodeURIComponent(nextRange)}&filter_spikes=1`, { cache:'no-store' });
                const j = await r.json().catch(() => ({}));
                const pts = Array.isArray(j?.points) ? j.points : [];
                if (!pts.length) {
                  setRangeHint(currentLang === 'de'
                    ? 'Keine Daten im gewählten Zeitraum verfügbar.'
                    : 'No data available in selected range.');
                  rangeLiveEl.value = activeRange;
                  return;
                }
              } catch {
                setRangeHint(currentLang === 'de'
                  ? 'Zeitraumwechsel fehlgeschlagen.'
                  : 'Range switch failed.');
                rangeLiveEl.value = activeRange;
                return;
              }
              setRangeHint('');
              activeRange = nextRange;
              localStorage.setItem('gt_range_minutes', nextRange);
              await loadHistory();
            });
          }

          const viewModeBtnEl = document.getElementById('viewModeBtn');
          if (viewModeBtnEl) {
            viewModeBtnEl.addEventListener('click', () => {
              viewMode = (viewMode === 'mobile') ? 'desktop' : 'mobile';
              localStorage.setItem('gt_view_mode', viewMode);
              applyViewMode();
            });
          }

          const exportBtnEl = document.getElementById('exportCsvBtn');
          if (exportBtnEl) {
            exportBtnEl.addEventListener('click', () => {
              const mins = Number(localStorage.getItem('gt_range_minutes') || '60');
              let rangeKey = String(mins);
              if (mins === 1440) rangeKey = '24h';
              if (mins === 10080) rangeKey = '7d';
              if (mins > 10080) rangeKey = 'all';
              const url = `/api/export?tent_id=${encodeURIComponent(String(currentTentId))}&range=${encodeURIComponent(rangeKey)}`;
              window.location.href = url;
            });
          }

          function applyGuestModeUi(){
            document.body.classList.remove('role-pending', 'role-guest', 'role-admin');
            if (isGuestMode) {
              document.body.classList.add('role-guest');
            } else {
              document.body.classList.add('role-admin');
            }
            document.querySelectorAll('button').forEach(btn => {
              const id = btn.id || '';
              const keep = (id === 'viewModeBtn' || id === 'mobileNavToggle');
              btn.disabled = isGuestMode && !keep;
            });
          }

          const mobileNavBtnEl = document.getElementById('mobileNavToggle');
          if (mobileNavBtnEl) {
            mobileNavBtnEl.addEventListener('click', () => {
              mobileNavExpanded = !mobileNavExpanded;
              syncMobileNavUi();
            });
          }
          window.addEventListener('resize', () => {
            if (!window.matchMedia('(max-width: 1024px)').matches && viewMode !== 'mobile') {
              mobileNavExpanded = false;
            }
            syncMobileNavUi();
          });

          (async () => {
            try {
              const r = await fetch('/auth/whoami', { cache:'no-store' });
              const j = await r.json().catch(() => ({}));
              isGuestMode = (j?.role === 'guest');
            } catch {
              isGuestMode = false;
            }
            applyGuestModeUi();
            applyThemeFromStorage();
            applyI18n();
            await refresh();
            setInterval(async () => { await refresh(); applyGuestModeUi(); }, 30000);
          })();
        </script>
      </body>
    </html>
    """

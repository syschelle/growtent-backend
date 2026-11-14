"""ESP-owned VPD channels. Never calculate, smooth or forward-fill a VPD."""
import math


def finite_number(value):
    if isinstance(value, bool) or value is None or not isinstance(value, (int, float, str)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def vpd_number(value):
    number = finite_number(value)
    return number if number is not None and number >= 0 else None


def _climate_available(payload):
    if "sensors.climate.fresh" in payload and payload["sensors.climate.fresh"] is not True:
        return False
    return "sensors.climate.status" not in payload or payload["sensors.climate.status"] == "ok"


def esp_control_vpd(payload):
    data = payload or {}
    if not _climate_available(data):
        return None
    return vpd_number(data.get("sensors.cur.vpdKpa"))


def esp_raw_vpd(payload):
    data = payload or {}
    if not _climate_available(data):
        return None
    key = "sensors.cur.vpdRawKpa" if "sensors.cur.vpdRawKpa" in data else "sensors.raw.vpdKpa"
    return vpd_number(data.get(key))


def normalise_vpd_channels(payload):
    data = dict(payload or {})
    control, raw = esp_control_vpd(data), esp_raw_vpd(data)
    data["sensors.cur.vpdKpa"] = control
    data["sensors.smoothed.vpdKpa"] = control  # compatibility alias, not another calculation
    data["sensors.cur.vpdRawKpa"] = raw
    data["sensors.raw.vpdKpa"] = raw
    data["backend.vpd.source"] = "esp_current" if control is not None else "unavailable"
    return data

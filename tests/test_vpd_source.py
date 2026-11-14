"""ESP-owned VPD across ingestion, latest/history and exports, no live DB/device."""
import ast
import copy
import json
import math
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request
from fastapi.responses import Response
from services.vpd_channels import finite_number, esp_control_vpd, esp_raw_vpd, normalise_vpd_channels


@pytest.mark.parametrize("value", [None, True, False, "", " ", "bad", float("nan"), float("inf"), -float("inf"), -0.01, {}, []])
def test_invalid_control_never_falls_back(value):
    payload={"sensors.cur.vpdKpa":value,"sensors.smoothed.vpdKpa":1.069,"sensors.cur.vpdRawKpa":0.94,"curVpd":2}
    assert esp_control_vpd(payload) is None
    assert normalise_vpd_channels(payload)["sensors.smoothed.vpdKpa"] is None


@pytest.mark.parametrize("value", [0, 0.94, 1.175, "1.17"])
def test_exact_current_channel_wins(value):
    payload={"sensors.cur.vpdKpa":value,"sensors.smoothed.vpdKpa":1.069,"sensors.cur.vpdRawKpa":0.91}
    before=copy.deepcopy(payload);result=normalise_vpd_channels(payload)
    assert result["sensors.cur.vpdKpa"]==float(value)==result["sensors.smoothed.vpdKpa"]
    assert result["sensors.raw.vpdKpa"]==0.91
    assert payload==before


@pytest.mark.parametrize("flag", [{"sensors.climate.fresh":False},{"sensors.climate.status":"stale"},{"sensors.climate.status":"invalid"},{"sensors.climate.status":"unavailable"}])
def test_explicit_sensor_invalidity_blocks_numeric_channels(flag):
    p={"sensors.cur.vpdKpa":0.94,"sensors.cur.vpdRawKpa":0.95,**flag}
    assert esp_control_vpd(p) is None and esp_raw_vpd(p) is None


class Database:
    def __init__(self, rows=()):self.rows=list(rows);self.statements=[]
    @contextmanager
    def connection(self):yield self
    @contextmanager
    def cursor(self):yield self
    def execute(self, sql, args=None):
        self.statements.append((sql,args))
        if sql.lstrip().startswith("INSERT"):
            self.rows.append((args[1],json.loads(args[2])))
    def fetchall(self):return self.rows
    def fetchone(self):
        ts,p=self.rows[-1]
        return (None,{},ts,p)


def functions(db):
    wanted={"_to_float","_sensor_values_valid","save_state","history_state","_despike_series","_iso_utc_z","export_history_csv","api_history_for_device","latest_state","_try_run_exhaust_vpd_control"}
    tree=ast.parse((Path(__file__).parents[1]/"api/app.py").read_text())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    for n in nodes:n.decorator_list=[]
    ns={"get_conn":db.connection,"datetime":datetime,"timezone":timezone,"timedelta":timedelta,"json":json,"math":math,"Request":Request,
        "HTTPException":HTTPException,"Response":Response,"RETENTION_DAYS":30,"TEMP_MIN_C":-20,"TEMP_MAX_C":80,"VPD_MIN_KPA":0,"VPD_MAX_KPA":6,
        "_finite_sensor_number":finite_number,"_esp_control_vpd":esp_control_vpd,"_esp_raw_vpd":esp_raw_vpd,"_normalise_vpd_channels":normalise_vpd_channels,
        "SENSOR_INIT":{},"_get_last_payload":lambda _: {"sensors.smoothed.vpdKpa":9,"sensors.raw.vpdKpa":8,"sensors.smoothed.temperatureC":21.9,"sensors.smoothed.humidityPct":55.4},
        "_normalise_pot_strains":lambda p:p or {},"_resolve_tent_id_by_device_id":lambda _:2,"load_auth_config":lambda:{"history_api_enabled":True},
        "LOGGER":SimpleNamespace(info=lambda *a:None,warning=lambda *a:None,exception=lambda *a:None)}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),"api/app.py","exec"),ns)
    return ns


def sample(vpd=0.94, **extra):
    return {"sensors.cur.temperatureRawC":21.95,"sensors.cur.humidityRawPct":55.5,
        "sensors.cur.temperatureC":21.9,"sensors.cur.humidityPct":55.4,
        "sensors.cur.vpdKpa":vpd,"sensors.cur.vpdRawKpa":0.93,
        "sensors.smoothed.vpdKpa":1.0689774430586394,"settings.grow.offsetLeafTemperature":-1.5,**extra}


def test_ingestion_retains_esp_value_without_formula_or_previous_vpd():
    db=Database();ns=functions(db);p=sample();before=copy.deepcopy(p)
    ns["save_state"](2,p)
    stored=db.rows[-1][1]
    assert stored["sensors.cur.vpdKpa"]==stored["sensors.smoothed.vpdKpa"]==0.94
    assert stored["sensors.raw.vpdKpa"]==0.93 and p==before
    for v in (None,float("nan"),float("inf"),True,-1):
        ns["save_state"](2,sample(v))
        stored=db.rows[-1][1]
        assert stored["sensors.cur.vpdKpa"] is None
        assert stored["sensors.smoothed.vpdKpa"] is None
        assert stored["backend.vpd.source"]=="unavailable"


@pytest.mark.parametrize("filter_spikes", [0,1])
def test_history_keeps_esp_values_and_explicit_gaps_even_when_raw_is_absent(filter_spikes):
    ts=datetime(2026,11,14,17,tzinfo=timezone.utc)
    payloads=[sample(0.94),sample(None),sample(3.25),{},sample(0),sample(0.96)]
    rows=[(ts.replace(second=i),p) for i,p in enumerate(payloads)]
    before=copy.deepcopy(rows);db=Database(rows);ns=functions(db)
    points=ns["history_state"](2,minutes=360,filter_spikes=filter_spikes)["points"]
    assert [p["vpd"] for p in points]==[0.94,None,3.25,None,0,0.96]
    assert [p["vpd_smoothed"] for p in points]==[p["vpd"] for p in points]
    assert [p["t"] for p in points]==[ts.isoformat() for ts,_ in rows]
    assert rows==before and db.rows==before
    assert all(sql.lstrip().startswith("SELECT") for sql,_ in db.statements)


def test_latest_and_both_history_exports_share_the_esp_channel():
    ts=datetime.now(timezone.utc);db=Database([(ts,sample(0.94)),(ts,sample(None))]);ns=functions(db)
    latest=ns["latest_state"](2,SimpleNamespace(headers={"host":"backend.invalid"}))["latest"]
    assert latest["sensors.cur.vpdKpa"] is None and latest["sensors.smoothed.vpdKpa"] is None
    exported=json.loads(ns["export_history_csv"](2).body)
    api=ns["api_history_for_device"]("test-device",limit=50)
    assert [p["vpd"] for p in exported["points"]]==[0.94,None]
    assert [p["vpd"] for p in api["points"]]==[0.94,None]
    assert db.rows[-1][1]["sensors.smoothed.vpdKpa"]==1.0689774430586394


def test_fifty_sample_regression_does_not_select_recomputed_backend_channel():
    ts=datetime.now(timezone.utc)
    rows=[(ts,sample(0.9+i/1000)) for i in range(50)]
    ns=functions(Database(rows));points=ns["history_state"](2)["points"]
    assert [p["vpd"] for p in points]==[0.9+i/1000 for i in range(50)]
    assert all(p["vpd"]!=1.0689774430586394 for p in points)


def test_incomplete_history_rows_keep_json_safe_climate_gaps():
    ts=datetime.now(timezone.utc)
    p=sample(None,**{"sensors.cur.temperatureRawC":float("inf"),"sensors.cur.humidityRawPct":float("nan"),"sensors.smoothed.temperatureC":float("inf")})
    ns=functions(Database([(ts,p)]));point=ns["history_state"](2)["points"][0]
    assert point["vpd"] is None and point["temperature_raw"] is None and point["temperature_smoothed"] is None
    json.dumps(point,allow_nan=False)


@pytest.mark.parametrize("value",[None,True,float("inf"),float("nan"),-1])
def test_invalid_vpd_does_not_trigger_backend_exhaust_network_io(value):
    db=Database();ns=functions(db)
    def forbidden(*args):raise AssertionError("No Shelly action is allowed without valid ESP VPD")
    ns["_read_exhaust_shelly_output"]=forbidden;ns["_set_exhaust_shelly_output"]=forbidden
    ns["_try_run_exhaust_vpd_control"]({"id":2,"exhaust_vpd_plan":{"enabled":True}},sample(value,**{"settings.shelly.exhaust.ip":"192.0.2.1"}))
    assert not db.statements

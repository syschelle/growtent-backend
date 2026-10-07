import ast
import json
from pathlib import Path

from fastapi import HTTPException
from models.schemas import TentPayload


def _load_normalizer():
    source_path = Path(__file__).resolve().parents[1] / "api" / "db" / "crud.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_normalise_soil_sensor_hosts"
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "json": json,
        "HTTPException": HTTPException,
        "normalize_air_sensor_host": lambda value: str(value).strip() or None,
        "validate_safe_sensor_host": lambda value: str(value).strip() or None,
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["_normalise_soil_sensor_hosts"]


_normalise_soil_sensor_hosts = _load_normalizer()


def test_soil_sensor_slots_preserve_empty_positions():
    assert _normalise_soil_sensor_hosts(["", "192.168.1.42", ""]) == ["", "192.168.1.42", ""]


def test_soil_sensor_slots_keep_pot_three_assignment():
    assert _normalise_soil_sensor_hosts(["", "", "192.168.1.43"]) == ["", "", "192.168.1.43"]


def test_tent_payload_does_not_compact_soil_sensor_slots():
    payload = TentPayload(
        name="Tent",
        source_url="http://192.168.1.10",
        soil_sensors=["", "192.168.1.42", ""],
    )
    assert payload.soil_sensors == ["", "192.168.1.42", ""]


def test_duplicate_soil_sensor_host_does_not_shift_later_slot():
    assert _normalise_soil_sensor_hosts(["192.168.1.42", "192.168.1.42", "192.168.1.43"]) == [
        "192.168.1.42",
        "",
        "192.168.1.43",
    ]

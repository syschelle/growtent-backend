import ast
import csv
import io
import os
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "api" / "app.py"


def _load_csv_helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted_assigns = {
        "STRAINS_CSV_COLUMNS",
        "STRAIN_FIELD_TO_CSV",
        "STRAIN_CSV_ALIASES",
        "STRAIN_PAYLOAD_ALIASES",
        "STRAINS_CSV_IMPORT_MAX_BYTES",
    }
    wanted_functions = {
        "_first_str",
        "_normalise_strain",
        "_normalise_genetics",
        "_parse_strains_csv_text",
        "_parse_strains_csv_bytes",
    }
    body = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            names = []
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node.target, ast.Name):
                names = [node.target.id]
            if any(name in wanted_assigns for name in names):
                body.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
            body.append(node)
    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"csv": csv, "io": io, "os": os}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


def test_export_format_with_multiline_fields_roundtrips():
    ns = _load_csv_helpers()
    csv_data = (
        'Name,Genetics,THC,CBD,Effects,Aroma\r\n'
        'Cereal Milk,50/50,20–26 %,< 1%,"line one\nline two","milk\nvanilla"\r\n'
    ).encode("utf-8")
    rows = ns["_parse_strains_csv_bytes"](csv_data)
    assert len(rows) == 1
    assert rows[0]["name"] == "Cereal Milk"
    assert rows[0]["genetics"] == "50/50"
    assert rows[0]["effects"] == "line one\nline two"
    assert rows[0]["aroma"] == "milk\nvanilla"


def test_duplicate_names_are_rejected_case_insensitively():
    ns = _load_csv_helpers()
    csv_data = (
        'Name,Genetics,THC,CBD,Effects,Aroma\n'
        'AK-47,Sativa,20%,,A,B\n'
        'ak-47,Sativa,21%,,A,B\n'
    ).encode("utf-8")
    try:
        ns["_parse_strains_csv_bytes"](csv_data)
    except ValueError as exc:
        assert "duplicate strain name" in str(exc)
    else:
        raise AssertionError("duplicate strain name should be rejected")


def test_name_header_is_required():
    ns = _load_csv_helpers()
    try:
        ns["_parse_strains_csv_bytes"](b'Genetics,THC\nSativa,20%\n')
    except ValueError as exc:
        assert "missing column: Name" in str(exc)
    else:
        raise AssertionError("missing Name header should be rejected")


def test_production_modular_router_exposes_csv_import_endpoint():
    routes = (Path(__file__).resolve().parents[1] / "api" / "routes" / "tents.py").read_text(encoding="utf-8")
    assert "@router.post('/strains/import.csv')" in routes
    assert "await legacy.import_strains_csv(request)" in routes

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
    schemas = SOURCE.parent / "models" / "schemas.py"
    normalizer = next(n for n in ast.parse(schemas.read_text(encoding="utf-8")).body if isinstance(n, ast.FunctionDef) and n.name == "normalize_flowering_weeks")
    module.body.insert(0, normalizer)
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
    assert "@router.post('/strains/import.csv', dependencies=[Depends(_admin_username)])" in routes
    assert "await legacy.import_strains_csv(request)" in routes


def test_flowering_category_csv_and_legacy():
    ns = _load_csv_helpers()
    parse = ns["_parse_strains_csv_text"]
    assert [r["flowering_weeks"] for r in parse("Name,FloweringWeeks\nA,short\nB,medium\nC,long\nD,\n")] == ["short", "medium", "long", ""]
    assert [r["flowering_weeks"] for r in parse("Name,Blütezeit\nA,Kurz\nB,Mittel\nC,Lang\n")] == ["short", "medium", "long"]
    assert "flowering_weeks" not in parse("Name,THC\nA,20%\n")[0]
    assert ns["_normalise_strain"]({"name": "A"})["flowering_weeks"] == ""
    for value in ("9", "8-10", "invalid"):
        try:
            parse(f"Name,FloweringWeeks\nA,{value}\n")
        except ValueError as exc:
            assert "row 2" in str(exc)
        else:
            raise AssertionError("invalid category accepted")


def test_flowering_ui_and_dashboard_localization():
    source = SOURCE.read_text(encoding="utf-8")
    for value in ("short", "medium", "long"):
        assert f'<option value="{value}" id="floweringWeeks' in source
    for label in ("Kurz – bis 8 Wochen", "Mittel – 9–10 Wochen", "Lang – ab 11 Wochen", "Short – up to 8 weeks", "Medium – 9–10 weeks", "Long – from 11 weeks"):
        assert source.count(label) == 2
    assert "flowering_weeks=COALESCE(%s, flowering_weeks)" in source
    assert "ALTER TABLE strains ADD COLUMN IF NOT EXISTS flowering_weeks" in source


def test_strain_payload_category_validation():
    from models.schemas import StrainPayload
    from pydantic import ValidationError
    import pytest

    base = {"name": "Example", "genetics": "50/50"}
    assert StrainPayload(**base).flowering_weeks is None
    for raw, canonical in [("", ""), ("Kurz", "short"), ("medium", "medium"), ("Lang", "long")]:
        assert StrainPayload(**base, flowering_weeks=raw).flowering_weeks == canonical
    for raw in ("8-10", 9, "unknown"):
        with pytest.raises(ValidationError):
            StrainPayload(**base, flowering_weeks=raw)

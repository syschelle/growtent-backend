"""Regression tests for secure, unfiltered 24-hour ESP heap CSV export."""
import ast
import csv
import io
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import Response

SOURCE = (Path(__file__).parents[1] / 'api' / 'app.py').read_text(encoding='utf-8')
ROUTES = (Path(__file__).parents[1] / 'api' / 'routes' / 'tents.py').read_text(encoding='utf-8')


def _to_float(v):
    try:
        n = float(v)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _functions():
    """Run production function bodies without importing DB/network dependencies."""
    funcs = {'_heap_export_csv', 'export_heap_24h_csv'}
    tree = ast.parse(SOURCE)
    nodes = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in funcs:
            node.decorator_list = []
            nodes.append(node)
    assert len(nodes) == 2
    ns = {
        'io': io,
        'csv': csv,
        'datetime': datetime,
        'timezone': timezone,
        '_to_float': _to_float,
        'Response': Response,
        'HTTPException': HTTPException,
        'Request': SimpleNamespace,
        'HEAP_EXPORT_FIELDS': ('timestamp_utc', 'uptime_seconds', 'free_heap_bytes', 'min_free_heap_bytes', 'largest_free_block_bytes', 'heap_size_bytes', 'largest_over_free_ratio'),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'api/app.py', 'exec'), ns)
    return ns


def _rows(csv_data):
    return list(csv.DictReader(io.StringIO(csv_data)))


def test_export_keeps_raw_sample_timestamps_and_ratios():
    ns = _functions()
    ts = datetime(2026, 11, 3, 20, 15, tzinfo=timezone(timedelta(hours=1)))
    sample = (ts, '4140', '124880', '66792', '59380', '320000')
    result = _rows(ns['_heap_export_csv']([sample]))
    assert len(result) == 1
    assert result[0]['timestamp_utc'] == '2026-11-03T19:15:00Z'
    assert result[0]['uptime_seconds'] == '4140'
    assert result[0]['free_heap_bytes'] == '124880'
    assert result[0]['min_free_heap_bytes'] == '66792'
    assert result[0]['largest_free_block_bytes'] == '59380'
    assert result[0]['heap_size_bytes'] == '320000'
    assert float(result[0]['largest_over_free_ratio']) == round(59380 / 124880, 5)


def test_missing_metrics_do_not_turn_into_zeros_and_samples_without_heap_are_skipped():
    ns = _functions()
    ts = datetime(2026, 11, 3, tzinfo=timezone.utc)
    result = _rows(ns['_heap_export_csv']([
        (ts, None, '122648', None, '47092', None),
        (ts, None, None, None, None, None),
        (ts, None, 'NaN', '-5', None, None),
    ]))
    assert len(result) == 1
    assert result[0]['free_heap_bytes'] == '122648'
    assert result[0]['min_free_heap_bytes'] == ''
    assert result[0]['heap_size_bytes'] == ''
    assert result[0]['uptime_seconds'] == ''
    assert float(result[0]['largest_over_free_ratio']) == round(47092/122648, 5)


def test_empty_export_has_headers_only():
    ns = _functions()
    assert ns['_heap_export_csv']([]).splitlines() == [','.join(ns['HEAP_EXPORT_FIELDS'])]


def test_no_ratio_when_free_heap_zero():
    ns = _functions()
    ts = datetime(2026, 11, 3, tzinfo=timezone.utc)
    result = _rows(ns['_heap_export_csv']([(ts, 1, 0, 0, 0, 0)]))
    assert result[0]['largest_over_free_ratio'] == ''


class FakeCursor:
    def __init__(self, exists=True, rows=()):
        self.exists = exists
        self.rows = list(rows)
        self.executions = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query, params): self.executions.append((query, params))
    def fetchone(self): return (1,) if self.exists else None
    def fetchall(self): return self.rows


class FakeConn:
    def __init__(self, cursor): self._cursor = cursor
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self): return self._cursor


def _setup_endpoint(role='admin', exists=True, rows=()):
    ns = _functions()
    cur = FakeCursor(exists, rows)
    ns['get_session'] = lambda cookie: {'role': role} if role else None
    ns['get_conn'] = lambda: FakeConn(cur)
    req = SimpleNamespace(cookies={'caop_session': 'token'})
    return ns['export_heap_24h_csv'], req, cur


@pytest.mark.parametrize('role', [None, 'guest'])
def test_guest_and_anonymous_cannot_download_even_when_auth_disabled(role):
    endpoint, req, cur = _setup_endpoint(role)
    with pytest.raises(HTTPException) as exc:
        endpoint(3, req)
    assert exc.value.status_code == 403
    assert cur.executions == []


def test_unknown_tent_is_not_exported():
    endpoint, req, cur = _setup_endpoint(exists=False)
    with pytest.raises(HTTPException) as exc:
        endpoint(9999, req)
    assert exc.value.status_code == 404
    assert len(cur.executions) == 1


def test_admin_endpoint_exports_last_24_hours_without_extra_controller_calls():
    ts = datetime(2026, 11, 3, 19, 15, tzinfo=timezone.utc)
    endpoint, req, cur = _setup_endpoint(rows=[(ts, 300, 124880, 66792, 59380, None)])
    resp = endpoint(7, req)
    assert resp.status_code == 200
    assert resp.headers['content-disposition'].startswith('attachment; filename="growtent-heap-tent-7-24h-')
    assert resp.headers['cache-control'].startswith('no-store')
    assert resp.headers['content-type'].startswith('text/csv')
    assert _rows(resp.body.decode())[0]['largest_free_block_bytes'] == '59380'
    assert len(cur.executions) == 2
    assert cur.executions[0][1] == (7,)
    query, params = cur.executions[1]
    assert "captured_at >= NOW() - INTERVAL '24 hours'" in query
    assert 'ORDER BY captured_at ASC' in query
    assert "payload->>'sys.freeHeap'" in query
    assert "payload->>'sys.uptimeS'" in query
    assert params == (7,)
    assert 'client' not in SOURCE[SOURCE.index('def export_heap_24h_csv'):SOURCE.index('@app.get("/tents/{tent_id}/history")')].lower()


def test_production_router_registers_download_and_does_not_bypass_auth():
    assert "@router.get('/tents/{tent_id}/heap/export.csv')" in ROUTES
    assert 'return legacy.export_heap_24h_csv(tent_id, request)' in ROUTES
    assert '@app.get("/tents/{tent_id}/heap/export.csv")' in SOURCE
    assert 'session.get("role") != "admin"' in SOURCE[SOURCE.index('def export_heap_24h_csv'):SOURCE.index('@app.get("/tents/{tent_id}/history")')]


def test_dashboard_admin_only_button_next_to_heap_chart_with_mobile_safe_width():
    dashboard = SOURCE[SOURCE.index('@app.get("/dashboard", response_class=HTMLResponse)'):]
    assert 'heap_export_action =' in dashboard
    assert 'if is_admin else' in dashboard.split('heap_export_action =',1)[1].splitlines()[0]
    assert '__HEAP_EXPORT_ACTION__' in dashboard
    assert '.replace("__HEAP_EXPORT_ACTION__", heap_export_action)' in dashboard
    assert '#heapExportBtn { width:auto !important;' in dashboard
    assert "heapExport24h: 'Download 24h CSV'" in dashboard
    assert "heapExport24h: '24h CSV herunterladen'" in dashboard
    assert 'currentUserRole !== \'admin\'' in dashboard
    assert '/heap/export.csv`' in dashboard


def test_button_not_emitted_into_guest_dashboard_html():
    tree = ast.parse(SOURCE)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'dashboard_page')
    fn.decorator_list = []
    ns = {
        'Request': SimpleNamespace,
        'get_session': lambda cookie: {'role': cookie} if cookie else None,
        'RedirectResponse': lambda **kwargs: kwargs,
        'FAVICON_LINKS': '',
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'api/app.py', 'exec'), ns)
    req = SimpleNamespace(query_params={'embed': '1'}, cookies={'caop_session': 'admin'})
    admin_html = ns['dashboard_page'](req)
    assert '<button id="heapExportBtn"' in admin_html
    assert '__HEAP_EXPORT_ACTION__' not in admin_html
    req.cookies['caop_session'] = 'guest'
    guest_html = ns['dashboard_page'](req)
    assert '<button id="heapExportBtn"' not in guest_html
    assert '__HEAP_EXPORT_ACTION__' not in guest_html

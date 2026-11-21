"""Optional fullscreen HDR must not alter default preview or the export."""
import ast
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote_plus

import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from PIL import Image
from services.analysis_archive import _hdr_style_camera_jpeg, MAX_CAMERA_FETCH_BYTES

with BytesIO() as buff:
    Image.new('RGB', (320, 180), (37, 48, 56)).save(buff, 'JPEG', quality=91)
    JPEG = buff.getvalue()


class Cursor:
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def execute(self, statement, values):
        assert 'rtsp_url FROM tents' in statement
        assert values == (2,)
    def fetchone(self): return ('rtsp://camera.local/live',)


class Connection:
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def cursor(self): return Cursor()


def route_under_test(handler):
    module = ast.parse((Path(__file__).parents[1] / 'api/app.py').read_text())
    method = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'tent_preview')
    method.decorator_list = []
    client = httpx.Client
    fake_httpx = SimpleNamespace(Client=lambda **kw: client(transport=httpx.MockTransport(handler), **kw))
    scope = {'get_conn': Connection, 'httpx': fake_httpx, 'Response': Response,
             'HTTPException': HTTPException, 'quote_plus': quote_plus,
             'Query': lambda value, **kw: value,
             'GO2RTC_BASE_URL': 'http://go2rtc:1984',
             'MAX_CAMERA_FETCH_BYTES': MAX_CAMERA_FETCH_BYTES,
             '_hdr_style_camera_jpeg': _hdr_style_camera_jpeg}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<isolated preview>', 'exec'), scope)
    return scope['tent_preview']


def test_default_camera_preview_is_byte_identical_and_unmodified():
    urls=[]
    def handle(request):
        urls.append(str(request.url));return httpx.Response(200, headers={'Content-Type':'image/jpeg'}, content=JPEG)
    preview=route_under_test(handle)
    response=preview(2, 1920, 1080, 88, hdr=False)
    assert response.body == JPEG
    assert response.media_type=='image/jpeg'
    assert 'width=1920' in urls[0] and 'height=1080' in urls[0] and 'q=88' in urls[0]
    assert 'rtsp%3A' in urls[0] or 'rtsp%3a' in urls[0]


def test_opt_in_hdr_uses_same_tone_mapping_as_zip():
    def handle(request):
        return httpx.Response(200, headers={'Content-Type':'image/jpeg'}, content=JPEG)
    preview=route_under_test(handle)
    response=preview(2, 1920, 1080, 88, hdr=True)
    assert response.body == _hdr_style_camera_jpeg(JPEG)
    assert response.body != JPEG
    assert response.headers['cache-control']=='no-store'
    with Image.open(BytesIO(response.body)) as image:
        assert image.size==(320,180)


@pytest.mark.parametrize('status,ctype,body', [
    (502,'image/jpeg',b'fail'),
    (200,'text/html',JPEG),
    (200,'image/jpeg',b'not-a-jpeg'),
])
def test_hdr_unavailable_does_not_return_original_as_hdr(status, ctype, body):
    def handle(request):
        return httpx.Response(status, headers={'Content-Type':ctype}, content=body)
    preview=route_under_test(handle)
    with pytest.raises(HTTPException) as error:
        preview(2,1920,1080,88,hdr=True)
    assert error.value.status_code == 502


def test_preview_mode_is_only_used_for_fullscreen_not_inline():
    source=(Path(__file__).parents[1] / 'api/app.py').read_text()
    assert 'inlinePreviewBase = basePreview ? withPreviewParams(basePreview, 1280, 720, 80)' in source
    assert 'previewModeOriginal' in source and 'previewModeHDR' in source
    assert 'const modePreview = (url) => hdrEnabled ? `${url}&hdr=1` : url;' in source
    assert 'previewModeEpoch++' in source
    assert '_hdr_style_camera_jpeg(r.content)' in source


def test_production_modular_router_forwards_hdr_to_preview_service():
    # Compile only the relevant two call chains; full app.py needs PostgreSQL
    # to import, while this routing contract needs no live database.
    from types import SimpleNamespace
    root = Path(__file__).parents[1] / 'api'
    tree = ast.parse((root / 'routes/tents.py').read_text())
    route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'preview')
    route.decorator_list = []
    ns = {'Depends': lambda v: None, 'get_tent_service': lambda: None, 'TentService': object}
    exec(compile(ast.Module(body=[route], type_ignores=[]), '<preview route>', 'exec'), ns)
    seen = []
    class FakeService:
        def preview(self, tent_id, **kw):
            seen.append((tent_id, kw));return 'ok'
    assert ns['preview'](2, w=1920, h=1080, q=88, hdr=True, service=FakeService()) == 'ok'
    assert seen[-1] == (2, {'w':1920, 'h':1080, 'q':88, 'hdr':True})

    tree = ast.parse((root / 'services/tent_service.py').read_text())
    service = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TentService')
    method = next(n for n in service.body if isinstance(n, ast.FunctionDef) and n.name == 'preview')
    ns = {'legacy': SimpleNamespace(tent_preview=lambda tid, **kw: seen.append((tid, kw)))}
    exec(compile(ast.Module(body=[method],type_ignores=[]), '<preview service>', 'exec'), ns)
    ns['preview'](FakeService(),2,1920,1080,88,True)
    assert seen[-1] == (2, {'w':1920, 'h':1080, 'q':88, 'hdr':True})

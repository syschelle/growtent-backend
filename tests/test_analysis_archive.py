"""Camera ZIP regressions: optional live JPEG, intact historic JSON, no network leaks."""
import ast
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED
from PIL import Image, ImageDraw

import httpx
import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from services.analysis_archive import (get_camera_jpeg, make_analysis_zip, MAX_CAMERA_BYTES, MAX_CAMERA_FETCH_BYTES,
    _high_quality_camera_jpeg, _hdr_style_camera_jpeg, HDR_METHOD, CAMERA_HDR_FILENAME)

with BytesIO() as _jpeg_buffer:
    Image.new('RGB', (160, 90), (35, 80, 125)).save(_jpeg_buffer, format='JPEG', quality=95)
    JPEG = _jpeg_buffer.getvalue()
JSON_BYTES = json.dumps({'schema': 'growtent.analysis.v1', 'tentId': 2, 'points': [{'metrics': {'vpd': {'avg': 1.2}}}],
    'grow_phase': {'label_de': 'Blüte · Woche 6 · spät'}}).encode()


def unpack(result):
    with ZipFile(BytesIO(result), 'r') as z:
        names = z.namelist()
        data = json.loads(z.read('growtent-2_24h.json'))
        return names, data, {name: z.read(name) for name in names}


def test_archive_carries_original_analysis_and_two_camera_jpegs():
    archived = make_analysis_zip(JSON_BYTES, 'growtent-2_24h.json', JPEG, datetime(2026,11,21,10,0,tzinfo=timezone.utc))
    names, data, contents = unpack(archived)
    assert names == ['growtent-2_24h.json', 'camera.jpg', CAMERA_HDR_FILENAME]
    assert contents['camera.jpg'] == JPEG
    assert contents[CAMERA_HDR_FILENAME] != JPEG
    with Image.open(BytesIO(contents[CAMERA_HDR_FILENAME])) as hdr:
        assert hdr.format == 'JPEG' and hdr.size == (160, 90)
    with ZipFile(BytesIO(archived), 'r') as archive:
        assert archive.getinfo('camera.jpg').compress_type == ZIP_STORED
        assert archive.getinfo(CAMERA_HDR_FILENAME).compress_type == ZIP_STORED
    assert {k:v for k,v in data.items() if k!='camera_snapshot'} == json.loads(JSON_BYTES)
    assert data['camera_snapshot'] == {'status':'included','filename':'camera.jpg','width_px':160,'height_px':90,
        'retrieved_at_utc':'2026-11-21T10:00:00Z',
        'hdr':{'status':'included','filename':CAMERA_HDR_FILENAME,'method':HDR_METHOD,'width_px':160,'height_px':90}}


def test_unavailable_camera_still_produces_valid_zip_and_bilingual_note():
    names, data, contents = unpack(make_analysis_zip(JSON_BYTES, 'growtent-2_24h.json', None))
    assert names == ['growtent-2_24h.json', 'camera-unavailable.txt']
    assert data['camera_snapshot'] == {'status':'unavailable','filename':None,'width_px':None,'height_px':None,
        'retrieved_at_utc':None,
        'hdr':{'status':'unavailable','filename':None,'method':None,'width_px':None,'height_px':None}}
    assert b'DE:' in contents['camera-unavailable.txt'] and b'EN:' in contents['camera-unavailable.txt']


@pytest.mark.parametrize('status,ctype,body,length,expected', [
    (200,'image/jpeg',JPEG,'',JPEG),
    (200,'image/jpeg; charset=binary',JPEG,'',JPEG),
    (200,'text/html',b'<html>not a camera</html>','',None),
    (502,'image/jpeg',b'', '',None),
    (302,'image/jpeg',b'', '',None),
    (200,'image/jpeg',b'not-jpeg', '',None),
    (200,'image/jpeg',JPEG,str(MAX_CAMERA_FETCH_BYTES+1),None),
    (200,'image/jpeg',b'\xff\xd8'+b'0'*(MAX_CAMERA_FETCH_BYTES+1)+b'\xff\xd9','',None),
])
def test_camera_http_responses_are_bounded_and_jpeg_validated(monkeypatch,status,ctype,body,length,expected):
    called = []
    def handler(request):
        called.append(request)
        headers = {'Content-Type': ctype}
        if length:
            headers['Content-Length'] = length
        return httpx.Response(status, content=body, headers=headers)
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr('services.analysis_archive.httpx.Client',lambda **kwargs: real_client(transport=transport,**kwargs))
    assert get_camera_jpeg('http://go2rtc:1984/',2,'rtsp://user:secret@192.168.1.2/stream') == expected
    assert len(called) == (3 if expected is None and (length or len(body)>MAX_CAMERA_FETCH_BYTES) else 1)
    assert called[0].url.host == 'go2rtc'
    assert called[0].url.path == '/api/frame.jpeg'
    assert called[0].url.params['src'].startswith('rtsp://user:secret@')
    assert 'width' not in called[0].url.params  # native stream resolution
    assert 'height' not in called[0].url.params
    assert 'q' not in called[0].url.params
    if len(called) == 3:
        assert [c.url.params.get('width') for c in called] == [None, '3840', '2560']


def test_go2rtc_failure_does_not_raise(monkeypatch):
    def handler(request):
        raise httpx.ConnectError('camera unavailable',request=request)
    transport=httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr('services.analysis_archive.httpx.Client',lambda **kwargs: real_client(transport=transport,**kwargs))
    assert get_camera_jpeg('http://go2rtc:1984',2,None) is None


def test_endpoint_reuses_json_export_and_preserves_old_handler():
    """Test route body without loading production DB, configuration or RTSP secrets."""
    tree=ast.parse((Path(__file__).parents[1]/'api/app.py').read_text())
    func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export_analysis_zip')
    assert any(isinstance(n,ast.FunctionDef) and n.name=='export_analysis_json' for n in tree.body)
    source={}
    camera_calls=[]
    def fake_json(tent,range_key):
        assert (tent,range_key)==(2,'24h')
        return Response(content=JSON_BYTES,media_type='application/json',headers={'Content-Disposition':'attachment; filename="growtent-2_24h.json"'})
    def fake_camera(base,tid,rtsp):
        camera_calls.append((base,tid,rtsp))
        return JPEG
    ns={'export_analysis_json':fake_json, 'get_tent_by_id': lambda tid:{'rtsp_url':'rtsp://secret:pw@camera/stream'},
        'get_camera_jpeg':fake_camera,'make_analysis_zip':make_analysis_zip,'Response':Response,
        're':__import__('re'),'datetime':datetime,'timezone':timezone,'GO2RTC_BASE_URL':'http://go2rtc:1984'}
    exec(compile(ast.Module(body=[func],type_ignores=[]),'api/app.py','exec'),ns)
    response=ns['export_analysis_zip'](2)
    assert response.media_type=='application/zip'
    assert response.headers['content-disposition']=='attachment; filename="growtent-2_24h.zip"'
    assert response.headers['cache-control']=='no-store'
    names,data,contents=unpack(response.body)
    assert names==['growtent-2_24h.json','camera.jpg',CAMERA_HDR_FILENAME]
    assert camera_calls==[('http://go2rtc:1984',2,'rtsp://secret:pw@camera/stream')]
    assert 'secret:pw' not in json.dumps(data)
    assert data['points']==json.loads(JSON_BYTES)['points']


def test_route_is_registered_without_replacing_old_json():
    source=(Path(__file__).parents[1]/'api/routes/system.py').read_text()
    assert "@router.get('/api/export/analysis')" in source
    assert "@router.get('/api/export/analysis.zip')" in source
    assert 'legacy.export_analysis_zip(tent_id, range)' in source


def test_native_4k_jpeg_is_preserved_byte_for_byte(monkeypatch):
    with BytesIO() as buffer:
        Image.new('RGB', (3840, 2160), (50, 110, 150)).save(buffer, format='JPEG', quality=96)
        source = buffer.getvalue()
    assert _high_quality_camera_jpeg(source) == source
    def handler(request):
        assert 'width' not in request.url.params and 'height' not in request.url.params
        return httpx.Response(200, content=source, headers={'Content-Type': 'image/jpeg'})
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client
    monkeypatch.setattr('services.analysis_archive.httpx.Client', lambda **kwargs: real_client(transport=transport,**kwargs))
    assert get_camera_jpeg('http://go2rtc:1984', 2, None) == source


def test_oversized_snapshot_uses_high_quality_proportional_downscale(monkeypatch):
    # Set a tiny simulated ZIP limit so a normal image exercises the resize path.
    monkeypatch.setattr('services.analysis_archive.MAX_CAMERA_BYTES', 110_000)
    with BytesIO() as buffer:
        Image.effect_noise((1800, 1200), 58).convert('RGB').save(buffer, format='JPEG', quality=96)
        source = buffer.getvalue()
    assert len(source) > 110_000
    image = _high_quality_camera_jpeg(source)
    assert image and len(image) <= 110_000
    with Image.open(BytesIO(image)) as processed:
        width, height = processed.size
        assert width <= 1800 and height <= 1200
        assert abs(width / height - 1.5) < 0.02
        processed.verify()
    # Image stays a valid JPEG and is not shrunk to a thumbnail arbitrarily.
    assert width >= 270 and height >= 180


def test_invalid_jpeg_is_rejected_even_with_valid_markers():
    assert _high_quality_camera_jpeg(b'\xff\xd8not-a-jpeg\xff\xd9') is None


def test_invalid_final_image_does_not_break_archive():
    names, data, _ = unpack(make_analysis_zip(JSON_BYTES, 'growtent-2_24h.json', b'not-a-jpeg'))
    assert names == ['growtent-2_24h.json', 'camera-unavailable.txt']
    assert data['camera_snapshot']['status'] == 'unavailable'


def test_hdr_style_improves_dark_detail_without_color_overdrive():
    scene = Image.new('RGB', (480, 240))
    paint = ImageDraw.Draw(scene)
    paint.rectangle((0, 0, 239, 239), fill=(36, 40, 45))
    paint.rectangle((240, 0, 479, 239), fill=(235, 235, 235))
    with BytesIO() as buffer:
        scene.save(buffer, 'JPEG', quality=96, subsampling=0)
        original = buffer.getvalue()
    hdr = _hdr_style_camera_jpeg(original)
    assert hdr is not None and hdr != original and len(hdr) <= MAX_CAMERA_BYTES
    with Image.open(BytesIO(hdr)) as result:
        assert result.size == scene.size
        left = result.getpixel((100, 120))
        right = result.getpixel((360, 120))
        assert sum(left) / 3 > 36  # Dark regions are more visible.
        assert sum(right) / 3 <= 239  # No exaggerated highlight clipping.
        assert max(left) - min(left) < 20  # No exaggerated saturation/hue shift.


def test_hdr_style_keeps_4k_resolution_and_original_is_bit_identical():
    with BytesIO() as buffer:
        Image.new('RGB', (3840, 2160), (25, 45, 80)).save(buffer, 'JPEG', quality=92)
        original = buffer.getvalue()
    hdr = _hdr_style_camera_jpeg(original)
    assert hdr and hdr != original
    assert len(hdr) <= MAX_CAMERA_BYTES
    with Image.open(BytesIO(hdr)) as check:
        assert check.size == (3840, 2160)
    names, data, contents = unpack(make_analysis_zip(JSON_BYTES, 'growtent-2_24h.json', original))
    assert contents['camera.jpg'] == original  # No mutation of original JPEG.
    assert data['camera_snapshot']['hdr']['width_px'] == 3840
    assert data['camera_snapshot']['hdr']['height_px'] == 2160


def test_hdr_style_scales_only_large_frames(monkeypatch):
    import services.analysis_archive as service
    monkeypatch.setattr(service, 'MAX_HDR_PIXELS', 100_000)
    with BytesIO() as buffer:
        Image.new('RGB', (800, 600), (110, 70, 45)).save(buffer, 'JPEG')
        original = buffer.getvalue()
    hdr = _hdr_style_camera_jpeg(original)
    assert hdr
    with Image.open(BytesIO(hdr)) as image:
        assert image.width <= 800 and image.height <= 600
        assert image.width * image.height <= 100_000
        assert abs(image.width / image.height - 800 / 600) < 0.015


def test_hdr_failed_still_keeps_original_and_bilingual_note(monkeypatch):
    monkeypatch.setattr('services.analysis_archive._hdr_style_camera_jpeg', lambda original: None)
    names, data, contents = unpack(make_analysis_zip(JSON_BYTES, 'growtent-2_24h.json', JPEG))
    assert names == ['growtent-2_24h.json', 'camera.jpg', 'camera-hdr-unavailable.txt']
    assert contents['camera.jpg'] == JPEG
    assert b'DE:' in contents['camera-hdr-unavailable.txt'] and b'EN:' in contents['camera-hdr-unavailable.txt']
    assert data['camera_snapshot']['hdr']['status'] == 'unavailable'
    assert data['camera_snapshot']['status'] == 'included'


def test_hdr_style_rejects_invalid_source_without_exception():
    assert _hdr_style_camera_jpeg(b'not-jpeg') is None

"""Read-only ZIP packaging of historical analysis JSON and two camera renderings.

The camera is fetched at the *stream's native resolution*. We keep the original
JPEG bytes wherever possible; the optional HDR-look variant uses single-frame
shadow/highlight tone mapping, NOT multi-exposure true HDR. No RTSP URLs,
credentials, or images are persisted by this service.
"""

from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import quote_plus
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import json

import httpx
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

# Keep the normal 4K/8MP JPEG untouched. These bounds protect the API from an
# unexpectedly huge camera response, independently of the 1 MB JSON limit.
MAX_CAMERA_BYTES = 20_000_000
MAX_CAMERA_FETCH_BYTES = 32_000_000
MAX_CAMERA_PIXELS = 48_000_000
CAMERA_FILENAME = 'camera.jpg'
CAMERA_HDR_FILENAME = 'camera-hdr.jpg'
MAX_HDR_PIXELS = 16_000_000  # Bound image-processing memory; 4K stays native.
HDR_METHOD = 'single_frame_tone_mapping'


def _high_quality_camera_jpeg(image: bytes) -> bytes | None:
    """Return original bytes, or reduce only an image exceeding the ZIP cap.

    If conversion is needed, use the original as source for *each* attempt:
    no repeated JPEG re-encoding, no upscaling, no changing aspect ratio.
    """
    try:
        with Image.open(BytesIO(image)) as probe:
            if probe.format != 'JPEG':
                return None
            width, height = probe.size
            if not width or not height or width * height > MAX_CAMERA_PIXELS:
                return None
            probe.verify()
        if len(image) <= MAX_CAMERA_BYTES:
            return image  # Preserve exact JPEG bytes and native resolution.
        with Image.open(BytesIO(image)) as source:
            source = ImageOps.exif_transpose(source)
            source.load()
            source = source.convert('RGB')
            width, height = source.size
            # Try retaining full resolution first. For downsizing use LANCZOS,
            # high JPEG quality and 4:4:4 chroma to avoid conspicuous artifacts.
            for factor in (1.0, .9, .8, .7, .6, .5, .4, .3, .2, .15):
                dimensions = (max(1, round(width * factor)), max(1, round(height * factor)))
                frame = source if factor == 1.0 else source.resize(
                    dimensions, Image.Resampling.LANCZOS, reducing_gap=3.0
                )
                with BytesIO() as output:
                    frame.save(output, format='JPEG', quality=94, subsampling=0, optimize=True)
                    if output.tell() <= MAX_CAMERA_BYTES:
                        return output.getvalue()
        return None
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return None



def _hdr_style_camera_jpeg(original_jpeg: bytes) -> bytes | None:
    """Make a natural-looking *single-exposure* HDR-style JPEG.

    Gently open local shadows and compress very bright regions on luminance
    only, preserving colours. The camera's clipped detail cannot be recovered.
    Keep 4K pixels, avoid upscaling or aggressive sharpening, and resize only
    if the source is unusually large or the final JPEG exceeds its size cap.
    The original camera JPEG is never modified or re-encoded by this function.
    """
    try:
        with Image.open(BytesIO(original_jpeg)) as image:
            if image.format != 'JPEG':
                return None
            w, h = image.size
            if not w or not h or w * h > MAX_CAMERA_PIXELS:
                return None
            if w * h > MAX_HDR_PIXELS:
                ratio = (MAX_HDR_PIXELS / (w * h)) ** .5
                image.draft('RGB', (round(w * ratio), round(h * ratio)))
            source = ImageOps.exif_transpose(image)
            source.load()
            source = source.convert('RGB')
        if source.width * source.height > MAX_HDR_PIXELS:
            ratio = (MAX_HDR_PIXELS / (source.width * source.height)) ** .5
            source = source.resize((max(1, int(source.width * ratio)), max(1, int(source.height * ratio))),
                                   Image.Resampling.LANCZOS, reducing_gap=3.0)
        y, cb, cr = source.convert('YCbCr').split()
        # A broad illumination estimate prevents noisy per-pixel correction.
        local = y.filter(ImageFilter.GaussianBlur(radius=max(4, min(source.size) / 150)))
        def smoothstep(low: float, high: float, value: float) -> float:
            f = min(1., max(0., (value - low) / (high - low)))
            return f * f * (3. - 2. * f)
        shadow_mask = local.point([round(105 * (1 - smoothstep(35, 165, v))) for v in range(256)])
        high_mask = local.point([round(85 * smoothstep(135, 245, v)) for v in range(256)])
        lifted = y.point([round(255 * (v / 255) ** .72) for v in range(256)])
        compressed = y.point([round(v * (1 - .07 * (v / 255) ** 3)) for v in range(256)])
        toned = Image.composite(lifted, y, shadow_mask)
        toned = Image.composite(compressed, toned, high_mask)
        result = Image.merge('YCbCr', (toned, cb, cr)).convert('RGB')
        with BytesIO() as out:
            result.save(out, format='JPEG', quality=94, subsampling=0, optimize=True)
            jpg = out.getvalue()
        # An extremely complex frame can still be large; apply the same
        # bounded, high-quality rule as for the original (never upscale).
        return jpg if len(jpg) <= MAX_CAMERA_BYTES else _high_quality_camera_jpeg(jpg)
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, MemoryError):
        return None


def _read_frame(client: httpx.Client, base_url: str, src: str, width: int | None = None) -> tuple[str, bytes | None]:
    """Download a single frame with an input bound; never follow redirects."""
    url = f'{base_url.rstrip("/")}/api/frame.jpeg?src={quote_plus(src)}'
    if width is not None:
        url += f'&width={width}'
    try:
        with client.stream('GET', url) as response:
            if response.status_code != 200:
                return 'unavailable', None
            if response.headers.get('content-type', '').split(';')[0].strip().lower() != 'image/jpeg':
                return 'unavailable', None
            if int(response.headers.get('content-length', '0') or 0) > MAX_CAMERA_FETCH_BYTES:
                return 'oversized', None
            chunks = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_CAMERA_FETCH_BYTES:
                    return 'oversized', None
                chunks.append(chunk)
        image = b''.join(chunks)
        if len(image) < 4 or not image.startswith(b'\xff\xd8') or not image.endswith(b'\xff\xd9'):
            return 'unavailable', None
        processed = _high_quality_camera_jpeg(image)
        return ('ok', processed) if processed else ('unavailable', None)
    except (httpx.HTTPError, ValueError, OverflowError):
        return 'unavailable', None


def get_camera_jpeg(go2rtc_base_url: str, tent_id: int, rtsp_url: str | None) -> bytes | None:
    """Fetch the largest practical JPEG from go2rtc without affecting previews.

    Native stream resolution is used by default (no width/height arguments).
    Only if the frame exceeds the *input* safety limit, retry via go2rtc with
    progressively smaller widths; this exception avoids dropping huge frames.
    """
    src = f'{rtsp_url}#media=video' if rtsp_url else f'tent_{int(tent_id)}'
    try:
        with httpx.Client(timeout=httpx.Timeout(9.0, connect=2.0), follow_redirects=False) as client:
            for width in (None, 3840, 2560):
                status, image = _read_frame(client, go2rtc_base_url, src, width)
                if status == 'ok':
                    return image
                if status != 'oversized':
                    return None
    except httpx.HTTPError:
        pass
    return None


def make_analysis_zip(json_bytes: bytes, json_filename: str, camera_jpeg: bytes | None,
                      retrieved_at: datetime | None = None) -> bytes:
    """Preserve the original analysis records while attaching snapshot availability metadata."""
    analysis = json.loads(json_bytes)
    included = camera_jpeg is not None
    width_px = height_px = None
    if included:
        # The analysis consumer can tell how much real detail the photo has.
        try:
            with Image.open(BytesIO(camera_jpeg)) as frame:
                if frame.format != 'JPEG':
                    raise ValueError('not a JPEG')
                width_px, height_px = frame.size
        except (OSError, ValueError, UnidentifiedImageError):
            # A corrupt final image must never break the climate export.
            included = False
            camera_jpeg = None
    hdr_jpeg = _hdr_style_camera_jpeg(camera_jpeg) if included else None
    hdr_width = hdr_height = None
    if hdr_jpeg is not None:
        try:
            with Image.open(BytesIO(hdr_jpeg)) as image:
                hdr_width, hdr_height = image.size
                if image.format != 'JPEG':
                    raise ValueError('not a JPEG')
                image.verify()
        except (OSError, ValueError, UnidentifiedImageError):
            hdr_jpeg = None
            hdr_width = hdr_height = None
    analysis['camera_snapshot'] = {
        'status': 'included' if included else 'unavailable',
        'filename': CAMERA_FILENAME if included else None,
        'width_px': width_px,
        'height_px': height_px,
        # Time of the camera response, not the historical end of the metrics window.
        'retrieved_at_utc': retrieved_at.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z') if included and retrieved_at else None,
        'hdr': {
            'status': 'included' if hdr_jpeg is not None else 'unavailable',
            'filename': CAMERA_HDR_FILENAME if hdr_jpeg is not None else None,
            'method': HDR_METHOD if hdr_jpeg is not None else None,
            'width_px': hdr_width,
            'height_px': hdr_height,
        },
    }
    with BytesIO() as buffer:
        with ZipFile(buffer, 'w', compression=ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr(json_filename, json.dumps(analysis, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
            if included:
                # JPEG is compressed already. Store byte-identically in ZIP.
                archive.writestr(CAMERA_FILENAME, camera_jpeg, compress_type=ZIP_STORED)
                if hdr_jpeg is not None:
                    archive.writestr(CAMERA_HDR_FILENAME, hdr_jpeg, compress_type=ZIP_STORED)
                else:
                    archive.writestr('camera-hdr-unavailable.txt',
                        'DE: Die HDR-Tonwertvariante konnte nicht erstellt werden. Das Originalbild bleibt enthalten.\n'
                        'EN: The HDR-style image could not be created. The original camera image is included.\n')
            else:
                archive.writestr('camera-unavailable.txt',
                    'DE: Zum Exportzeitpunkt war kein Kamerabild verfügbar. Die historischen Messwerte sind vollständig enthalten.\n'
                    'EN: No camera image was available at export time. Historical measurements are still included.\n')
        return buffer.getvalue()

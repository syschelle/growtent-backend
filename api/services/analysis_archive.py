"""Read-only ZIP packaging of historical analysis JSON and two camera renderings.

The camera is fetched at the *stream's native resolution*. We keep the original
JPEG bytes wherever possible; the optional HDR-look variant uses single-frame
adaptive tone mapping and clarity enhancement, NOT multi-exposure true HDR. No RTSP URLs,
credentials, or images are persisted by this service.
"""

from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import quote_plus
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
import json

import httpx
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
from services.pot_markers import draw_marked_camera_jpeg, normalize_pot_positions

# Keep the normal 4K/8MP JPEG untouched. These bounds protect the API from an
# unexpectedly huge camera response, independently of the 1 MB JSON limit.
MAX_CAMERA_BYTES = 20_000_000
MAX_CAMERA_FETCH_BYTES = 32_000_000
MAX_CAMERA_PIXELS = 48_000_000
CAMERA_FILENAME = 'camera.jpg'
CAMERA_HDR_FILENAME = 'camera-hdr.jpg'
CAMERA_MARKED_FILENAME = 'camera-marked.jpg'
MAX_HDR_PIXELS = 16_000_000  # Bound image-processing memory; 4K stays native.
HDR_METHOD = 'single_frame_adaptive_tone_mapping_v2'


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
    """Enhanced single-frame HDR *look*, calibrated on real tent-camera samples.

    Older processing barely moved midtones, especially with diffuse LED light.
    The new adaptive luminance curve brings back global separation, while a
    bounded local-contrast pass makes existing detail easier to see. This does
    not recover clipped highlights or lost optical focus, and is not true HDR.

    Work on luminance, retain natural colour (only a small saturation lift),
    and never affect the original JPEG. Keep 4K frames without resampling.
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
        histogram = y.histogram()
        total = sum(histogram)
        def percentile(fraction: float) -> int:
            threshold = total * fraction
            n = 0
            for value, count in enumerate(histogram):
                n += count
                if n >= threshold:
                    return value
            return 255

        p2, p10, p50, p90, p99 = (percentile(q) for q in (.02, .10, .50, .90, .99))
        # For uniformly dark captures, lift shadows rather than crushing them.
        # Otherwise, a gentle S curve improves the often hazy 10–90% range.
        spread = p90 - p10
        amount = min(1.0, max(0.0, (spread - 12) / 45))
        def shift(value: int, delta: float) -> int:
            return max(0, min(255, round(value + delta * amount)))
        anchors = [
            (0, 0),
            (p2, shift(p2, 12 if p2 < 55 else -17)),
            (p10, shift(p10, 10 if p10 < 68 else -16)),
            (p50, shift(p50, 2)),
            (p90, min(249, p99, shift(p90, 22))),
            (p99, min(253, p99)),
            (255, 255),
        ]
        # Flat/synthetic scenes can have identical percentiles. Coalesce
        # repeated X values and keep a monotonically increasing mapping.
        unique = []
        for x, value in anchors:
            if unique and x == unique[-1][0]:
                unique[-1] = (x, value)
            else:
                unique.append((x, value))
        knots = []
        for x, value in unique:
            knots.append((x, max(value, knots[-1][1] if knots else 0)))
        lut = []
        index = 0
        for value in range(256):
            while index < len(knots) - 2 and value > knots[index + 1][0]:
                index += 1
            x0, y0 = knots[index]
            x1, y1 = knots[index + 1]
            mapped = y0 if x0 == x1 else y0 + (y1 - y0) * (value - x0) / (x1 - x0)
            lut.append(max(0, min(255, round(mapped))))
        toned = y.point(lut)
        # Clarity increases genuine local contrast, with a small threshold
        # to avoid exaggerating JPEG grain and block artifacts.
        if spread >= 24:
            radius = max(2.0, min(source.size) / 130)
            toned = toned.filter(ImageFilter.UnsharpMask(radius=radius, percent=120, threshold=3))
        result = Image.merge('YCbCr', (toned, cb, cr)).convert('RGB')
        if spread >= 24:
            result = ImageEnhance.Color(result).enhance(1.10)
        with BytesIO() as out:
            result.save(out, format='JPEG', quality=94, subsampling=0, optimize=True)
            jpg = out.getvalue()
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
    positions = normalize_pot_positions(analysis.get('pot_positions'))
    has_positions = any(point is not None for point in positions.values())
    marked = draw_marked_camera_jpeg(camera_jpeg, positions, analysis.get('pot_strains')) if included and has_positions else None
    marked_jpeg, marked_width, marked_height = marked if marked is not None else (None, None, None)
    marked_status = ('included' if marked_jpeg is not None else
                     'unavailable' if not included else
                     'not_configured' if not has_positions else 'error')
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
        'marked': {
            'status': marked_status,
            'filename': CAMERA_MARKED_FILENAME if marked_jpeg is not None else None,
            'width_px': marked_width,
            'height_px': marked_height,
            'source': 'current_tent_configuration',
        },
    }
    with BytesIO() as buffer:
        with ZipFile(buffer, 'w', compression=ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr(json_filename, json.dumps(analysis, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
            if included:
                # JPEG is compressed already. Store byte-identically in ZIP.
                archive.writestr(CAMERA_FILENAME, camera_jpeg, compress_type=ZIP_STORED)
                if marked_jpeg is not None:
                    archive.writestr(CAMERA_MARKED_FILENAME, marked_jpeg, compress_type=ZIP_STORED)
                elif has_positions:
                    archive.writestr('camera-marked-unavailable.txt',
                        'DE: Das markierte Kamerabild konnte nicht erstellt werden. Original/HDR bleiben enthalten.\n'
                        'EN: The labelled camera image could not be generated. Original/HDR are unaffected.\n')
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

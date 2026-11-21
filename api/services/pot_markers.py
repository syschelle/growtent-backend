"""Read-only camera-label renderer and normalized per-tent pot coordinates.

Positions are normalized fractions of the *upright* camera picture.  Keeping
labels separate from the stream makes them stable at any preview resolution.
"""
from io import BytesIO
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

POT_KEYS = ('pot1', 'pot2', 'pot3')
MAX_MARKED_PIXELS = 16_000_000  # native 4K is retained; bound CPU and memory
MAX_MARKED_JPEG_BYTES = 20_000_000


def normalize_pot_positions(value) -> dict:
    """Return exactly three positions or null; never synthesize coordinates."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            value = {}
    if not isinstance(value, dict):
        value = {}
    result = {}
    for key in POT_KEYS:
        point = value.get(key)
        if not isinstance(point, dict):
            result[key] = None
            continue
        x, y = point.get('x'), point.get('y')
        if (isinstance(x, bool) or isinstance(y, bool) or
            not isinstance(x, (int, float)) or not isinstance(y, (int, float)) or
            not math.isfinite(x) or not math.isfinite(y) or
            not (0 <= x <= 1 and 0 <= y <= 1)):
            result[key] = None
        else:
            result[key] = {'x': round(x, 5), 'y': round(y, 5)}
    return result


def _font(pixel_size: int):
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
                 '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'):
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, pixel_size)
            except (OSError, ValueError):
                pass
    return ImageFont.load_default(size=pixel_size)


def draw_marked_camera_jpeg(original_jpeg: bytes, pot_positions: dict, pot_strains: dict | None = None):
    """Produce a number-only JPEG or None. Never alter original input bytes.

    Returns (jpeg, width, height), with dimensions of the *actual* output.
    JPEG is generated only when at least one saved pot position exists.
    """
    positions = normalize_pot_positions(pot_positions)
    if not any(positions.values()):
        return None
    try:
        with Image.open(BytesIO(original_jpeg)) as source:
            if source.format != 'JPEG':
                return None
            width, height = source.size
            if width < 1 or height < 1 or width * height > 48_000_000:
                return None
            if width * height > MAX_MARKED_PIXELS:
                ratio = (MAX_MARKED_PIXELS / (width * height)) ** .5
                source.draft('RGB', (max(1, int(width * ratio)), max(1, int(height * ratio))))
            image = ImageOps.exif_transpose(source).convert('RGB')
        if image.width * image.height > MAX_MARKED_PIXELS:
            ratio = (MAX_MARKED_PIXELS / (image.width * image.height)) ** .5
            image = image.resize((max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
                                 Image.Resampling.LANCZOS, reducing_gap=3.0)
        w, h = image.size
        draw = ImageDraw.Draw(image)
        scale = max(0.5, min(w / 1920, h / 1080))
        radius = round(17 * scale)
        font = _font(max(11, round(20 * scale)))
        colors = ('#3b82f6', '#06b6d4', '#f59e0b')
        for i, key in enumerate(POT_KEYS):
            point = positions[key]
            if point is None:
                continue
            x = int(point['x'] * (w - 1))
            y = int(point['y'] * (h - 1))
            color = colors[i]
            draw.ellipse((x-radius-3, y-radius-3, x+radius+3, y+radius+3), fill='#0b1220', outline='white', width=max(1, round(2*scale)))
            draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)
            n = str(i + 1)
            nr = draw.textbbox((0, 0), n, font=font)
            draw.text((x - (nr[2]-nr[0])/2, y - (nr[3]-nr[1])/2 - nr[1]), n,
                      fill='white', font=font, stroke_width=1, stroke_fill='#142033')
        with BytesIO() as out:
            image.save(out, format='JPEG', quality=94, subsampling=0, optimize=True)
            result = out.getvalue()
        if len(result) > MAX_MARKED_JPEG_BYTES:
            return None  # no repeated JPEG compression or label distortion
        return result, w, h
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, MemoryError, UnicodeError):
        return None

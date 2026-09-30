import io
import random

import pytest
from fastapi import HTTPException
from PIL import Image

from app.core.compressor import MAX_DIMENSION, compress_image


def _encode(image: Image.Image, fmt: str, **kwargs) -> bytes:
    output = io.BytesIO()
    image.save(output, format=fmt, **kwargs)
    return output.getvalue()


def _open(content: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(content))
    image.load()
    return image


def _noisy(size: tuple[int, int], mode: str = "RGB") -> Image.Image:
    rng = random.Random(7)
    image = Image.new(mode, size)
    bands = len(mode)
    image.putdata([tuple(rng.randrange(256) for _ in range(bands)) for _ in range(size[0] * size[1])])
    return image


def _photo(size: tuple[int, int]) -> Image.Image:
    gradient = Image.linear_gradient("L").resize(size)
    grain = Image.effect_noise(size, 12)
    return Image.merge("RGB", (gradient, Image.blend(gradient, grain, 0.3), grain))


def test_png_becomes_smaller_jpeg():
    source = _encode(_photo((300, 200)), "PNG")
    out = compress_image(source)
    image = _open(out.content)
    assert (out.extension, out.content_type) == (".jpg", "image/jpeg")
    assert image.format == "JPEG"
    assert image.size == (300, 200)
    assert len(out.content) < len(source)


def test_extremely_detailed_image_still_encodes():
    out = compress_image(_encode(_noisy((300, 200)), "PNG"))
    assert _open(out.content).format == "JPEG"


def test_transparent_png_keeps_transparency():
    rgba = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    rgba.paste((200, 0, 0, 255), (0, 0, 32, 64))
    out = compress_image(_encode(rgba, "PNG"))
    image = _open(out.content).convert("RGBA")
    assert (out.extension, out.content_type) == (".png", "image/png")
    assert image.getpixel((48, 32))[3] == 0
    assert image.getpixel((8, 32)) == (200, 0, 0, 255)


def test_transparent_webp_becomes_png():
    rgba = _photo((80, 80)).convert("RGBA")
    rgba.putalpha(Image.linear_gradient("L").resize((80, 80)))
    out = compress_image(_encode(rgba, "WEBP", lossless=True))
    image = _open(out.content)
    assert image.format == "PNG"
    assert image.mode == "RGBA"
    assert image.getchannel("A").getextrema()[0] < 5


def test_fully_opaque_alpha_png_becomes_jpeg():
    opaque = _photo((120, 80)).convert("RGBA")
    out = compress_image(_encode(opaque, "PNG"))
    assert out.extension == ".jpg"


def test_oversized_image_is_downscaled_keeping_aspect_ratio():
    source = _encode(Image.new("RGB", (MAX_DIMENSION * 2, MAX_DIMENSION), (10, 120, 60)), "PNG")
    image = _open(compress_image(source).content)
    assert image.format == "JPEG"
    assert image.size == (MAX_DIMENSION, MAX_DIMENSION // 2)


def test_oversized_transparent_image_is_downscaled_as_png():
    source = _encode(Image.new("RGBA", (MAX_DIMENSION * 2, MAX_DIMENSION), (10, 120, 60, 0)), "PNG")
    image = _open(compress_image(source).content)
    assert image.format == "PNG"
    assert image.size == (MAX_DIMENSION, MAX_DIMENSION // 2)


def test_custom_max_dimension_downscales_small_slots():
    source = _encode(Image.new("RGBA", (1254, 1254), (10, 120, 60, 0)), "PNG")
    image = _open(compress_image(source, max_dimension=512).content)
    assert image.size == (512, 512)


def test_exif_orientation_is_applied():
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° clockwise on display
    source = _encode(Image.new("RGB", (120, 60), (40, 40, 200)), "JPEG", quality=95, exif=exif)
    image = _open(compress_image(source).content)
    assert image.size == (60, 120)
    assert image.getexif().get(0x0112) in (None, 1)


def test_compact_jpeg_is_returned_unchanged():
    source = _encode(_noisy((200, 200)), "JPEG", quality=40)
    assert compress_image(source).content == source


def test_lossy_webp_keeps_top_quality_even_if_larger():
    source = _encode(_noisy((200, 200)), "WEBP", quality=30)
    out = compress_image(source).content
    assert _open(out).format == "JPEG"
    assert len(out) > len(source)
    decoded = _open(source).convert("RGB")
    reencoded = _open(out).convert("RGB")
    diffs = [abs(a - b) for a, b in zip(decoded.tobytes(), reencoded.tobytes())]
    assert sum(diffs) / len(diffs) < 6


def test_unreadable_bytes_are_rejected():
    with pytest.raises(HTTPException) as exc:
        compress_image(b"definitely not an image")
    assert exc.value.status_code == 400

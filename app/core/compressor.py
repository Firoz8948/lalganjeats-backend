# backend/app/core/compressor.py
"""Re-encode uploaded images as compact files without visible quality loss."""
import io
from dataclasses import dataclass

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError

# Longest edge kept. Larger than any slot we render (home banner is 2140 px wide),
# so downscaling only strips pixels no screen will ever show.
MAX_DIMENSION = 2560
# (quality, chroma subsampling) tried in order; the first result no bigger than
# the upload wins. 88 with full-resolution colour (4:4:4) keeps banner text
# crisp. The floor, 85 at 4:2:0, is still high quality. Already-lossy sources
# (mostly WebP) that JPEG cannot match in size fall back to the first, best
# setting: quality is never traded away just to hit a smaller file.
JPEG_ATTEMPTS = ((88, 0), (88, 2), (85, 2))
# Refuse absurd pixel counts before decoding (decompression-bomb guard).
MAX_PIXELS = 60_000_000

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


@dataclass(frozen=True)
class CompressedImage:
    content: bytes
    extension: str
    content_type: str


def _jpeg(content: bytes) -> CompressedImage:
    return CompressedImage(content, ".jpg", "image/jpeg")


def _png(content: bytes) -> CompressedImage:
    return CompressedImage(content, ".png", "image/png")


def _has_transparency(image: Image.Image) -> bool:
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")
    if image.mode not in ("RGBA", "LA", "PA"):
        return False
    return image.getchannel("A").getextrema()[0] < 255


def compress_image(content: bytes, max_dimension: int = MAX_DIMENSION) -> CompressedImage:
    """
    Compress any supported upload (JPG/PNG/WebP).

    Images with transparent areas become optimized lossless PNGs so the
    transparency survives (JPEG has no alpha channel); everything else becomes
    a JPEG.     EXIF rotation is applied, the colour profile is preserved, and
    images are only downscaled beyond max_dimension. Re-encoded files carry no
    EXIF/GPS metadata. An upload already smaller than its re-encoded form is
    kept unchanged when it is already in the target format.
    """
    try:
        with Image.open(io.BytesIO(content)) as source:
            source_format = source.format
            source.seek(0)  # first frame of animated WebP/PNG
            image = ImageOps.exif_transpose(source)
            image.load()
            icc_profile = source.info.get("icc_profile")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Could not read that image.") from exc

    transparent = _has_transparency(image)
    image = image.convert("RGBA" if transparent else "RGB")

    resized = max(image.size) > max_dimension
    if resized:
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    if transparent:
        encoded = _save(image, "PNG", optimize=True, icc_profile=icc_profile)
        if source_format == "PNG" and not resized and len(content) <= len(encoded):
            return _png(content)
        return _png(encoded)

    best_quality = None
    for quality, subsampling in JPEG_ATTEMPTS:
        encoded = _encode_jpeg(image, quality, subsampling, icc_profile)
        best_quality = best_quality or encoded
        if resized or len(encoded) <= len(content):
            return _jpeg(encoded)

    if source_format == "JPEG":
        return _jpeg(content)
    return _jpeg(best_quality)


def _encode_jpeg(image: Image.Image, quality: int, subsampling: int, icc_profile: bytes | None) -> bytes:
    options = {"quality": quality, "subsampling": subsampling, "icc_profile": icc_profile}
    try:
        return _save(image, "JPEG", optimize=True, progressive=True, **options)
    except OSError:
        # Pillow buffers optimized/progressive output at ~1 byte per pixel, which
        # extremely detailed images overflow; plain baseline JPEG streams instead.
        return _save(image, "JPEG", **options)


def _save(image: Image.Image, fmt: str, **options) -> bytes:
    output = io.BytesIO()
    image.save(output, format=fmt, **options)
    return output.getvalue()

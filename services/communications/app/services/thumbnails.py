"""Phase 17b — server-side image thumbnail generator.

Uses Pillow when available. Falls back gracefully (returns None) when:
  * Pillow isn't installed,
  * the source bytes aren't a recognisable image,
  * the source is already smaller than the thumbnail bounds,
  * generation raises any unexpected error.

Thumbnails:
  * Max bounding box 256x256, preserving aspect.
  * Always encoded as JPEG quality 80 (small + universally supported).
  * Transparent PNGs are flattened onto a white background.

Output is bytes the caller hands to the storage backend.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)


THUMB_BOX = (256, 256)
THUMB_QUALITY = 80


def generate_thumbnail(data: bytes, mime_type: str) -> Optional[bytes]:
    """Return JPEG-encoded thumbnail bytes, or None when no thumbnail
    should be generated.

    Args:
        data: raw bytes of the uploaded file.
        mime_type: client-declared MIME (e.g. "image/png").
    """
    if not mime_type.startswith("image/"):
        return None
    if mime_type == "image/gif":
        # Animated gifs are typically tiny + lose meaning when flat-
        # thumbed. Skip.
        return None
    try:
        from PIL import Image, ImageOps
    except ImportError:  # pragma: no cover
        logger.warning("Pillow not installed; skipping thumbnail")
        return None

    try:
        img = Image.open(io.BytesIO(data))
        # Respect EXIF orientation so portrait photos don't end up
        # sideways.
        img = ImageOps.exif_transpose(img)
        # Flatten transparency onto white so the JPEG looks clean.
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode != "P" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        img.thumbnail(THUMB_BOX, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=THUMB_QUALITY,
                 optimize=True, progressive=True)
        return buf.getvalue()
    except Exception as e:
        logger.warning("thumbnail_generation_failed err=%s", e)
        return None

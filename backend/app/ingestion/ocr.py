import io
import logging

import pytesseract
from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    _configured = True


def ocr_image_bytes(image_bytes: bytes) -> str:
    """Run local OCR on raw image bytes. Returns '' (never raises) if the image is unreadable
    or OCR is unavailable, so a missing/broken image never fails the whole ingestion pipeline."""
    _ensure_configured()
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert("RGB")
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception:  # noqa: BLE001 - OCR is best-effort by design
        logger.warning("OCR failed for an embedded image", exc_info=True)
        return ""

"""OCR extraction for scanned documents and images (blueprint §17).

Behind the existing :class:`TextExtractor` port, so the ingestion pipeline is
unchanged: a scanned PDF becomes text the same way a DOCX does.

**Off by default** (``OCR_ENABLED=false``). OCR needs the Tesseract *binary*,
a system package rather than a Python dependency, so it cannot be guaranteed
present the way ``pypdf`` can. Enabling it without installing Tesseract would
turn every scanned upload into an opaque failure, so instead the capability is
declared in config and the code reports precisely what is missing.

Rendering uses ``pypdfium2``, which ships self-contained wheels — unlike
``pdf2image``, which needs Poppler installed separately and would have added a
second system dependency to explain.
"""

from __future__ import annotations

import asyncio
from io import BytesIO

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.interfaces.extraction import TextExtractionError
from app.platform.registry import register_provider

logger = get_logger("app.infrastructure.extraction.ocr")

# Pages beyond this are ignored. OCR is ~1s/page on CPU, and a 500-page scan
# would occupy a worker long enough to look like a hang.
_MAX_PAGES = 50
# Rendering scale. Tesseract wants ~300 DPI; PDF user units are 72/inch.
_RENDER_SCALE = 300 / 72


class OcrUnavailableError(TextExtractionError):
    """Raised when OCR is requested but cannot run.

    Distinct from a parse failure: the document may be perfectly fine and the
    deployment is simply missing a binary. The message says which.
    """


def _require_engine() -> tuple[object, object]:
    """Import the OCR stack, or explain exactly what is missing."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise OcrUnavailableError(
            "OCR requires the 'ocr' extra: pip install -e '.[ocr]'"
        ) from exc

    try:
        pytesseract.get_tesseract_version()
    except Exception as exc:  # pragma: no cover - depends on the host
        raise OcrUnavailableError(
            "OCR requires the Tesseract binary (apt-get install tesseract-ocr / "
            "brew install tesseract); the Python package alone is not enough"
        ) from exc

    return pytesseract, Image


def ocr_available() -> bool:
    """Whether OCR could run right now. Never raises."""
    try:
        _require_engine()
    except OcrUnavailableError:
        return False
    return True


@register_provider(kind="extractor", name="ocr")
class OcrTextExtractor:
    """Reads text out of raster images and scanned PDFs via Tesseract."""

    def __init__(self, languages: str | None = None) -> None:
        self._languages = languages

    @property
    def languages(self) -> str:
        return self._languages or get_settings().ocr_languages

    async def extract(self, content: bytes) -> str:
        """OCR ``content``, which may be an image or a PDF."""
        if not get_settings().ocr_enabled:
            raise OcrUnavailableError(
                "OCR is disabled; set OCR_ENABLED=true to process scanned documents"
            )
        text = await asyncio.to_thread(self._extract_sync, content)
        if not text.strip():
            raise TextExtractionError("OCR found no readable text in this document")
        return text

    # -- worker-thread body --------------------------------------------------

    def _extract_sync(self, content: bytes) -> str:
        pytesseract, image_module = _require_engine()
        if content.startswith(b"%PDF-"):
            return self._ocr_pdf(content, pytesseract, image_module)
        return self._ocr_image(content, pytesseract, image_module)

    def _ocr_image(self, content: bytes, pytesseract: object, image_module: object) -> str:
        try:
            image = image_module.open(BytesIO(content))  # type: ignore[attr-defined]
            image.load()
        except Exception as exc:
            raise TextExtractionError(f"Not a readable image: {exc}") from exc
        return str(
            pytesseract.image_to_string(image, lang=self.languages)  # type: ignore[attr-defined]
        )

    def _ocr_pdf(self, content: bytes, pytesseract: object, image_module: object) -> str:
        try:
            import pypdfium2
        except ImportError as exc:  # pragma: no cover - depends on install extras
            raise OcrUnavailableError(
                "Scanned-PDF OCR requires the 'ocr' extra: pip install -e '.[ocr]'"
            ) from exc

        try:
            document = pypdfium2.PdfDocument(content)
        except Exception as exc:
            raise TextExtractionError(f"Failed to open PDF for OCR: {exc}") from exc

        pages: list[str] = []
        try:
            total = len(document)
            if total > _MAX_PAGES:
                logger.warning(
                    "ocr.page_limit_reached",
                    extra={"pages": total, "limit": _MAX_PAGES},
                )
            for number in range(min(total, _MAX_PAGES)):
                page = document[number]
                bitmap = page.render(scale=_RENDER_SCALE)
                try:
                    image = bitmap.to_pil()
                    pages.append(
                        str(
                            pytesseract.image_to_string(  # type: ignore[attr-defined]
                                image, lang=self.languages
                            )
                        )
                    )
                finally:
                    bitmap.close()
                    page.close()
        finally:
            document.close()

        return "\n\n".join(pages)

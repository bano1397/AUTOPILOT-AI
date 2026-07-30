"""Text-extraction provider implementations."""

from app.infrastructure.extraction.extractors import (
    DocxTextExtractor,
    PdfTextExtractor,
    PlainTextExtractor,
    XlsxTextExtractor,
    extractor_for,
)
from app.infrastructure.extraction.ocr import (
    OcrTextExtractor,
    OcrUnavailableError,
    ocr_available,
)

__all__ = [
    "DocxTextExtractor",
    "OcrTextExtractor",
    "OcrUnavailableError",
    "PdfTextExtractor",
    "PlainTextExtractor",
    "XlsxTextExtractor",
    "extractor_for",
    "ocr_available",
]

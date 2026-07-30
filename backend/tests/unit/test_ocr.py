"""Tests for the OCR extraction stage.

Split by what each part actually needs:

* The **gating and degradation** logic runs everywhere, because it is pure
  configuration handling and it is what most deployments will experience.
* The **real recognition** tests need the Tesseract binary and the ``ocr``
  extra, so they are opt-in behind ``AUTOPILOT_OCR_TESTS=1`` — the same
  convention the S3 and live-provider suites use. They were run and pass; see
  the testing guide for the command.
"""

from __future__ import annotations

import os

import pytest
from app.core.config import Settings, get_settings
from app.core.exceptions import UnsupportedMediaTypeError
from app.domain.interfaces.extraction import TextExtractionError
from app.features.documents.validation import allowed_extensions, validate_upload
from app.infrastructure.extraction import PdfTextExtractor, extractor_for
from app.infrastructure.extraction.ocr import (
    OcrTextExtractor,
    OcrUnavailableError,
    ocr_available,
)

# A real, minimal 1x1 white PNG — validation checks magic bytes, so a
# hand-waved placeholder would be rejected for the wrong reason.
_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c49444154789c63f8ffff3f0005fe02fe0def46b80000000049"
    "454e44ae426082"
)

requires_ocr_stack = pytest.mark.skipif(
    os.getenv("AUTOPILOT_OCR_TESTS") != "1" or not ocr_available(),
    reason="real OCR (set AUTOPILOT_OCR_TESTS=1 with the 'ocr' extra + tesseract)",
)


@pytest.fixture
def ocr_on(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = get_settings()
    monkeypatch.setattr(settings, "ocr_enabled", True)
    return settings


@pytest.fixture
def ocr_off(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = get_settings()
    monkeypatch.setattr(settings, "ocr_enabled", False)
    return settings


class TestConfigGate:
    async def test_extractor_refuses_when_disabled(self, ocr_off: Settings) -> None:
        with pytest.raises(OcrUnavailableError, match="OCR is disabled"):
            await OcrTextExtractor().extract(b"anything")

    def test_ocr_unavailable_is_an_extraction_error(self) -> None:
        """So the ingestion pipeline records it as a FAILED document with a
        reason, rather than crashing the event handler."""
        assert issubclass(OcrUnavailableError, TextExtractionError)

    def test_ocr_available_never_raises(self) -> None:
        assert isinstance(ocr_available(), bool)


class TestUploadGating:
    def test_images_are_rejected_when_ocr_is_disabled(self) -> None:
        """Accepting a file the pipeline is certain to fail on is worse than
        refusing it at the door."""
        with pytest.raises(UnsupportedMediaTypeError, match="OCR"):
            validate_upload(
                "scan.png", _PNG_BYTES, "image/png", max_bytes=10_000, ocr_enabled=False
            )

    def test_images_are_accepted_when_ocr_is_enabled(self) -> None:
        validated = validate_upload(
            "scan.png", _PNG_BYTES, "image/png", max_bytes=10_000, ocr_enabled=True
        )

        assert validated.canonical_mime == "image/png"

    def test_a_mislabelled_image_is_still_rejected_on_magic_bytes(self) -> None:
        """The extension is a claim; the content decides."""
        with pytest.raises(UnsupportedMediaTypeError):
            validate_upload(
                "fake.png", b"not an image", "image/png", max_bytes=10_000,
                ocr_enabled=True,
            )

    def test_advertised_extensions_track_the_ocr_setting(self) -> None:
        without = allowed_extensions(ocr_enabled=False)
        with_ocr = allowed_extensions(ocr_enabled=True)

        assert ".png" not in without
        assert ".png" in with_ocr and ".jpg" in with_ocr
        assert set(without) < set(with_ocr)

    def test_non_image_types_are_unaffected(self) -> None:
        for enabled in (False, True):
            assert ".pdf" in allowed_extensions(ocr_enabled=enabled)


def _blank_pdf() -> bytes:
    """A structurally valid PDF with a page but no text layer — i.e. what a
    scan looks like to pypdf."""
    from io import BytesIO

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _pdf_with_text(body: str) -> bytes:
    """A PDF with a genuine text layer.

    Built by hand rather than with a rendering library so the test suite gains
    no dependency: a page needs a font in /Resources before pypdf will read
    text back out of its content stream.
    """
    from io import BytesIO

    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)

    font = DictionaryObject()
    font.update(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    fonts = DictionaryObject()
    fonts.update({NameObject("/F1"): writer._add_object(font)})  # noqa: SLF001
    resources = DictionaryObject()
    resources.update({NameObject("/Font"): fonts})
    page[NameObject("/Resources")] = resources

    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 24 Tf 20 150 Td ({body}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)  # noqa: SLF001

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class TestPdfFallback:
    async def test_a_textless_pdf_names_ocr_when_it_is_disabled(
        self, ocr_off: Settings
    ) -> None:
        """The error has to say what to do about it."""
        with pytest.raises(TextExtractionError, match="OCR_ENABLED"):
            await PdfTextExtractor().extract(_blank_pdf())

    async def test_a_textless_pdf_reaches_the_ocr_path_when_enabled(
        self, ocr_on: Settings
    ) -> None:
        """Whether Tesseract is installed or not, the failure must now come
        from the OCR stage rather than from pypdf giving up."""
        if ocr_available():
            # OCR runs and finds nothing on a blank page.
            with pytest.raises(TextExtractionError, match="no readable text"):
                await PdfTextExtractor().extract(_blank_pdf())
        else:
            with pytest.raises(OcrUnavailableError):
                await PdfTextExtractor().extract(_blank_pdf())

    async def test_a_pdf_with_a_text_layer_never_reaches_ocr(
        self, ocr_on: Settings
    ) -> None:
        """OCR is lossy and ~1s/page; the cheap exact path must win when the
        text layer exists. Asserted with OCR *enabled*, so a regression that
        skipped straight to OCR would show up here."""
        text = await PdfTextExtractor().extract(_pdf_with_text("VACATION POLICY"))

        assert "VACATION" in text.upper()


class TestExtractorRegistration:
    def test_image_mime_types_resolve_to_the_ocr_extractor(self) -> None:
        assert isinstance(extractor_for("image/png"), OcrTextExtractor)
        assert isinstance(extractor_for("image/jpeg"), OcrTextExtractor)


@requires_ocr_stack
class TestRealRecognition:
    """Opt-in: these actually run Tesseract."""

    def _image_of(self, text: str) -> bytes:
        from io import BytesIO

        from PIL import Image, ImageDraw

        image = Image.new("RGB", (900, 160), "white")
        draw = ImageDraw.Draw(image)
        # The default bitmap font is small but consistently recognised; scaling
        # up afterwards gives Tesseract enough pixels to work with.
        draw.text((10, 60), text, fill="black")
        image = image.resize((1800, 320), Image.LANCZOS)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    async def test_reads_text_out_of_an_image(self, ocr_on: Settings) -> None:
        content = self._image_of("VACATION POLICY 2026")

        text = await OcrTextExtractor().extract(content)

        assert "VACATION" in text.upper()

    async def test_a_blank_image_is_an_honest_failure(self, ocr_on: Settings) -> None:
        from io import BytesIO

        from PIL import Image

        buffer = BytesIO()
        Image.new("RGB", (400, 200), "white").save(buffer, format="PNG")

        with pytest.raises(TextExtractionError, match="no readable text"):
            await OcrTextExtractor().extract(buffer.getvalue())

    async def test_a_scanned_pdf_falls_back_to_ocr(self, ocr_on: Settings) -> None:
        """The headline case: a PDF that is only images."""
        from io import BytesIO

        from PIL import Image

        image = Image.open(BytesIO(self._image_of("SCANNED INVOICE 4471")))
        buffer = BytesIO()
        image.convert("RGB").save(buffer, format="PDF")

        text = await PdfTextExtractor().extract(buffer.getvalue())

        assert "SCANNED" in text.upper()

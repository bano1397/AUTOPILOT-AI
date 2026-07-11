"""Unit tests for upload validation (extension, MIME, magic bytes, size)."""

from __future__ import annotations

import pytest
from app.core.exceptions import (
    FileTooLargeError,
    UnsupportedMediaTypeError,
    ValidationAppError,
)
from app.features.documents.validation import validate_upload

_MAX = 1024 * 1024
_PDF = b"%PDF-1.7 fake body"
_ZIP = b"PK\x03\x04 fake ooxml body"


def test_valid_txt() -> None:
    result = validate_upload("notes.txt", b"hello world", "text/plain", max_bytes=_MAX)
    assert result.safe_filename == "notes.txt"
    assert result.suffix == ".txt"
    assert result.canonical_mime == "text/plain"


def test_valid_pdf() -> None:
    result = validate_upload("report.PDF", _PDF, "application/pdf", max_bytes=_MAX)
    assert result.suffix == ".pdf"
    assert result.canonical_mime == "application/pdf"


def test_valid_docx_and_xlsx_zip_magic() -> None:
    docx = validate_upload("a.docx", _ZIP, None, max_bytes=_MAX)
    xlsx = validate_upload("b.xlsx", _ZIP, None, max_bytes=_MAX)
    assert docx.canonical_mime.endswith("wordprocessingml.document")
    assert xlsx.canonical_mime.endswith("spreadsheetml.sheet")


def test_octet_stream_declared_type_is_accepted() -> None:
    result = validate_upload(
        "data.csv", b"a,b\n1,2\n", "application/octet-stream", max_bytes=_MAX
    )
    assert result.canonical_mime == "text/csv"


def test_client_path_components_are_stripped() -> None:
    result = validate_upload(
        "../../etc/passwd.txt", b"content", "text/plain", max_bytes=_MAX
    )
    assert result.safe_filename == "passwd.txt"

    windows = validate_upload(
        "C:\\Users\\evil\\..\\doc.txt", b"content", "text/plain", max_bytes=_MAX
    )
    assert windows.safe_filename == "doc.txt"


def test_disallowed_extension_is_rejected() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        validate_upload("malware.exe", b"MZ...", None, max_bytes=_MAX)


def test_mismatched_declared_mime_is_rejected() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        validate_upload("report.pdf", _PDF, "text/html", max_bytes=_MAX)


def test_wrong_magic_bytes_are_rejected() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        validate_upload("report.pdf", b"<html>not a pdf</html>", None, max_bytes=_MAX)


def test_binary_content_in_text_file_is_rejected() -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        validate_upload("notes.txt", b"\x00\xff\xfe binary", None, max_bytes=_MAX)


def test_empty_file_is_rejected() -> None:
    with pytest.raises(ValidationAppError):
        validate_upload("notes.txt", b"", None, max_bytes=_MAX)


def test_missing_filename_is_rejected() -> None:
    with pytest.raises(ValidationAppError):
        validate_upload(None, b"content", None, max_bytes=_MAX)


def test_oversized_file_is_rejected() -> None:
    with pytest.raises(FileTooLargeError):
        validate_upload("notes.txt", b"too big", None, max_bytes=3)

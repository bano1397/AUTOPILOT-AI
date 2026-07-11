"""Upload validation: extension, declared MIME, magic bytes, and size.

Pure functions with no HTTP or persistence concerns (unit-testable). Security
posture per blueprint §27: the client's filename and content type are treated
as claims; the file content (magic bytes) is decisive, and the canonical MIME
type stored on the document is derived from the validated extension.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath

from app.core.exceptions import (
    FileTooLargeError,
    UnsupportedMediaTypeError,
    ValidationAppError,
)

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"  # DOCX/XLSX are OOXML zip containers


def _is_utf8_text(content: bytes) -> bool:
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return b"\x00" not in content


@dataclass(frozen=True)
class _FileType:
    """Validation rules and canonical metadata for one allowed extension."""

    canonical_mime: str
    allowed_declared_mimes: frozenset[str]

    def matches_content(self, content: bytes) -> bool:
        if self.canonical_mime == "application/pdf":
            return content.startswith(_PDF_MAGIC)
        if self.canonical_mime.startswith("application/vnd."):
            return content.startswith(_ZIP_MAGIC)
        return _is_utf8_text(content)


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Browsers sometimes send application/octet-stream for anything; accept it as a
# declared type everywhere — the magic-byte check remains decisive.
_OCTET = "application/octet-stream"

ALLOWED_TYPES: dict[str, _FileType] = {
    ".pdf": _FileType("application/pdf", frozenset({"application/pdf", _OCTET})),
    ".docx": _FileType(_DOCX_MIME, frozenset({_DOCX_MIME, _OCTET})),
    ".xlsx": _FileType(_XLSX_MIME, frozenset({_XLSX_MIME, _OCTET})),
    ".txt": _FileType("text/plain", frozenset({"text/plain", _OCTET})),
    ".csv": _FileType(
        "text/csv", frozenset({"text/csv", "application/csv", "text/plain", _OCTET})
    ),
}


@dataclass(frozen=True)
class ValidatedUpload:
    """Outcome of a successful upload validation."""

    safe_filename: str
    suffix: str
    canonical_mime: str


def validate_upload(
    filename: str | None,
    content: bytes,
    declared_mime: str | None,
    *,
    max_bytes: int,
) -> ValidatedUpload:
    """Validate an upload's name, declared type, content, and size.

    Returns the sanitized display filename, the normalized extension, and the
    canonical MIME type to persist. Raises :class:`UnsupportedMediaTypeError`,
    :class:`FileTooLargeError`, or :class:`ValidationAppError` on rejection.
    """
    if not filename:
        raise ValidationAppError("A filename is required")

    # Strip any client-supplied directory components (both separator styles).
    basename = PureWindowsPath(PurePosixPath(filename).name).name
    if not basename:
        raise ValidationAppError("A filename is required")
    basename = basename[:255]

    suffix = PurePosixPath(basename).suffix.lower()
    file_type = ALLOWED_TYPES.get(suffix)
    if file_type is None:
        allowed = ", ".join(sorted(ALLOWED_TYPES))
        raise UnsupportedMediaTypeError(
            f"File type {suffix or '(none)'!r} is not supported",
            details={"allowed_extensions": allowed},
        )

    if declared_mime and declared_mime.lower() not in file_type.allowed_declared_mimes:
        raise UnsupportedMediaTypeError(
            f"Declared content type {declared_mime!r} does not match {suffix!r}"
        )

    if not content:
        raise ValidationAppError("Uploaded file is empty")

    if len(content) > max_bytes:
        raise FileTooLargeError(
            f"File exceeds the maximum allowed size of {max_bytes} bytes",
            details={"max_bytes": max_bytes, "size_bytes": len(content)},
        )

    if not file_type.matches_content(content):
        raise UnsupportedMediaTypeError(
            f"File content does not match the {suffix!r} format"
        )

    return ValidatedUpload(
        safe_filename=basename, suffix=suffix, canonical_mime=file_type.canonical_mime
    )

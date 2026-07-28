"""Decoding helpers for RFC 5322 messages.

Split out from the IMAP transport because this is the part with real edge cases
(encoded-word headers, multipart bodies, declared-vs-actual charsets) and it is
pure — every case below is unit-tested without a server.
"""

from __future__ import annotations

from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parsedate_to_datetime


def decode_header_value(raw: str | None) -> str:
    """Decode an RFC 2047 encoded-word header into text."""
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except (UnicodeDecodeError, LookupError, ValueError):
        # Malformed encoding is not worth failing a whole sync over.
        return raw


def extract_body(message: Message, *, max_chars: int = 20000) -> str:
    """Return the message's plain-text body.

    Prefers ``text/plain``; falls back to stripping tags from ``text/html`` only
    if that is all the sender provided. Attachments are ignored.
    """
    if message.is_multipart():
        plain = _first_part(message, "text/plain")
        if plain is not None:
            return _payload_text(plain)[:max_chars]
        html = _first_part(message, "text/html")
        if html is not None:
            return _strip_tags(_payload_text(html))[:max_chars]
        return ""
    text = _payload_text(message)
    if message.get_content_type() == "text/html":
        text = _strip_tags(text)
    return text[:max_chars]


def parse_date(raw: str | None) -> datetime | None:
    """Parse a Date header, tolerating the many ways it is malformed."""
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None


def _first_part(message: Message, content_type: str) -> Message | None:
    for part in message.walk():
        if part.get_content_type() == content_type and not part.is_multipart():
            disposition = str(part.get("Content-Disposition") or "")
            if "attachment" not in disposition.lower():
                return part
    return None


def _payload_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes):
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        # Sender declared a charset Python doesn't know.
        return payload.decode("utf-8", errors="replace")


def _strip_tags(html: str) -> str:
    """Crude tag strip — enough to give the LLM readable text."""
    from html.parser import HTMLParser

    class _Extractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.chunks: list[str] = []
            self._skip = False

        def handle_starttag(self, tag: str, attrs: object) -> None:
            if tag in {"script", "style"}:
                self._skip = True

        def handle_endtag(self, tag: str) -> None:
            if tag in {"script", "style"}:
                self._skip = False

        def handle_data(self, data: str) -> None:
            if not self._skip and data.strip():
                self.chunks.append(data.strip())

    parser = _Extractor()
    parser.feed(html)
    return "\n".join(parser.chunks)

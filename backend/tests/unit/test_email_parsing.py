"""Unit tests for email decoding and classifier-output parsing."""

from __future__ import annotations

import email
import json

import pytest
from app.agents.email.parsing import parse_classification
from app.features.emails.models import EmailIntent
from app.infrastructure.email.parsing import (
    decode_header_value,
    extract_body,
    parse_date,
)

# --- header / body decoding -------------------------------------------------


def test_decode_encoded_word_header() -> None:
    assert decode_header_value("=?utf-8?q?Caf=C3=A9_invoice?=") == "Café invoice"


def test_decode_plain_and_empty_headers() -> None:
    assert decode_header_value("Plain Subject") == "Plain Subject"
    assert decode_header_value(None) == ""


def test_extract_plain_text_body() -> None:
    message = email.message_from_string(
        "Content-Type: text/plain; charset=utf-8\n\nHello there\n"
    )

    assert extract_body(message).strip() == "Hello there"


def test_multipart_prefers_plain_text_over_html() -> None:
    raw = (
        'Content-Type: multipart/alternative; boundary="b"\n\n'
        "--b\nContent-Type: text/plain\n\nplain version\n"
        "--b\nContent-Type: text/html\n\n<p>html version</p>\n"
        "--b--\n"
    )
    message = email.message_from_string(raw)

    assert "plain version" in extract_body(message)
    assert "html version" not in extract_body(message)


def test_html_only_body_is_stripped_to_text() -> None:
    raw = (
        'Content-Type: multipart/alternative; boundary="b"\n\n'
        "--b\nContent-Type: text/html\n\n"
        "<style>p{color:red}</style><p>Hello</p><script>evil()</script><p>World</p>\n"
        "--b--\n"
    )
    message = email.message_from_string(raw)
    body = extract_body(message)

    assert "Hello" in body and "World" in body
    # Script and style content must not reach the prompt.
    assert "evil()" not in body and "color:red" not in body


def test_attachments_are_ignored() -> None:
    raw = (
        'Content-Type: multipart/mixed; boundary="b"\n\n'
        "--b\nContent-Type: text/plain\n\nreal body\n"
        '--b\nContent-Type: text/plain\nContent-Disposition: attachment; filename="a.txt"\n\n'
        "attachment text\n--b--\n"
    )
    message = email.message_from_string(raw)

    assert "real body" in extract_body(message)
    assert "attachment text" not in extract_body(message)


def test_unknown_charset_falls_back_without_raising() -> None:
    message = email.message_from_string(
        "Content-Type: text/plain; charset=definitely-not-a-charset\n\nbody\n"
    )

    assert "body" in extract_body(message)


def test_body_is_truncated() -> None:
    message = email.message_from_string(
        "Content-Type: text/plain\n\n" + ("x" * 50_000)
    )

    assert len(extract_body(message, max_chars=100)) == 100


@pytest.mark.parametrize("raw", [None, "", "not a date", "Tue, 99 Xxx 2026"])
def test_malformed_dates_return_none(raw: str | None) -> None:
    assert parse_date(raw) is None


def test_valid_date_is_parsed() -> None:
    parsed = parse_date("Tue, 28 Jul 2026 09:30:00 +0000")

    assert parsed is not None
    assert parsed.year == 2026 and parsed.hour == 9


# --- classifier output ------------------------------------------------------


def test_parse_clean_json_classification() -> None:
    raw = json.dumps(
        {
            "intent": "invoice",
            "entities": {"amounts": ["$420.00"], "order_ids": ["INV-1"]},
            "summary": "Chasing payment.",
        }
    )

    parsed = parse_classification(raw)

    assert parsed.intent is EmailIntent.INVOICE
    assert parsed.entities == {"amounts": ["$420.00"], "order_ids": ["INV-1"]}
    assert parsed.summary == "Chasing payment."


def test_parse_fenced_json() -> None:
    raw = '```json\n{"intent": "complaint", "entities": {}}\n```'

    assert parse_classification(raw).intent is EmailIntent.COMPLAINT


def test_parse_json_embedded_in_prose() -> None:
    raw = 'Sure! Here is the classification:\n{"intent": "meeting"}\nHope that helps.'

    assert parse_classification(raw).intent is EmailIntent.MEETING


def test_unparseable_output_degrades_to_other() -> None:
    assert parse_classification("I think this is spam maybe?").intent is EmailIntent.OTHER


def test_unknown_intent_degrades_to_other() -> None:
    raw = json.dumps({"intent": "urgent-ish"})

    assert parse_classification(raw).intent is EmailIntent.OTHER


def test_intent_is_case_and_space_insensitive() -> None:
    assert parse_classification('{"intent": "  SUPPORT "}').intent is EmailIntent.SUPPORT


def test_unknown_entity_keys_are_dropped() -> None:
    raw = json.dumps({"intent": "other", "entities": {"colours": ["red"], "people": ["Ada"]}})

    assert parse_classification(raw).entities == {"people": ["Ada"]}


def test_entity_lists_are_capped_and_truncated() -> None:
    raw = json.dumps(
        {"intent": "other", "entities": {"people": [f"p{i}" for i in range(50)]}}
    )

    assert len(parse_classification(raw).entities["people"]) == 10


def test_non_string_entities_are_filtered() -> None:
    raw = json.dumps({"intent": "other", "entities": {"amounts": [None, {"a": 1}, "12"]}})

    assert parse_classification(raw).entities == {"amounts": ["12"]}


def test_entities_that_are_not_an_object_are_ignored() -> None:
    raw = json.dumps({"intent": "other", "entities": ["not", "an", "object"]})

    assert parse_classification(raw).entities == {}

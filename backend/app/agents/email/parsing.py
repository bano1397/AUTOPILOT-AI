"""Layered parsing of the classifier's JSON output.

Same posture as the planner's plan parsing: local models wrap JSON in prose or
fences, so try progressively looser strategies, and when nothing parses fall back
to a neutral classification rather than inventing one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.features.emails.models import EmailIntent

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_ENTITY_KEYS = ("people", "organizations", "dates", "amounts", "order_ids")
_MAX_ENTITIES = 10
_MAX_ENTITY_CHARS = 200


@dataclass(frozen=True)
class ClassifiedEmail:
    """Parsed classifier output."""

    intent: EmailIntent
    entities: dict[str, list[str]] = field(default_factory=dict)
    summary: str = ""


def parse_classification(raw: str) -> ClassifiedEmail:
    """Parse the classifier reply, degrading to ``OTHER`` when unparseable."""
    payload = _decode(raw)
    if payload is None:
        return ClassifiedEmail(intent=EmailIntent.OTHER)

    return ClassifiedEmail(
        intent=_intent_of(payload.get("intent")),
        entities=_entities_of(payload.get("entities")),
        summary=str(payload.get("summary") or "")[:500],
    )


def _decode(raw: str) -> dict[str, Any] | None:
    candidates = [raw.strip()]
    fenced = _FENCE.search(raw)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    # Last resort: the outermost {...} span in the reply.
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        candidates.append(raw[start : end + 1])

    for candidate in candidates:
        try:
            decoded = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            return decoded
    return None


def _intent_of(value: object) -> EmailIntent:
    if not isinstance(value, str):
        return EmailIntent.OTHER
    try:
        return EmailIntent(value.strip().lower())
    except ValueError:
        return EmailIntent.OTHER


def _entities_of(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, list[str]] = {}
    for key in _ENTITY_KEYS:
        items = value.get(key)
        if not isinstance(items, list):
            continue
        strings = [
            str(item)[:_MAX_ENTITY_CHARS]
            for item in items[:_MAX_ENTITIES]
            if isinstance(item, str | int | float) and str(item).strip()
        ]
        if strings:
            cleaned[key] = strings
    return cleaned

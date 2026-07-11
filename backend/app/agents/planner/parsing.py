"""Parsing of the planner LLM's JSON output.

Local models don't always follow "JSON only" perfectly, so parsing is layered:
direct parse → markdown-fence strip → outermost-bracket substring. Items are
validated individually; invalid ones are skipped rather than failing the plan.
"""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field, ValidationError

from app.features.tasks.models import TaskPriority

_MAX_TASKS = 10
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$", re.MULTILINE)


class PlanItem(BaseModel):
    """One task proposed by the planner."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    priority: TaskPriority = TaskPriority.MEDIUM


def parse_plan(text: str) -> list[PlanItem]:
    """Extract validated plan items from the LLM reply; [] when unparseable."""
    raw = _load_json_array(text)
    if raw is None:
        return []

    items: list[PlanItem] = []
    for entry in raw[:_MAX_TASKS]:
        if not isinstance(entry, dict):
            continue
        try:
            items.append(PlanItem.model_validate(entry))
        except ValidationError:
            continue
    return items


def _load_json_array(text: str) -> list[object] | None:
    candidates = [text.strip(), _FENCE_RE.sub("", text).strip()]
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(value, list):
            return value
    return None

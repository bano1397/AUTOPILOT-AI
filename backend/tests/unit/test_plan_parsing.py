"""Unit tests for planner output parsing."""

from __future__ import annotations

from app.agents.planner.parsing import parse_plan
from app.features.tasks.models import TaskPriority

_PLAIN = '[{"title": "Draft outline", "description": "Scope it.", "priority": "high"}]'


def test_parses_plain_json_array() -> None:
    items = parse_plan(_PLAIN)
    assert len(items) == 1
    assert items[0].title == "Draft outline"
    assert items[0].priority is TaskPriority.HIGH


def test_parses_markdown_fenced_json() -> None:
    items = parse_plan(f"```json\n{_PLAIN}\n```")
    assert len(items) == 1


def test_parses_array_embedded_in_prose() -> None:
    items = parse_plan(f"Here is your plan!\n{_PLAIN}\nGood luck!")
    assert len(items) == 1


def test_defaults_and_skips_invalid_items() -> None:
    text = (
        '[{"title": "Valid"}, {"description": "missing title"}, "not-a-dict",'
        ' {"title": "Bad priority", "priority": "someday"}]'
    )
    items = parse_plan(text)
    assert [item.title for item in items] == ["Valid"]
    assert items[0].priority is TaskPriority.MEDIUM
    assert items[0].description == ""


def test_caps_item_count() -> None:
    text = "[" + ",".join(f'{{"title": "T{i}"}}' for i in range(20)) + "]"
    assert len(parse_plan(text)) == 10


def test_unparseable_returns_empty() -> None:
    assert parse_plan("Sure! First, do the thing. Then the other thing.") == []
    assert parse_plan('{"title": "an object, not an array"}') == []

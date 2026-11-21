"""Tests for the per-lot diff fixtures: lot added/removed, unchanged and differing deadlines."""

import json
from pathlib import Path

import pytest
import yaml
from src.ted_watch.core.diff import diff
from src.ted_watch.core.map import map_raw_to_notice
from src.ted_watch.core.model import Notice, RawNotice

REPO_ROOT = Path(__file__).resolve().parents[2]
VISIBLE = REPO_ROOT / "fixtures" / "visible"
PROCEDURES = (
    "vis-lot-added",
    "vis-lot-removed",
    "vis-no-op-change",
    "vis-differing-lot-deadlines",
)


def _load(path: Path) -> Notice:
    """Load a visible fixture and map it. No network."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return map_raw_to_notice(RawNotice.model_validate(data))


def _expected(procedure: str) -> dict[str, object]:
    """Read the fixture's expected file."""
    path = VISIBLE / procedure / "expected.yaml"
    loaded: dict[str, object] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


@pytest.mark.parametrize("procedure", PROCEDURES)
def test_events_match_expected(procedure: str) -> None:
    """The deadline_changed events equal the fixture's expected file."""
    expected = _expected(procedure)
    previous = _load(VISIBLE / procedure / "predecessor.json")
    current = _load(VISIBLE / procedure / str(expected["change"]))
    events = diff(current, previous)
    assert all(e["event"] == "deadline_changed" for e in events)
    assert [
        {"lot": e["lot"], "previous": e["previous"], "current": e["current"]} for e in events
    ] == expected["events"]


def test_no_op_change_emits_no_deadline_changed() -> None:
    """A change that keeps the deadline emits nothing."""
    assert _expected("vis-no-op-change")["events"] == []

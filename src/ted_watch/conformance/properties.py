"""Hypothesis property checks for map and diff, run inside the ted_api conformance kit."""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from ..core.diff import diff_notices
from ..core.map import map_raw_to_notice
from ..core.model import RawNotice

MAX_EXAMPLES = 25
FIXTURE_DIR = (
    Path(__file__).resolve().parents[3] / "fixtures" / "connectors" / "ted_api" / "fixtures"
)

REQUIRED_EVENT_KEYS = (
    "event",
    "notice",
    "source",
    "coverage",
    "attribution",
    "kind",
    "current_notice",
)
_OPTIONAL_FIELDS = (
    "deadline",
    "authorityCity",
    "url",
    "changeReasonCode",
    "changeReason",
    "noticeIdentifier",
    "noticeVersion",
    "publicationNumber",
    "procedureIdentifier",
    "changeNoticeVersionIdentifier",
)
_DATE_FIELDS = ("publicationDate", "deadline")
_REASON_CODES = ("susp-review", "cancel-intent", "EXT", "NONE")


def fixture_notices() -> list[dict[str, Any]]:
    """Return the raw ted_api connector fixture notices."""
    notices: list[dict[str, Any]] = []
    for file_path in sorted(FIXTURE_DIR.glob("*.json")):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        notices.extend(item for item in (data if isinstance(data, list) else [data]) if item)
    return notices


def _truncate(value: Any, length: int) -> Any:
    """Cut a date/time string to its first ``length`` characters."""
    return value[:length] if isinstance(value, str) else value


@st.composite
def mutated_notices(draw: st.DrawFn) -> dict[str, Any]:
    """Draw a fixture notice, drop optional fields, shuffle lots, truncate date/time values."""
    item = copy.deepcopy(draw(st.sampled_from(fixture_notices())))
    for key in draw(st.lists(st.sampled_from(_OPTIONAL_FIELDS), unique=True, max_size=6)):
        item.pop(key, None)
    lots = item.get("lots")
    if isinstance(lots, list):
        item["lots"] = draw(st.permutations(lots))
        for lot in item["lots"]:
            if isinstance(lot, dict) and "deadline" in lot:
                lot["deadline"] = _truncate(lot["deadline"], draw(st.integers(0, 10)))
    for key in _DATE_FIELDS:
        if key in item:
            item[key] = _truncate(item[key], draw(st.integers(0, 10)))
    if draw(st.booleans()):
        item["changeReasonCode"] = draw(st.sampled_from(_REASON_CODES))
    result: dict[str, Any] = item
    return result


def validate_event(event: Mapping[str, Any]) -> list[str]:
    """Return schema errors for a diff event; empty when it validates."""
    errors = [f"missing {key}" for key in REQUIRED_EVENT_KEYS if key not in event]
    errors.extend(
        f"{key} is not a non-empty string"
        for key in REQUIRED_EVENT_KEYS
        if key in event and not (isinstance(event[key], str) and event[key])
    )
    return errors


def check_notice(item: dict[str, Any]) -> tuple[int, list[str]]:
    """Map and diff one raw notice; return ``(events, unresolved)``.

    Map must not raise on input that ``RawNotice`` accepts. An event that fails
    validation is reported as unresolved instead of being dropped.
    """
    try:
        raw = RawNotice.model_validate(item)
    except ValueError:
        return 0, []
    notice = map_raw_to_notice(raw)
    events = diff_notices(None, notice)
    unresolved = [
        f"{event.get('event')}: {errors}"
        for event in events
        if (errors := validate_event(event))
    ]
    return len(events), unresolved


def run_properties(max_examples: int = MAX_EXAMPLES) -> int:
    """Run the map/diff properties with a bounded ``max_examples``; return 0 on success."""

    @settings(
        max_examples=max_examples,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(mutated_notices())
    def _property(item: dict[str, Any]) -> None:
        _count, unresolved = check_notice(item)
        assert not unresolved, unresolved

    _property()
    return 0

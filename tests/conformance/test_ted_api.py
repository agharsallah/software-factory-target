"""Conformance property checks for the ted_api connector."""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from src.ted_watch.conformance import (
    check_map_and_diff,
    event_is_valid,
    run_map_diff_checks,
)
from src.ted_watch.conformance.strategy import mutate_fixture_json, mutated_raw_notice
from src.ted_watch.core.map import map_raw_to_notice
from src.ted_watch.core.model import RawNotice

FIXTURE_DIR = (
    Path(__file__).parent.parent.parent / "fixtures" / "connectors" / "ted_api" / "fixtures"
)
WITH_LOTS = "notice_contract_with_lots.json"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class TestTedApiConformance:
    """Conformance §5.2 checks: mutated ted_api inputs never crash or emit junk."""

    @settings(max_examples=50, deadline=None, derandomize=True)
    @given(raw=mutated_raw_notice("ted_api"))
    def test_map_never_crashes_and_diff_valid(self, raw: RawNotice) -> None:
        """Map never raises; every diff output is schema-valid or unresolved."""
        notice = map_raw_to_notice(raw)
        assert notice.notice_id == raw.notice_id
        report = check_map_and_diff(raw)
        assert report in {"valid", "unresolved"}

    def test_kit_runs_ted_api_with_bounded_examples(self) -> None:
        """The conformance kit executes the ted_api property with a finite bound."""
        run_map_diff_checks("ted_api", max_examples=50)


def test_strategy_drops_optionals_shuffles_lots_truncates_arrays() -> None:
    """Mutation drops optional fields, reorders lots, and shortens date/time arrays."""
    original = _load(WITH_LOTS)
    mutated = mutate_fixture_json(
        original,
        drop_fields=["url", "authorityCity", "changeReason", "deadline"],
        lot_order=[1, 0],
        truncate_lengths={
            "deadline-receipt-tender-date-lot": 1,
            "deadline-receipt-tender-time-lot": 0,
            "deadline-receipt-request-date-lot": 1,
        },
    )

    assert "url" not in mutated
    assert "authorityCity" not in mutated
    assert "changeReason" not in mutated
    assert "deadline" not in mutated
    assert mutated["noticeId"] == original["noticeId"]
    assert mutated["title"] == original["title"]
    assert mutated["noticeType"] == original["noticeType"]
    assert mutated["lots"][0]["id"] == "LOT-002"
    assert mutated["lots"][1]["id"] == "LOT-001"
    assert len(mutated["deadline-receipt-tender-date-lot"]) == 1
    assert len(mutated["deadline-receipt-tender-time-lot"]) == 0
    assert len(mutated["deadline-receipt-tender-date-lot"]) != len(
        mutated["deadline-receipt-tender-time-lot"]
    )
    raw = RawNotice.model_validate(mutated)
    assert map_raw_to_notice(raw).notice_id == "123456-2024"


def test_missing_diff_is_reported_unresolved() -> None:
    """Without core.diff, the kit reports unresolved rather than inventing events."""
    raw = RawNotice.model_validate(_load(WITH_LOTS))
    assert check_map_and_diff(raw, diff_fn=None) == "unresolved"


def test_diff_output_validates_against_event_schema() -> None:
    """Schema-valid diff events pass; anything else is rejected or unresolved."""
    raw = RawNotice.model_validate(_load(WITH_LOTS))

    def valid_diff(previous, current):
        return [
            {
                "event": "deadline_changed",
                "kind": "cor-buy",
                "lot": "LOT-001",
                "previous": "2024-02-01",
                "current": "2024-02-28",
            }
        ]

    def unresolved_diff(previous, current):
        return "unresolved"

    def invalid_diff(previous, current):
        return [{"event": "not-an-event", "lot": 1}]

    assert check_map_and_diff(raw, diff_fn=valid_diff) == "valid"
    assert check_map_and_diff(raw, diff_fn=unresolved_diff) == "unresolved"
    with pytest.raises(ValueError):
        check_map_and_diff(raw, diff_fn=invalid_diff)


def test_event_schema_requires_known_event_kind() -> None:
    """The event schema accepts deadline changes and rejects malformed objects."""
    assert event_is_valid(
        {"event": "deadline_changed", "lot": "LOT-001", "previous": None, "current": "2024-02-28"}
    )
    assert event_is_valid({"event": "suspension"})
    assert not event_is_valid({"event": "nope"})
    assert not event_is_valid({"lot": "LOT-001"})
    assert not event_is_valid("unresolved")

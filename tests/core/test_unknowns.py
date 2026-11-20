"""Tests for aggregating unmapped values across notices."""

import json
from collections import Counter
from pathlib import Path

from src.ted_watch.core.map import map_raw_to_notice
from src.ted_watch.core.model import RawNotice
from src.ted_watch.core.unknowns import aggregate

FIXTURE_DIR = (
    Path(__file__).parent.parent.parent / "fixtures" / "connectors" / "ted_api" / "fixtures"
)


def load_fixture(name: str) -> RawNotice:
    """Load a fixture JSON file and parse as RawNotice."""
    path = FIXTURE_DIR / name
    with path.open() as f:
        data = json.load(f)
    return RawNotice.model_validate(data)


def test_fixture_reason_and_pointer_show_up_in_aggregate() -> None:
    """Reason code new-code-x and a malformed pointer are counted and do not crash."""
    raw = load_fixture("notice_contract_unknown_values.json")
    notice = map_raw_to_notice(raw)
    counts = aggregate([notice])

    assert isinstance(counts, Counter)
    assert counts[("change-reason-code", "new-code-x")] == 1
    assert counts[("pointer", "not-a-pointer")] == 1
    assert raw.change_reason_code == "new-code-x"
    assert raw.change_notice_version_identifier == "not-a-pointer"


def test_aggregate_sums_the_same_pair_across_notices() -> None:
    """The same (kind, value) pair adds up across notices."""
    raw = load_fixture("notice_contract_unknown_values.json")
    notices = [map_raw_to_notice(raw), map_raw_to_notice(raw)]
    counts = aggregate(notices)
    assert counts[("change-reason-code", "new-code-x")] == 2
    assert counts[("pointer", "not-a-pointer")] == 2


def test_aggregate_keys_are_kind_value_tuples() -> None:
    """Every counter key is a (kind, value) pair of strings."""
    raw = load_fixture("notice_contract_unknown_values.json")
    counts = aggregate([map_raw_to_notice(raw)])
    assert counts
    for key in counts:
        assert isinstance(key, tuple)
        assert len(key) == 2
        kind, value = key
        assert isinstance(kind, str)
        assert isinstance(value, str)


def test_aggregate_empty() -> None:
    """No notices yields an empty counter."""
    assert aggregate([]) == Counter()


def test_aggregate_is_pure() -> None:
    """Repeated aggregation matches and does not keep a global tally."""
    raw = load_fixture("notice_contract_unknown_values.json")
    notices = [map_raw_to_notice(raw)]
    first = aggregate(notices)
    second = aggregate(notices)
    assert first == second
    assert first is not second
    first[("change-reason-code", "new-code-x")] += 10
    assert aggregate(notices)[("change-reason-code", "new-code-x")] == 1

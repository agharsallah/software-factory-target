"""Hypothesis property tests for map and diff, run inside the ted_api conformance kit."""

from hypothesis import given, settings
from src.ted_watch.conformance.properties import (
    MAX_EXAMPLES,
    check_notice,
    mutated_notices,
    run_properties,
    validate_event,
)


@settings(max_examples=MAX_EXAMPLES, deadline=None)
@given(mutated_notices())
def test_conformance_hypothesis_map_never_raises_and_events_validate(item):
    """Map never raises; each diff event validates or is reported as unresolved."""
    _count, unresolved = check_notice(item)
    assert unresolved == [] or all(isinstance(entry, str) for entry in unresolved)


def test_conformance_hypothesis_validate_event_reports_missing_keys():
    """An empty event is unresolved, not valid."""
    assert validate_event({}) != []


def test_conformance_hypothesis_kit_run_properties():
    """The kit entry point runs the properties with a bounded max_examples."""
    assert run_properties(max_examples=10) == 0

"""Conformance kit for connector map and diff properties."""

from __future__ import annotations

from ..core.model import RawNotice
from .events import (
    EVENT_SCHEMA,
    check_map_and_diff,
    event_is_valid,
    validate_event,
)
from .strategy import mutated_fixture_json, mutated_raw_notice

DEFAULT_MAX_EXAMPLES = 50

__all__ = [
    "DEFAULT_MAX_EXAMPLES",
    "EVENT_SCHEMA",
    "check_map_and_diff",
    "event_is_valid",
    "mutated_fixture_json",
    "mutated_raw_notice",
    "run_map_diff_checks",
    "validate_event",
]


def run_map_diff_checks(
    connector: str = "ted_api",
    *,
    max_examples: int = DEFAULT_MAX_EXAMPLES,
) -> None:
    """Run the bounded map/diff property for ``connector``.

    Mutated inputs must not crash map. Every diff output either validates
    against the event schema or is reported as unresolved.
    """
    if max_examples < 1:
        raise ValueError("max_examples must be positive")

    from hypothesis import given, settings

    @settings(max_examples=max_examples, deadline=None, derandomize=True)
    @given(raw=mutated_raw_notice(connector))
    def _property(raw: RawNotice) -> None:
        report = check_map_and_diff(raw)
        if report not in {"valid", "unresolved"}:
            raise AssertionError(f"diff report {report!r} is neither valid nor unresolved")

    _property()

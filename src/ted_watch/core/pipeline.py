"""Pure pipeline: map, link, diff and dedupe raw notices into events."""

from collections.abc import Iterable

from .dedupe import Dedupe, Event
from .diff import DEFAULT_ATTRIBUTION, DEFAULT_COVERAGE, diff_notices
from .link import _candidate_keys, resolve_predecessor
from .map import map_raw_to_notice
from .model import Notice, RawNotice


def run_pipeline(
    raw_items: Iterable[RawNotice],
    *,
    coverage: str = DEFAULT_COVERAGE,
    attribution: str = DEFAULT_ATTRIBUTION,
) -> list[Event]:
    """Return exactly-once events for ``raw_items``, whatever their order or repeats.

    The predecessor index is built from the whole batch before any diff, so
    delivery order does not change which pointers resolve. No network is used.
    """
    notices: list[Notice] = [map_raw_to_notice(raw) for raw in raw_items]
    index: dict[str, Notice] = {}
    for notice in notices:
        for key in _candidate_keys(notice):
            index.setdefault(key, notice)
    events: list[Event] = []
    for notice in notices:
        previous = resolve_predecessor(notice, index)
        events.extend(diff_notices(previous, notice, coverage=coverage, attribution=attribution))
    return list(Dedupe(events))

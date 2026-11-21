"""Offline pipeline from a connector to deduped change events."""

from datetime import date, datetime
from pathlib import Path

from ..connectors import Connector
from .dedupe import Dedupe, Event
from .diff import diff, event_sort_key
from .link import resolve_predecessor
from .model import Notice
from .source import load_source

_SOURCE_PATH = Path(__file__).resolve().parents[1] / "connectors" / "ted_api" / "source.yaml"


def _coerce_date(value: date | datetime | str | None) -> date | None:
    """Return ``value`` as a date, or ``None`` when it is an open bound."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if text == "" or text.upper() == "D":
        return None
    return date.fromisoformat(text[:10])


def _notice_sort_key(notice: Notice) -> tuple[str, str, str]:
    """Order notices so a shuffled fetch still diffs in the same sequence."""
    published = notice.publication_date.isoformat()
    version = "" if notice.notice_version is None else str(notice.notice_version)
    return (published, notice.notice_id, version)


def _labels() -> tuple[str, str]:
    """Return coverage and attribution from the TED source file."""
    source = load_source(_SOURCE_PATH)
    return source.coverage, source.attribution


def run(
    connector: Connector,
    since: date | str | None = None,
    until: date | str | None = None,
) -> list[Event]:
    """Return deduped deadline_changed, suspension and cancellation events.

    Wires ``list_changes`` → ``fetch`` → ``map`` → predecessor link → diff →
    :class:`~ted_watch.core.dedupe.Dedupe`. The returned list does not depend
    on the order ``list_changes`` yields refs. An unresolved predecessor sets
    ``previous`` to ``None`` (unknown). The previous deadline is never guessed.
    """
    since_date = _coerce_date(since)
    until_date = _coerce_date(until)
    refs = list(connector.list_changes(since_date, until_date))
    notices = [connector.map(connector.fetch(ref)) for ref in refs]
    notices.sort(key=_notice_sort_key)
    index = {notice.notice_id: notice for notice in notices}
    coverage, attribution = _labels()
    events: list[Event] = []
    for notice in notices:
        predecessor = resolve_predecessor(notice, index)
        if predecessor is not None and predecessor.notice_id == notice.notice_id:
            predecessor = None
        events.extend(diff(notice, predecessor, coverage=coverage, attribution=attribution))
    deduped = list(Dedupe(events))
    deduped.sort(key=event_sort_key)
    return deduped

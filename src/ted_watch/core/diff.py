"""Diff a notice against its predecessor into change events.

``diff`` emits deadline_changed/suspension/cancellation events. ``diff_notices``
emits procedure events (``procedure_suspended``, ``cancellation_intended``).
"""

from datetime import date
from typing import Any

from .dedupe import Event
from .model import LotDeadline, Notice

DEADLINE_CHANGED = "deadline_changed"
SUSPENSION = "suspension"
CANCELLATION = "cancellation"

_EVENT_TYPES = (DEADLINE_CHANGED, SUSPENSION, CANCELLATION)


def _text(value: object) -> str | None:
    """Return a stripped string for ``value`` or ``None`` when empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def event_type_for(reason_code: str | None) -> str | None:
    """Map a change-reason code to an event type, or ``None`` when it is not a change.

    ``susp-review`` becomes suspension, ``cancel-intent`` becomes cancellation,
    and any other non-empty code other than ``none`` becomes deadline_changed.
    """
    code = _text(reason_code)
    if code is None:
        return None
    normalized = code.lower()
    if normalized == "none":
        return None
    if "susp" in normalized:
        return SUSPENSION
    if "cancel" in normalized:
        return CANCELLATION
    return DEADLINE_CHANGED


def _iso(value: date | None) -> str | None:
    """Return ``value`` as ``YYYY-MM-DD``, or ``None``."""
    if value is None:
        return None
    return value.isoformat()


def _utc(value: date | None) -> str | None:
    """Return midnight UTC for a date-only deadline, or ``None``."""
    if value is None:
        return None
    return value.isoformat() + "T00:00:00Z"


def _pointer(notice: Notice) -> str | None:
    """Return the predecessor pointer, if the notice has one."""
    return _text(getattr(notice, "change_notice_version_identifier", None))


def _lot_on(notice: Notice | None, lot_id: str) -> LotDeadline | None:
    """Return the lot with ``lot_id``, or ``None`` when that lot is absent.

    A missing lot is unknown. Another lot's deadline is never used as a stand-in.
    """
    if notice is None:
        return None
    for lot in notice.lots:
        if lot.lot_id == lot_id:
            return lot
    return None


def _reason(lot: LotDeadline | None, notice: Notice) -> str | None:
    """Prefer the lot reason; fall back to the notice reason only when the lot has none."""
    if lot is not None:
        lot_reason = _text(lot.deadline_change_reason_code)
        if lot_reason is not None:
            return lot_reason
    return _text(notice.change_reason_code)


def _event(
    notice: Notice,
    predecessor: Notice | None,
    *,
    event_type: str,
    kind: str,
    lot: str | None,
    previous: date | None,
    current: date | None,
    coverage: str,
    attribution: str,
) -> Event:
    """Build one event. ``previous`` is the predecessor deadline or unknown (``None``)."""
    source = _text(notice.url) or "ted.europa.eu"
    procedure = _text(notice.procedure_identifier)
    previous_notice = None if predecessor is None else predecessor.notice_id
    return {
        "event": event_type,
        "kind": kind,
        "lot": lot,
        "previous": _iso(previous),
        "current": _iso(current),
        "current_utc": _utc(current),
        "source": source,
        "coverage": coverage,
        "attribution": attribution,
        "procedure": procedure,
        "procedure_identifier": procedure,
        "previous_notice": previous_notice,
        "current_notice": notice.notice_id,
    }


def _emit(
    notice: Notice,
    predecessor: Notice | None,
    *,
    lot: LotDeadline | None,
    current: date | None,
    previous: date | None,
    lot_known: bool,
    coverage: str,
    attribution: str,
) -> Event | None:
    """Return an event when the reason or a known deadline difference says so.

    An unresolved predecessor, or a predecessor lot that is not present, leaves
    ``previous`` unknown. The missing value is never filled from another lot,
    the notice-level deadline, or the current deadline.
    """
    reason = _reason(lot, notice)
    event_type = event_type_for(reason)
    dates_differ = lot_known and previous != current
    unresolved = predecessor is None and _pointer(notice) is not None
    if event_type is None and not dates_differ and not unresolved:
        return None
    if event_type is None:
        event_type = DEADLINE_CHANGED
    kind = reason if reason is not None else event_type
    if event_type not in _EVENT_TYPES:
        return None
    return _event(
        notice,
        predecessor,
        event_type=event_type,
        kind=kind,
        lot=None if lot is None else lot.lot_id,
        previous=previous if lot_known else None,
        current=current,
        coverage=coverage,
        attribution=attribution,
    )


def diff(
    notice: Notice,
    predecessor: Notice | None,
    *,
    coverage: str = "EU tenders",
    attribution: str = "TED (ted.europa.eu)",
) -> list[Event]:
    """Return deadline_changed, suspension and cancellation events for ``notice``.

    ``predecessor`` is the linked notice, or ``None`` when the pointer does not
    resolve. Unresolved predecessors set ``previous`` to ``None`` (unknown).
    A deadline is never guessed.
    """
    events: list[Event] = []
    if notice.lots:
        for lot in notice.lots:
            pred_lot = _lot_on(predecessor, lot.lot_id)
            lot_known = pred_lot is not None
            previous = pred_lot.deadline if pred_lot is not None else None
            event = _emit(
                notice,
                predecessor,
                lot=lot,
                current=lot.deadline,
                previous=previous,
                lot_known=lot_known,
                coverage=coverage,
                attribution=attribution,
            )
            if event is not None:
                events.append(event)
        return events

    lot_known = predecessor is not None
    previous = predecessor.deadline if predecessor is not None else None
    event = _emit(
        notice,
        predecessor,
        lot=None,
        current=notice.deadline,
        previous=previous,
        lot_known=lot_known,
        coverage=coverage,
        attribution=attribution,
    )
    if event is not None:
        events.append(event)
    return events


def event_sort_key(event: Event | dict[str, Any]) -> tuple[str, ...]:
    """Return a total order so shuffled inputs still emit the same list."""
    fields = (
        "procedure",
        "current_notice",
        "previous_notice",
        "lot",
        "event",
        "kind",
        "current",
        "previous",
    )
    return tuple("" if event.get(name) is None else str(event.get(name)) for name in fields)


# Matches connectors/ted_api/source.yaml. Callers may override; this module does not read the file.
DEFAULT_COVERAGE = "EU tenders"
DEFAULT_ATTRIBUTION = "Source: TED (ted.europa.eu), © European Union"

# These codes never become a deadline_changed event, even when the deadline moved.
_PROCEDURE_EVENTS = {
    "susp-review": "procedure_suspended",
    "cancel-intent": "cancellation_intended",
}

_DEADLINE_EVENT = "deadline_changed"


def _normalize(value: object) -> str | None:
    """Return a stripped lower-case reason code, or ``None`` when absent."""
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _procedure_codes(notice: Notice) -> list[str]:
    """Return susp-review / cancel-intent codes on the notice or its lots, in order."""
    raw_codes: list[object] = [notice.change_reason_code]
    raw_codes.extend(lot.deadline_change_reason_code for lot in notice.lots)
    codes: list[str] = []
    for raw in raw_codes:
        code = _normalize(raw)
        if code in _PROCEDURE_EVENTS and code not in codes:
            codes.append(code)
    return codes


def _source_url(notice: Notice) -> str:
    """Return the notice URL, or the TED origin when the notice has none."""
    url = notice.url.strip() if isinstance(notice.url, str) else ""
    return url or "https://ted.europa.eu"


def _procedure_event(
    name: str,
    *,
    current: Notice,
    previous: Notice | None,
    kind: str,
    coverage: str,
    attribution: str,
) -> Event:
    """Build one procedure event. Personal-data fields are not copied."""
    event: Event = {
        "event": name,
        "notice": current.notice_id,
        "source": _source_url(current),
        "coverage": coverage,
        "attribution": attribution,
        "kind": kind,
        "current_notice": current.notice_id,
    }
    if current.procedure_identifier:
        event["procedure"] = current.procedure_identifier
    if previous is not None:
        event["previous_notice"] = previous.notice_id
    return event


def diff_notices(
    previous: Notice | None,
    current: Notice,
    *,
    coverage: str = DEFAULT_COVERAGE,
    attribution: str = DEFAULT_ATTRIBUTION,
) -> list[Event]:
    """Return procedure events for ``current``, never a deadline_changed event.

    ``susp-review`` yields ``procedure_suspended``. ``cancel-intent`` yields
    ``cancellation_intended``. Other reason codes yield nothing. Each event
    carries the notice id, source URL, coverage and attribution. Deadline
    values and personal data are not copied.
    """
    events: list[Event] = []
    for code in _procedure_codes(current):
        name = _PROCEDURE_EVENTS[code]
        if name == _DEADLINE_EVENT:
            continue
        events.append(
            _procedure_event(
                name,
                current=current,
                previous=previous,
                kind=code,
                coverage=coverage,
                attribution=attribution,
            )
        )
    return events

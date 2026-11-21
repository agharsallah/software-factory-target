"""Diff notices into suspension and intended-cancellation events."""

from .dedupe import Event
from .model import Notice

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

"""Conformance checks for formats, event kinds, redaction and attribution."""

import json
import re
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ..core.map import map_raw_to_notice
from ..core.model import Notice, RawNotice

# Brief attribution string required on every output event.
ATTRIBUTION = "Source: TED (ted.europa.eu), © European Union"
# Coverage label required on every output event.
COVERAGE = "EU tenders"

DEADLINE_CHANGED = "deadline_changed"
_DEADLINE_EVENTS = frozenset({DEADLINE_CHANGED, "deadline_change"})
_NO_EVENT = frozenset({"", "none", "null"})

# Reason code -> event type we emit. Aliases are accepted by the check.
PRIMARY_EVENT_TYPE = {
    "susp-review": "suspension",
    "cancel-intent": "cancel_intent",
}
OWN_EVENT_TYPES = {
    "susp-review": frozenset({"suspension", "susp-review", "susp_review"}),
    "cancel-intent": frozenset(
        {"cancel_intent", "cancel-intent", "intended_cancellation", "cancellation"}
    ),
}

_TIMESTAMP_KEYS = frozenset(
    {"current", "previous", "current_utc", "currentUtc", "fetched_at", "fetchedAt"}
)
_DATE_KEYS = frozenset(
    {
        "deadline",
        "publication_date",
        "publicationDate",
        "submissionDeadline",
        "submission_deadline",
    }
)
_COUNTRY_KEYS = frozenset(
    {
        "country",
        "buyer_country",
        "buyerCountry",
        "buyer-country",
        "authority_country",
        "authorityCountry",
        "authority-country",
    }
)
_CPV_KEYS = frozenset(
    {
        "cpv",
        "cpv_code",
        "cpv_codes",
        "cpvCodes",
        "classification-cpv",
        "classification_cpv",
    }
)

_ISO_OFFSET_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_COUNTRY = re.compile(r"[A-Z]{2}|[A-Z]{3}")
_CPV_CODE = re.compile(r"\d{8}(?:-\d)?")
_EMAIL_RE = re.compile(r"(?<![\w.+-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE_RE = re.compile(
    r"(?<![\w/])(?:\+[1-9]\d{0,2}|00[1-9]\d{0,2})(?:[\s.\-()]*\d){6,14}(?![\w@])"
)

_REASON_KEYS = (
    "changeReasonCode",
    "change_reason_code",
    "change-reason-code",
)
_LOT_REASON_KEYS = (
    "deadlineChangeReasonCode",
    "changeReasonCode",
    "deadline_change_reason_code",
    "change_reason_code",
    "change-reason-code",
)


def check_formats(payload: Any) -> list[str]:
    """Return format violations for timestamps, buyer country and CPV codes.

    Timestamps must be ISO 8601 with a numeric offset or ``Z``. Buyer country
    must be ISO 3166 alpha-2 or alpha-3. CPV codes must be 8 digits with an
    optional check digit. An empty list means the payload conforms.
    """
    violations: list[str] = []
    _walk_formats(payload, "", violations)
    return violations


def check_event_kinds(items: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return violations for suspension and intended-cancellation events.

    A fixture or event whose reason is ``susp-review`` or ``cancel-intent``
    must yield that reason's own event type, or no event, never
    ``deadline_changed``.
    """
    violations: list[str] = []
    for index, item in enumerate(items):
        if _is_output_event(item):
            violations.extend(_kind_violations(item, f"[{index}]"))
        else:
            violations.extend(_fixture_kind_violations(item, f"[{index}]"))
    return violations


def check_redaction(serialized_events: str | Sequence[Any]) -> list[str]:
    """Regex-scan serialized events for an email address or phone number.

    Returns one violation per match. An empty list means no contact data
    survived into the serialized events.
    """
    if not isinstance(serialized_events, str):
        text = json.dumps(serialized_events, ensure_ascii=False)
    else:
        text = serialized_events
    violations: list[str] = []
    for match in _EMAIL_RE.finditer(text):
        violations.append(f"email:{match.group(0)}")
    for match in _PHONE_RE.finditer(text):
        violations.append(f"phone:{match.group(0)}")
    return violations


def check_attribution(events: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return violations when an event lacks the attribution string or coverage label."""
    violations: list[str] = []
    for index, event in enumerate(events):
        if event.get("attribution") != ATTRIBUTION:
            violations.append(f"event[{index}]: missing attribution string")
        if event.get("coverage") != COVERAGE:
            violations.append(f"event[{index}]: missing coverage label")
    return violations


def events_from_notice(notice: Notice) -> list[dict[str, Any]]:
    """Build output events for ``notice``.

    Personal contact fields are never copied. Suspension and intended
    cancellation get their own event types, never ``deadline_changed``.
    """
    events: list[dict[str, Any]] = []
    if notice.lots:
        for lot in notice.lots:
            reason = lot.deadline_change_reason_code or notice.change_reason_code
            event_type = _event_type(reason)
            if event_type is None:
                continue
            if event_type == DEADLINE_CHANGED and lot.deadline is None:
                continue
            events.append(_make_event(notice, lot.lot_id, lot.deadline, event_type, reason))
        return events

    event_type = _event_type(notice.change_reason_code)
    if event_type is None:
        return events
    if event_type == DEADLINE_CHANGED and notice.deadline is None:
        return events
    events.append(_make_event(notice, None, notice.deadline, event_type, notice.change_reason_code))
    return events


def events_from_fixture(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Map a raw fixture dict to output events. Pure: no network, no I/O."""
    raw = RawNotice.model_validate(dict(data))
    return events_from_notice(map_raw_to_notice(raw))


def run_checks(fixtures: Sequence[Mapping[str, Any]]) -> list[str]:
    """Run formats, event-kind, redaction and attribution checks on fixtures.

    ``fixtures`` are in-memory connector records, such as the ted_api JSON
    fixtures. Returns violation messages; an empty list means they conform.
    No network calls.
    """
    violations: list[str] = []
    for index, fixture in enumerate(fixtures):
        label = f"fixture[{index}]"
        notice = map_raw_to_notice(RawNotice.model_validate(dict(fixture)))
        events = events_from_notice(notice)
        record = {
            "buyer_country": notice.country,
            "authority_country": notice.authority_country,
            "cpv_codes": list(notice.cpv_codes),
            "events": events,
        }
        serialized = json.dumps(events, ensure_ascii=False)
        violations.extend(_tag(label, check_formats(fixture)))
        violations.extend(_tag(label, check_formats(record)))
        violations.extend(_tag(label, check_event_kinds([fixture])))
        violations.extend(_tag(label, check_redaction(serialized)))
        violations.extend(_tag(label, check_attribution(events)))
    return violations


def load_connector_fixtures(connector: str = "ted_api") -> list[dict[str, Any]]:
    """Load a connector's JSON fixtures. Pure read of on-disk fixtures; no network."""
    root = Path(__file__).resolve().parents[3] / "fixtures" / "connectors" / connector / "fixtures"
    loaded: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        loaded.append(json.loads(path.read_text(encoding="utf-8")))
    return loaded


def run_connector_checks(connector: str = "ted_api") -> list[str]:
    """Run all four checks against a connector's fixtures.

    Defaults to the ted_api connector. An empty list means the fixtures conform.
    """
    return run_checks(load_connector_fixtures(connector))


def _tag(label: str, found: list[str]) -> list[str]:
    """Prefix violation messages with the fixture label."""
    return [f"{label}: {item}" for item in found]


def _walk_formats(value: Any, prefix: str, violations: list[str]) -> None:
    """Walk ``value`` and append format violations."""
    if isinstance(value, BaseModel):
        _walk_formats(value.model_dump(mode="json"), prefix, violations)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            _check_format_key(str(key), item, path, violations)
            _walk_formats(item, path, violations)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk_formats(item, f"{prefix}[{index}]", violations)


def _check_format_key(key: str, item: Any, path: str, violations: list[str]) -> None:
    """Validate one keyed value for timestamp, country or CPV shape."""
    if key in _TIMESTAMP_KEYS:
        if item is not None and not _is_offset_timestamp(item):
            violations.append(f"{path}: not an ISO offset timestamp")
        return
    if key in _DATE_KEYS:
        if item is not None and not (_is_iso_date(item) or _is_offset_timestamp(item)):
            violations.append(f"{path}: not an ISO date or ISO offset timestamp")
        return
    if key in _COUNTRY_KEYS:
        if not _is_country(item):
            violations.append(f"{path}: not an ISO 3166 alpha-2 or alpha-3 code")
        return
    if key in _CPV_KEYS:
        violations.extend(_cpv_violations(item, path))


def _is_offset_timestamp(value: Any) -> bool:
    """Return True when ``value`` is an ISO 8601 timestamp with an offset."""
    if isinstance(value, datetime):
        return value.tzinfo is not None
    if not isinstance(value, str) or not _ISO_OFFSET_TS.fullmatch(value.strip()):
        return False
    try:
        datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_iso_date(value: Any) -> bool:
    """Return True when ``value`` is an ISO calendar date."""
    if isinstance(value, datetime):
        return False
    if isinstance(value, date):
        return True
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value.strip()):
        return False
    try:
        date.fromisoformat(value.strip())
    except ValueError:
        return False
    return True


def _is_country(value: Any) -> bool:
    """Return True when ``value`` is an ISO 3166 alpha-2 or alpha-3 code."""
    if not isinstance(value, str):
        return False
    return _ISO_COUNTRY.fullmatch(value.strip().upper()) is not None


def _cpv_violations(value: Any, path: str) -> list[str]:
    """Return shape violations for one CPV code or a list of them."""
    codes = value if isinstance(value, list) else [value]
    violations: list[str] = []
    for code in codes:
        text = str(code).strip() if code is not None else ""
        if _CPV_CODE.fullmatch(text) is None:
            violations.append(f"{path}: CPV code {code!r} has invalid shape")
    return violations


def _is_output_event(item: Mapping[str, Any]) -> bool:
    """Return True when ``item`` is an output event rather than a notice fixture."""
    return "event" in item and "noticeId" not in item and "notice_id" not in item


def _kind_violations(event: Mapping[str, Any], path: str) -> list[str]:
    """Return a violation when a protected reason yielded a deadline event."""
    kind = _normalized_reason(event.get("kind"))
    event_type = str(event.get("event") or "")
    expected = PRIMARY_EVENT_TYPE.get(kind)
    allowed = OWN_EVENT_TYPES.get(kind)
    if allowed is None:
        return []
    if event_type in allowed:
        return []
    if event_type in _DEADLINE_EVENTS:
        return [f"{path}: kind {kind} yielded deadline_changed; expected {expected} or none"]
    shown = event_type or "none"
    return [f"{path}: kind {kind} yielded {shown}; expected {expected} or none"]


def _fixture_kind_violations(data: Mapping[str, Any], path: str) -> list[str]:
    """Check events yielded by a notice fixture. No event is a pass."""
    events = events_from_fixture(data)
    violations: list[str] = []
    for index, event in enumerate(events):
        violations.extend(_kind_violations(event, f"{path}.events[{index}]"))
    reasons = set(_collect_reasons(data))
    if reasons & set(PRIMARY_EVENT_TYPE):
        for index, event in enumerate(events):
            if str(event.get("event") or "") in _DEADLINE_EVENTS:
                message = (
                    f"{path}.events[{index}]: susp-review/cancel-intent yielded deadline_changed"
                )
                if message not in violations:
                    violations.append(message)
    return violations


def _collect_reasons(data: Mapping[str, Any]) -> list[str]:
    """Collect normalized change-reason codes from a notice fixture."""
    reasons: list[str] = []
    for key in _REASON_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            reasons.append(value.strip().lower())
    lots = data.get("lots") or []
    if isinstance(lots, list):
        for lot in lots:
            if not isinstance(lot, Mapping):
                continue
            for key in _LOT_REASON_KEYS:
                value = lot.get(key)
                if isinstance(value, str) and value.strip():
                    reasons.append(value.strip().lower())
                    break
    return reasons


def _normalized_reason(value: object) -> str:
    """Return a stripped lowercase reason code."""
    if value is None:
        return ""
    return str(value).strip().lower()


def _event_type(reason: object) -> str | None:
    """Map a reason code to an event type, or None when no event is emitted."""
    code = _normalized_reason(reason)
    if code in _NO_EVENT:
        return None
    return PRIMARY_EVENT_TYPE.get(code, DEADLINE_CHANGED)


def _timestamp(value: date | None) -> str | None:
    """Render a date as an ISO timestamp with a UTC offset."""
    if value is None:
        return None
    return f"{value.isoformat()}T00:00:00+00:00"


def _make_event(
    notice: Notice,
    lot_id: str | None,
    deadline: date | None,
    event_type: str,
    reason: object,
) -> dict[str, Any]:
    """Build one output event from allow-listed fields only."""
    current = _timestamp(deadline)
    kind = str(reason).strip() if reason is not None else ""
    return {
        "event": event_type,
        "kind": kind,
        "lot": lot_id,
        "previous": None,
        "current": current,
        "current_utc": current,
        "source": notice.url if notice.url else "https://ted.europa.eu",
        "coverage": COVERAGE,
        "attribution": ATTRIBUTION,
    }

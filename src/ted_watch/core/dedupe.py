"""Stable event ids and exactly-once dedupe for deadline changes."""

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, TypedDict

# Identity fields, in contract order. Aliases cover CLI dicts (previous/current)
# and notice-shaped events (previous_notice/current_notice) without mixing them
# when both are present: explicit notice fields win over deadline fallbacks.
_PROCEDURE_FIELDS = ("procedure", "procedure_identifier", "procedure_id")
_LOT_FIELDS = ("lot", "lot_id")
_KIND_FIELDS = ("kind",)
_PREVIOUS_NOTICE_FIELDS = (
    "previous_notice",
    "previousNotice",
    "prev_notice",
    "prev",
    "previous",
)
_CURRENT_NOTICE_FIELDS = (
    "current_notice",
    "currentNotice",
    "curr_notice",
    "current",
)
_IDENTITY_FIELDS = (
    _PROCEDURE_FIELDS,
    _LOT_FIELDS,
    _KIND_FIELDS,
    _PREVIOUS_NOTICE_FIELDS,
    _CURRENT_NOTICE_FIELDS,
)


class Event(TypedDict, total=False):
    """Deadline-change or procedure event, plus logical-change identity."""

    event: str
    notice: str
    kind: str
    lot: str | None
    previous: str | None
    current: str | None
    current_utc: str | None
    source: str
    coverage: str
    attribution: str
    procedure: str | None
    procedure_identifier: str | None
    previous_notice: str | None
    current_notice: str | None


def _lookup(event: Any, names: tuple[str, ...]) -> Any:
    """Return the first present, non-null field from ``event``."""
    if isinstance(event, Mapping):
        for name in names:
            if name in event and event[name] is not None:
                return event[name]
        return None
    for name in names:
        value = getattr(event, name, None)
        if value is not None:
            return value
    return None


def _text(value: Any) -> str:
    """Normalize an identity component to a stable string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def event_id(event: Event | Mapping[str, Any] | Any) -> str:
    """Return a deterministic hash of procedure, lot, kind, previous notice and current notice.

    The digest is SHA-256 over those five components in that order. Deadline
    values and delivery order are not part of the identity.
    """
    parts = [_text(_lookup(event, names)) for names in _IDENTITY_FIELDS]
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class Dedupe:
    """Emit each logical change once, whatever the order or repeats.

    A single instance is an exactly-once store: later calls remember ids already
    emitted. Constructing ``Dedupe(events)`` dedupes that batch immediately.
    """

    def __init__(self, events: Iterable[Any] | None = None) -> None:
        self._seen: set[str] = set()
        self._emitted: list[Any] = []
        if events is not None:
            self.extend(events)

    def extend(self, events: Iterable[Any]) -> list[Any]:
        """Record ``events`` and return those whose ids have not been seen."""
        fresh: list[Any] = []
        for event in events:
            eid = event_id(event)
            if eid in self._seen:
                continue
            self._seen.add(eid)
            self._emitted.append(event)
            fresh.append(event)
        return fresh

    def emit(self, events: Iterable[Any]) -> Iterator[Any]:
        """Yield events whose logical-change id has not been seen yet."""
        yield from self.extend(events)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._emitted)

    def __len__(self) -> int:
        return len(self._emitted)

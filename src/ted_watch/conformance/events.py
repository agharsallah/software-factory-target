"""Event schema checks for diff output."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..core.map import map_raw_to_notice
from ..core.model import Notice, RawNotice

# Deadline-change event shape. Extra keys are allowed; known keys are typed.
EVENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["event"],
    "additionalProperties": True,
    "properties": {
        "event": {
            "type": "string",
            "enum": [
                "deadline_changed",
                "deadline_change",
                "suspension",
                "intended_cancellation",
                "intended-cancellation",
                "cancellation",
            ],
        },
        "kind": {"type": ["string", "null"]},
        "lot": {"type": ["string", "null"]},
        "previous": {"type": ["string", "null"]},
        "current": {"type": ["string", "null"]},
        "current_utc": {"type": ["string", "null"]},
        "source": {"type": ["string", "null"]},
        "coverage": {"type": ["string", "null"]},
        "attribution": {"type": ["string", "null"]},
    },
}

_DIFF_NAMES = (
    "diff_notices",
    "diff",
    "diff_deadlines",
    "deadline_diff",
    "diff_lots",
)

_MISSING = object()


def _matches_type(value: object, spec: str | list[str]) -> bool:
    if isinstance(spec, list):
        return any(_matches_type(value, item) for item in spec)
    if spec == "string":
        return isinstance(value, str)
    if spec == "null":
        return value is None
    if spec == "object":
        return isinstance(value, dict)
    return True


def event_is_valid(event: object) -> bool:
    """Return True when ``event`` matches ``EVENT_SCHEMA``."""
    if not isinstance(event, dict):
        return False
    for key in EVENT_SCHEMA["required"]:
        if key not in event:
            return False
    properties = EVENT_SCHEMA["properties"]
    event_name = event.get("event")
    allowed = properties["event"]["enum"]
    if not isinstance(event_name, str) or event_name not in allowed:
        return False
    for key, spec in properties.items():
        if key not in event or key == "event":
            continue
        if not _matches_type(event[key], spec["type"]):
            return False
    return True


def validate_event(event: object) -> None:
    """Raise ValueError when ``event`` does not match the event schema."""
    if not event_is_valid(event):
        raise ValueError("diff produced an invalid event")


def _load_diff() -> Callable[..., Any] | None:
    """Import core.diff when present; otherwise report that diff is unavailable."""
    try:
        from ..core import diff as diff_mod
    except ImportError:
        return None
    for name in _DIFF_NAMES:
        fn = getattr(diff_mod, name, None)
        if callable(fn):
            return fn
    return None


def _invoke_diff(diff_fn: Callable[..., Any], previous: Notice | None, current: Notice) -> Any:
    try:
        return diff_fn(previous, current)
    except TypeError:
        return diff_fn(current)


def _is_unresolved(events: object) -> bool:
    if events is None or events == "unresolved":
        return True
    if isinstance(events, dict) and events.get("status") == "unresolved":
        return True
    return False


def classify_diff(
    previous: Notice | None,
    current: Notice,
    diff_fn: Callable[..., Any] | None,
) -> str:
    """Return ``valid`` or ``unresolved``. Invalid events raise ValueError."""
    if diff_fn is None:
        return "unresolved"
    events = _invoke_diff(diff_fn, previous, current)
    if _is_unresolved(events):
        return "unresolved"
    if not isinstance(events, list):
        raise ValueError("diff produced an invalid event")
    for event in events:
        if isinstance(event, dict) and event.get("status") == "unresolved":
            continue
        validate_event(event)
    return "valid"


def check_map_and_diff(
    raw: RawNotice,
    diff_fn: Callable[..., Any] | None | object = _MISSING,
) -> str:
    """Map ``raw`` and classify diff output as ``valid`` or ``unresolved``.

    Mapping errors propagate. When core.diff is missing the outcome is
    ``unresolved``. An event that fails ``EVENT_SCHEMA`` raises ValueError.
    """
    current = map_raw_to_notice(raw)
    fn = _load_diff() if diff_fn is _MISSING else diff_fn
    if fn is not None and not callable(fn):
        return "unresolved"
    return classify_diff(None, current, fn if callable(fn) else None)

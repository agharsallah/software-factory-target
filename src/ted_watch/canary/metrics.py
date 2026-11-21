"""Canary metrics over a batch of mapped notices: pointer share, field presence, volume.

Pure functions: no network, no TED calls, no file access.
"""

from typing import Any

from ..core.link import _candidate_keys, resolve_predecessor
from ..core.model import Notice

FIELDS = (
    "notice_id",
    "publication_number",
    "notice_identifier",
    "procedure_identifier",
    "country",
    "cpv_codes",
    "lots",
    "deadline",
)
DEFAULT_TOLERANCE = 0.05


def build_links(notices: list[Notice]) -> dict[str, Notice]:
    """Build the ``links`` index (candidate key -> notice) for a batch."""
    index: dict[str, Notice] = {}
    for notice in notices:
        for key in _candidate_keys(notice):
            index[key] = notice
    return index


def _present(value: object) -> bool:
    """Return True when ``value`` is neither empty nor blank."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | dict | set):
        return len(value) > 0
    return True


def compute(notices: list[Notice], links: dict[str, Notice]) -> dict[str, Any]:
    """Compute canary metrics for ``notices``.

    ``links`` is the index supplied by the caller (see :func:`build_links`), and may
    contain notices outside the batch. ``n_changes`` counts notices with a predecessor
    pointer; ``resolved_pointer_share`` is resolved / n_changes, or ``None`` when the
    batch has no changes. ``field_presence`` maps each field to its rate in [0, 1].
    """
    n_notices = len(notices)
    changes = [
        n for n in notices if _present(getattr(n, "change_notice_version_identifier", None))
    ]
    resolved = sum(1 for n in changes if resolve_predecessor(n, links) is not None)
    share = resolved / len(changes) if changes else None
    presence = {
        field: (
            sum(1 for n in notices if _present(getattr(n, field, None))) / n_notices
            if n_notices
            else 0.0
        )
        for field in FIELDS
    }
    return {
        "n_notices": n_notices,
        "n_changes": len(changes),
        "resolved_pointer_share": share,
        "field_presence": presence,
    }


def check(metrics: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Return alert strings comparing ``metrics`` with ``baseline``.

    Baseline keys (all optional): ``resolved_pointer_share``, ``tolerance``,
    ``field_presence``, ``min_notices``, ``max_notices``.
    """
    alerts: list[str] = []
    n_notices = metrics["n_notices"]
    if n_notices == 0:
        alerts.append("empty result: no notices in batch")

    share = metrics.get("resolved_pointer_share")
    base_share = baseline.get("resolved_pointer_share")
    tolerance = baseline.get("tolerance", DEFAULT_TOLERANCE)
    if share is not None and base_share is not None and share < base_share - tolerance:
        alerts.append(
            f"resolved pointer share {share:.2f} below baseline {base_share:.2f} "
            f"- tolerance {tolerance:.2f}"
        )

    current = metrics.get("field_presence", {})
    for field, rate in baseline.get("field_presence", {}).items():
        if rate > 0 and current.get(field, 0.0) == 0:
            alerts.append(f"field missing: {field} (baseline presence {rate:.2f})")

    low = baseline.get("min_notices")
    high = baseline.get("max_notices")
    if n_notices > 0 and (
        (low is not None and n_notices < low) or (high is not None and n_notices > high)
    ):
        alerts.append(f"volume {n_notices} outside baseline range [{low}, {high}]")
    return alerts

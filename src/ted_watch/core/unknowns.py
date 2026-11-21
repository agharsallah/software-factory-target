"""Aggregate unmapped values observed while mapping notices.

``map_raw_to_notice`` records each unknown as ``{"kind", "value"}``. Kinds:

- ``change-reason-code`` — value is an unrecognised change-reason code
- ``pointer`` — value is a pointer that is not UUID+version or a publication number
- ``lot-arrays`` — value describes lot arrays whose lengths do not match
"""

from collections import Counter
from collections.abc import Iterable

from .model import Notice


def aggregate(notices: Iterable[Notice]) -> Counter[tuple[str, str]]:
    """Count unknowns across notices, keyed by ``(kind, value)``.

    Pure: reads each notice's ``unknowns`` list and writes nothing global.
    """
    counts: Counter[tuple[str, str]] = Counter()
    for notice in notices:
        for item in notice.unknowns:
            if not isinstance(item, dict):
                continue
            kind = item.get("kind")
            value = item.get("value")
            if kind is None or value is None:
                continue
            counts[(str(kind), str(value))] += 1
    return counts

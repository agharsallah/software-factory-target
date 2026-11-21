"""Pure request-body helper for the TED search API; makes no network calls."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .query import FIELDS, build_query


def build_search_body(
    cpv_division: str, countries: Sequence[str], since: str, until: str, limit: int = 100
) -> dict[str, Any]:
    """Return the JSON body for a TED v3 notice search using the shared query and fields."""
    return {
        "query": build_query(cpv_division, countries, since, until),
        "fields": list(FIELDS),
        "limit": limit,
        "paginationMode": "ITERATION",
    }

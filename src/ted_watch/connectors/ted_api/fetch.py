"""Pure request-body helper for the TED search API; makes no network calls."""

from datetime import date

from .query import FIELDS, build_query


def build_search_body(
    cpv_division: str,
    countries: list[str],
    since: date | str,
    until: date | str,
    limit: int = 100,
) -> dict[str, object]:
    """Return a TED v3 search body for the given division, countries and window.

    The expert query and field list come from :func:`build_query` and
    :data:`FIELDS`. This module does not inline them.
    """
    return {
        "query": build_query(cpv_division, countries, since, until),
        "fields": list(FIELDS),
        "limit": limit,
        "paginationMode": "ITERATION",
    }

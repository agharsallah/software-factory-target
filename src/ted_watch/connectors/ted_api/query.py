"""Pure TED expert-query builder for one CPV division and 1-2 buyer countries."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from typing import Final

FIELDS: Final[tuple[str, ...]] = (
    "publication-number",
    "notice-identifier",
    "notice-version",
    "procedure-identifier",
    "change-notice-version-identifier",
    "change-reason-code",
    "identifier-lot",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-tender-time-lot",
    "deadline-receipt-request-date-lot",
    "buyer-country",
    "classification-cpv",
    "notice-type",
    "links",
)

_DIVISION = re.compile(r"[0-9]{2}")
_COUNTRY = re.compile(r"[A-Z]{2}")
_MAX_COUNTRIES: Final[int] = 2


def _check_division(value: str) -> str:
    """Return ``value`` if it is a 2-digit CPV division, else raise ValueError."""
    if not isinstance(value, str) or not _DIVISION.fullmatch(value):
        raise ValueError(f"CPV division must be exactly 2 digits: {value!r}")
    return value


def _check_countries(values: Sequence[str]) -> list[str]:
    """Return the ISO 3166-1 alpha-2 codes, or raise ValueError."""
    if isinstance(values, str) or not 1 <= len(values) <= _MAX_COUNTRIES:
        raise ValueError("expected 1 or 2 buyer countries")
    for value in values:
        if not isinstance(value, str) or not _COUNTRY.fullmatch(value):
            raise ValueError(f"country must be an ISO alpha-2 code like 'DE': {value!r}")
    return list(values)


def _check_date(value: str) -> str:
    """Return ``value`` (YYYY-MM-DD) as TED's YYYYMMDD, or raise ValueError."""
    try:
        return date.fromisoformat(value).strftime("%Y%m%d")
    except (TypeError, ValueError):
        raise ValueError(f"date must be YYYY-MM-DD: {value!r}") from None


def build_query(cpv_division: str, countries: Sequence[str], since: str, until: str) -> str:
    """Build a TED expert query for change notices of one CPV division.

    Change notices are those with a ``change-notice-version-identifier``. Both date bounds are
    required (YYYY-MM-DD) and inclusive. Raises ValueError on any invalid input.
    """
    division = _check_division(cpv_division)
    codes = _check_countries(countries)
    start = _check_date(since)
    end = _check_date(until)
    if start > end:
        raise ValueError(f"since is after until: {since!r} > {until!r}")
    country_clause = " OR ".join(f"buyer-country={code}" for code in codes)
    return (
        f"({country_clause}) AND classification-cpv={division}* "
        f"AND publication-date>={start} AND publication-date<={end} "
        "AND change-notice-version-identifier IS NOT EMPTY"
    )

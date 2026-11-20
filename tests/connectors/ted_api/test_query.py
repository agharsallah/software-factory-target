"""Tests for the TED expert query builder."""

from datetime import date, datetime

import pytest
from src.ted_watch.connectors.ted_api.fetch import build_search_body
from src.ted_watch.connectors.ted_api.query import FIELDS, build_query

_SINCE = date(2024, 1, 1)
_UNTIL = date(2024, 1, 31)
_REASONS = "update-add cor-buy cor-pub info-release susp-review cancel-intent"


def test_fields_are_the_fourteen_brief_fields() -> None:
    """FIELDS is the 14 TED v3 fields used to detect deadline changes."""
    assert FIELDS == [
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
    ]
    assert len(FIELDS) == 14
    assert len(set(FIELDS)) == 14


@pytest.mark.parametrize(
    ("division", "countries", "since", "until", "expected"),
    [
        (
            "72",
            ["DE"],
            _SINCE,
            _UNTIL,
            (
                "buyer-country = DE "
                "AND classification-cpv = 72* "
                "AND publication-date >= 2024-01-01 "
                "AND publication-date <= 2024-01-31 "
                f"AND change-reason-code IN ({_REASONS})"
            ),
        ),
        (
            "45",
            ["DE", "PL"],
            "2024-03-01",
            "2024-03-31",
            (
                "buyer-country IN (DE PL) "
                "AND classification-cpv = 45* "
                "AND publication-date >= 2024-03-01 "
                "AND publication-date <= 2024-03-31 "
                f"AND change-reason-code IN ({_REASONS})"
            ),
        ),
        (
            "09",
            ["fr", "deu"],
            "20240301",
            datetime(2024, 6, 30, 15, 0),
            (
                "buyer-country IN (FR DEU) "
                "AND classification-cpv = 09* "
                "AND publication-date >= 2024-03-01 "
                "AND publication-date <= 2024-06-30 "
                f"AND change-reason-code IN ({_REASONS})"
            ),
        ),
    ],
)
def test_build_query_exact(
    division: str,
    countries: list[str],
    since: date | str | datetime,
    until: date | str | datetime,
    expected: str,
) -> None:
    """Query text matches the expert-search fragments for the inputs."""
    assert build_query(division, countries, since, until) == expected


def test_build_query_contains_required_filters() -> None:
    """Output contains country filters, a CPV prefix match, and the date range."""
    query = build_query("72", ["DE", "PL"], _SINCE, _UNTIL)
    assert "buyer-country" in query
    assert "DE" in query
    assert "PL" in query
    assert "classification-cpv = 72*" in query
    assert "publication-date >= 2024-01-01" in query
    assert "publication-date <= 2024-01-31" in query
    assert "change-reason-code" in query


def test_build_query_is_pure() -> None:
    """Same inputs always produce the same query string."""
    first = build_query("72", ["DE"], _SINCE, _UNTIL)
    second = build_query("72", ["DE"], _SINCE, _UNTIL)
    assert first == second
    assert isinstance(first, str)


@pytest.mark.parametrize("division", ["7", "720", "7A", "AB", "", "72*", " 7 ", "7 2"])
def test_invalid_division_raises(division: str) -> None:
    """A division that is not exactly two digits raises ValueError."""
    with pytest.raises(ValueError):
        build_query(division, ["DE"], _SINCE, _UNTIL)


@pytest.mark.parametrize(
    "country",
    ["XX", "ZZ", "ZZZ", "Germany", "D", "UK", "EL", "123", "DEUT", ""],
)
def test_non_iso_country_raises(country: str) -> None:
    """A non-ISO country code raises ValueError."""
    with pytest.raises(ValueError):
        build_query("72", [country], _SINCE, _UNTIL)


def test_non_iso_country_among_valid_raises() -> None:
    """One invalid code rejects the whole country list."""
    with pytest.raises(ValueError):
        build_query("72", ["DE", "XX"], _SINCE, _UNTIL)


def test_fetch_uses_build_query_and_fields() -> None:
    """fetch builds the search body from build_query and FIELDS, not inline strings."""
    body = build_search_body("72", ["PL"], _SINCE, _UNTIL)
    assert body["query"] == build_query("72", ["PL"], _SINCE, _UNTIL)
    assert body["fields"] == FIELDS
    assert body["fields"] is not FIELDS

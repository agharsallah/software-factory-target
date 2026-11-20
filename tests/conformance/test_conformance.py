"""Tests for conformance checks against ted_api fixtures."""

import json
from pathlib import Path

import pytest
from src.ted_watch.conformance import (
    check_attribution,
    check_event_kinds,
    check_formats,
    check_redaction,
)
from src.ted_watch.conformance import checks as checks_module
from src.ted_watch.conformance.checks import (
    ATTRIBUTION,
    COVERAGE,
    events_from_fixture,
    events_from_notice,
    run_checks,
    run_connector_checks,
)
from src.ted_watch.core.map import map_raw_to_notice
from src.ted_watch.core.model import RawNotice

FIXTURE_DIR = (
    Path(__file__).parent.parent.parent / "fixtures" / "connectors" / "ted_api" / "fixtures"
)


def load_fixture(name: str) -> dict:
    """Load a ted_api fixture JSON object."""
    path = FIXTURE_DIR / name
    with path.open() as handle:
        return json.load(handle)


@pytest.fixture(params=sorted(path.name for path in FIXTURE_DIR.glob("*.json")))
def fixture_name(request) -> str:
    """Parametrized ted_api fixture name."""
    return request.param


def test_checks_are_importable_from_conformance() -> None:
    """The four checks are exported by the conformance package."""
    assert checks_module.check_formats is check_formats
    assert checks_module.check_event_kinds is check_event_kinds
    assert checks_module.check_redaction is check_redaction
    assert checks_module.check_attribution is check_attribution


def test_attribution_string_and_coverage_label() -> None:
    """Events must carry the brief attribution string and the coverage label."""
    assert ATTRIBUTION == "Source: TED (ted.europa.eu), © European Union"
    assert COVERAGE == "EU tenders"


def test_check_formats_accepts_iso_shapes() -> None:
    """ISO offset timestamps, alpha-2/alpha-3 countries and CPV shape pass."""
    assert (
        check_formats(
            {
                "current": "2024-06-30T12:00:00+02:00",
                "current_utc": "2024-06-30T10:00:00Z",
                "previous": None,
                "buyer_country": "DEU",
                "authority_country": "DE",
                "cpv_codes": ["72000000", "45210000-1"],
            }
        )
        == []
    )


def test_check_formats_rejects_bad_values() -> None:
    """Naive timestamps, non-ISO countries and short CPV codes are violations."""
    assert check_formats(
        {
            "current": "2024-06-30T12:00:00",
            "buyer_country": "Germany",
            "cpv_codes": ["72"],
        }
    ) == [
        "current: not an ISO offset timestamp",
        "buyer_country: not an ISO 3166 alpha-2 or alpha-3 code",
        "cpv_codes: CPV code '72' has invalid shape",
    ]


def test_formats_on_ted_api_fixture(fixture_name: str) -> None:
    """Each ted_api fixture and its events satisfy the format checks."""
    data = load_fixture(fixture_name)
    notice = map_raw_to_notice(RawNotice.model_validate(data))
    events = events_from_notice(notice)
    assert check_formats(data) == []
    assert (
        check_formats(
            {
                "buyer_country": notice.country,
                "authority_country": notice.authority_country,
                "cpv_codes": notice.cpv_codes,
                "events": events,
            }
        )
        == []
    )
    for event in events:
        assert check_formats(event) == []
        if event["current"] is not None:
            assert event["current"] == f"{event['current'][:10]}T00:00:00+00:00"
            assert event["current_utc"] == event["current"]


def test_buyer_country_alpha2_and_alpha3() -> None:
    """ted_api fixtures cover both ISO 3166 alpha-2 and alpha-3 buyer countries."""
    alpha2 = load_fixture("notice_contract_cpv72_deu.json")
    assert alpha2["country"] == "DE"
    assert (
        check_formats({"buyer_country": alpha2["country"], "cpv_codes": alpha2["cpvCodes"]}) == []
    )

    alpha3 = load_fixture("notice_cancel_intent.json")
    assert alpha3["country"] == "POL"
    assert alpha3["authorityCountry"] == "POL"
    assert (
        check_formats({"buyer_country": alpha3["country"], "cpv_codes": alpha3["cpvCodes"]}) == []
    )


def test_change_reason_event_is_offset_timestamp() -> None:
    """A deadline change is emitted as an ISO offset timestamp with attribution."""
    events = events_from_fixture(load_fixture("notice_contract_change_reason.json"))
    assert events == [
        {
            "event": "deadline_changed",
            "kind": "COR",
            "lot": "LOT-A",
            "previous": None,
            "current": "2024-04-30T00:00:00+00:00",
            "current_utc": "2024-04-30T00:00:00+00:00",
            "source": "https://ted.europa.eu/notice/555666-2024",
            "coverage": COVERAGE,
            "attribution": ATTRIBUTION,
        }
    ]


def test_unchanged_lot_emits_no_event() -> None:
    """A lot whose reason is none does not yield a deadline event."""
    events = events_from_fixture(load_fixture("notice_contract_with_lots.json"))
    assert [event["lot"] for event in events] == ["LOT-001"]
    assert events[0]["event"] == "deadline_changed"
    assert events[0]["kind"] == "EXT"


def test_susp_review_fixture_never_deadline_changed() -> None:
    """susp-review yields suspension, never deadline_changed."""
    data = load_fixture("notice_susp_review.json")
    events = events_from_fixture(data)
    assert [event["event"] for event in events] == ["suspension"]
    assert [event["kind"] for event in events] == ["susp-review"]
    assert "deadline_changed" not in {event["event"] for event in events}
    assert check_event_kinds([data]) == []
    assert check_event_kinds(events) == []


def test_cancel_intent_fixture_never_deadline_changed() -> None:
    """cancel-intent yields cancel_intent, never deadline_changed."""
    data = load_fixture("notice_cancel_intent.json")
    events = events_from_fixture(data)
    assert [event["event"] for event in events] == ["cancel_intent"]
    assert [event["kind"] for event in events] == ["cancel-intent"]
    assert "deadline_changed" not in {event["event"] for event in events}
    assert check_event_kinds([data]) == []
    assert check_event_kinds(events) == []


def test_protected_reason_may_yield_no_event() -> None:
    """susp-review may yield no event; that is not a deadline_changed event."""
    data = load_fixture("notice_planning_without_lots.json")
    data = {
        **data,
        "changeReasonCode": "susp-review",
        "deadline": None,
        "lots": [
            {
                "id": "LOT-1",
                "deadline": "2024-06-20",
                "deadlineChangeReasonCode": "NONE",
            }
        ],
    }
    events = events_from_fixture(data)
    assert events == []
    assert check_event_kinds([data]) == []
    assert check_event_kinds(events) == []


def test_check_event_kinds_rejects_deadline_changed() -> None:
    """A deadline_changed event for susp-review or cancel-intent is a violation."""
    assert check_event_kinds(
        [{"event": "deadline_changed", "kind": "susp-review", "lot": "LOT-S1"}]
    ) == ["[0]: kind susp-review yielded deadline_changed; expected suspension or none"]
    assert check_event_kinds([{"event": "deadline_changed", "kind": "cancel-intent"}]) == [
        "[0]: kind cancel-intent yielded deadline_changed; expected cancel_intent or none"
    ]


def test_check_redaction_reports_email_and_phone() -> None:
    """The redaction scan reports each email and phone it finds."""
    text = "reach jane.doe@example.com or +49 30 1234 5678"
    assert check_redaction(text) == [
        "email:jane.doe@example.com",
        "phone:+49 30 1234 5678",
    ]


def test_synthetic_contact_fixture_does_not_survive() -> None:
    """Seeded contact fields are detectable in the fixture and absent from events."""
    path = FIXTURE_DIR / "notice_with_contact_fields.json"
    raw_text = path.read_text()
    assert check_redaction(raw_text) == [
        "email:jane.doe@stadtbibliothek.example",
        "email:procurement@buyer.example",
        "email:tenders@example.org",
        "phone:+49 30 1234 5678",
        "phone:+48 22 123 45 67",
        "phone:0049 89 1234567",
    ]
    events = events_from_fixture(json.loads(raw_text))
    serialized = json.dumps(events, ensure_ascii=False)
    assert events != []
    assert check_redaction(serialized) == []
    assert check_redaction(events) == []
    assert "jane.doe@stadtbibliothek.example" not in serialized
    assert "procurement@buyer.example" not in serialized
    assert "tenders@example.org" not in serialized
    assert "+49 30 1234 5678" not in serialized
    assert "+48 22 123 45 67" not in serialized
    assert "0049 89 1234567" not in serialized
    assert "Jane Doe" not in serialized
    assert serialized is not raw_text


def test_redaction_on_ted_api_fixture(fixture_name: str) -> None:
    """Serialized events from every ted_api fixture contain no email or phone."""
    events = events_from_fixture(load_fixture(fixture_name))
    serialized = json.dumps(events, ensure_ascii=False)
    assert check_redaction(serialized) == []


def test_attribution_on_ted_api_fixture(fixture_name: str) -> None:
    """Every event from a ted_api fixture has the attribution string and coverage label."""
    events = events_from_fixture(load_fixture(fixture_name))
    assert check_attribution(events) == []
    for event in events:
        assert event["attribution"] == ATTRIBUTION
        assert event["coverage"] == COVERAGE


def test_check_attribution_rejects_missing_fields() -> None:
    """An event without attribution or coverage is a violation."""
    assert check_attribution([{"event": "deadline_changed"}]) == [
        "event[0]: missing attribution string",
        "event[0]: missing coverage label",
    ]


def test_events_from_notice_is_pure(fixture_name: str) -> None:
    """Event building is pure: same input, equal output, not the same object."""
    notice = map_raw_to_notice(RawNotice.model_validate(load_fixture(fixture_name)))
    first = events_from_notice(notice)
    second = events_from_notice(notice)
    assert first == second
    assert first is not second


def test_ted_api_connector_fixtures_pass() -> None:
    """All four checks pass on the ted_api connector fixtures."""
    names = sorted(path.name for path in FIXTURE_DIR.glob("*.json"))
    assert "notice_susp_review.json" in names
    assert "notice_cancel_intent.json" in names
    assert "notice_with_contact_fields.json" in names
    fixtures = [load_fixture(name) for name in names]
    assert run_checks(fixtures) == []
    assert run_connector_checks("ted_api") == []
    assert fixtures is not names

"""Tests for the pure map_raw_to_notice function."""

import json
from pathlib import Path

import pytest
from src.ted_watch.core.map import map_raw_to_notice
from src.ted_watch.core.model import RawNotice

FIXTURE_DIR = (
    Path(__file__).parent.parent.parent / "fixtures" / "connectors" / "ted_api" / "fixtures"
)


def load_fixture(name: str) -> RawNotice:
    """Load a fixture JSON file and parse as RawNotice."""
    path = FIXTURE_DIR / name
    with path.open() as f:
        data = json.load(f)
    return RawNotice.model_validate(data)


@pytest.fixture(
    params=[
        "notice_contract_with_lots.json",
        "notice_planning_without_lots.json",
        "notice_contract_change_reason.json",
        "notice_contract_alternate_fields.json",
        "notice_contract_unknown_values.json",
    ]
)
def raw_notice(request) -> RawNotice:
    """Parametrized fixture providing RawNotice instances."""
    return load_fixture(request.param)


def test_map_raw_to_notice_preserves_id(raw_notice: RawNotice) -> None:
    """Notice ID is preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.notice_id == raw_notice.notice_id


def test_map_raw_to_notice_preserves_title(raw_notice: RawNotice) -> None:
    """Title is preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.title == raw_notice.title


def test_map_raw_to_notice_preserves_type(raw_notice: RawNotice) -> None:
    """Notice type is preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.notice_type == raw_notice.notice_type


def test_map_raw_to_notice_preserves_publication_date(raw_notice: RawNotice) -> None:
    """Publication date is preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.publication_date == raw_notice.publication_date


def test_map_raw_to_notice_preserves_deadline(raw_notice: RawNotice) -> None:
    """Overall deadline is preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.deadline == raw_notice.deadline


def test_map_raw_to_notice_preserves_country(raw_notice: RawNotice) -> None:
    """Country code is preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.country == raw_notice.country


def test_map_raw_to_notice_preserves_authority(raw_notice: RawNotice) -> None:
    """Authority information is preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.authority_name == raw_notice.authority_name
    assert notice.authority_city == raw_notice.authority_city
    assert notice.authority_country == raw_notice.authority_country


def test_map_raw_to_notice_preserves_cpv_codes(raw_notice: RawNotice) -> None:
    """CPV codes are preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.cpv_codes == raw_notice.cpv_codes


def test_map_raw_to_notice_preserves_change_reason(raw_notice: RawNotice) -> None:
    """Change reason fields are preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.change_reason_code == raw_notice.change_reason_code
    assert notice.change_reason == raw_notice.change_reason


def test_map_raw_to_notice_preserves_url(raw_notice: RawNotice) -> None:
    """URL is preserved through mapping."""
    notice = map_raw_to_notice(raw_notice)
    assert notice.url == raw_notice.url


def test_map_raw_to_notice_maps_lots_correctly(raw_notice: RawNotice) -> None:
    """Lots are correctly mapped to LotDeadline objects."""
    notice = map_raw_to_notice(raw_notice)

    # Count expected valid lots from raw data
    expected_lot_count = sum(
        1
        for lot in raw_notice.lots
        if (lot.get("id") or lot.get("lotId") or lot.get("lot_id"))
        and (lot.get("deadline") or lot.get("submissionDeadline"))
    )
    assert len(notice.lots) == expected_lot_count

    # Each lot should have required fields
    for lot in notice.lots:
        assert lot.lot_id
        assert lot.deadline
        # change reason fields may be None


def test_map_raw_to_notice_handles_alternate_field_names() -> None:
    """Mapping handles alternate field names in lots (lotId, submissionDeadline, etc.)."""
    raw = load_fixture("notice_contract_alternate_fields.json")
    notice = map_raw_to_notice(raw)

    assert len(notice.lots) == 2
    lot_ids = {lot.lot_id for lot in notice.lots}
    assert lot_ids == {"LOT-100", "LOT-200"}

    # Check deadlines parsed correctly
    deadlines = {lot.lot_id: lot.deadline for lot in notice.lots}
    from datetime import date

    assert deadlines["LOT-100"] == date(2024, 3, 20)
    assert deadlines["LOT-200"] == date(2024, 4, 10)

    # Check change reason codes mapped
    change_codes = {lot.lot_id: lot.deadline_change_reason_code for lot in notice.lots}
    assert change_codes["LOT-100"] == "EXT"
    assert change_codes["LOT-200"] == "NONE"


def test_map_raw_to_notice_is_pure(raw_notice: RawNotice) -> None:
    """Mapping function is pure - same input always produces same output."""
    notice1 = map_raw_to_notice(raw_notice)
    notice2 = map_raw_to_notice(raw_notice)
    assert notice1 == notice2
    # Ensure it's not the same object (immutability)
    assert notice1 is not notice2


def test_map_records_unrecognised_reason_and_malformed_pointer() -> None:
    """Unrecognised reason codes and pointer shapes are returned, not dropped."""
    raw = load_fixture("notice_contract_unknown_values.json")
    notice = map_raw_to_notice(raw)
    assert notice.unknowns == [
        {"kind": "change-reason-code", "value": "new-code-x"},
        {"kind": "pointer", "value": "not-a-pointer"},
    ]
    assert notice.change_reason_code == "new-code-x"
    assert notice.change_notice_version_identifier == "not-a-pointer"


def test_map_records_unequal_lot_arrays() -> None:
    """Lot arrays of unequal length are recorded and do not crash mapping."""
    raw = RawNotice.model_validate(
        {
            "noticeId": "1",
            "title": "t",
            "noticeType": "contract",
            "publicationDate": "2024-01-01",
            "country": "DE",
            "authorityName": "A",
            "authorityCountry": "DE",
            "identifier-lot": ["LOT-1", "LOT-2"],
            "deadline-receipt-tender-date-lot": ["2024-02-01"],
        }
    )
    notice = map_raw_to_notice(raw)
    assert notice.unknowns == [
        {
            "kind": "lot-arrays",
            "value": "identifier-lot:2,deadline-receipt-tender-date-lot:1",
        }
    ]


def test_map_equal_lot_arrays_are_not_unknown() -> None:
    """Parallel lot arrays of the same length are not reported."""
    raw = RawNotice.model_validate(
        {
            "noticeId": "1",
            "title": "t",
            "noticeType": "contract",
            "publicationDate": "2024-01-01",
            "country": "DE",
            "authorityName": "A",
            "authorityCountry": "DE",
            "changeReasonCode": "cor-buy",
            "changeNoticeVersionIdentifier": "719096-2026",
            "identifier-lot": ["LOT-1", "LOT-2"],
            "deadline-receipt-tender-date-lot": ["2024-02-01", "2024-03-01"],
            "deadline-receipt-tender-time-lot": ["12:00", "13:00"],
        }
    )
    notice = map_raw_to_notice(raw)
    assert notice.unknowns == []


def test_map_same_bytes_are_identical_and_nothing_is_global() -> None:
    """Same input bytes yield identical notices and map keeps no global counts."""
    import src.ted_watch.core.map as map_module

    path = FIXTURE_DIR / "notice_contract_unknown_values.json"
    payload = path.read_bytes()
    before = {
        key: repr(value) for key, value in vars(map_module).items() if not key.startswith("__")
    }
    first = map_raw_to_notice(RawNotice.model_validate(json.loads(payload)))
    second = map_raw_to_notice(RawNotice.model_validate(json.loads(payload)))
    after = {
        key: repr(value) for key, value in vars(map_module).items() if not key.startswith("__")
    }
    assert first == second
    assert first is not second
    assert first.unknowns == second.unknowns
    assert before == after
    assert first.model_dump() == second.model_dump()

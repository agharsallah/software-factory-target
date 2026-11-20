"""Tests for predecessor link resolution."""

from src.ted_watch.core.link import resolve_predecessor
from src.ted_watch.core.model import Notice


def _notice(**kwargs) -> Notice:
    base = {
        "notice_id": "000000-2026",
        "title": "t",
        "notice_type": "contract",
        "publication_date": "2026-01-01",
        "country": "DE",
        "authority_name": "A",
        "authority_country": "DE",
    }
    base.update(kwargs)
    return Notice.model_validate(base)


def test_form_a_uuid_version() -> None:
    pred = _notice(
        notice_id="pred-pub",
        notice_identifier="e6f24cac-1111-2222-3333-444444444444",
        notice_version="01",
    )
    change = _notice(
        notice_id="change-pub",
        change_notice_version_identifier="e6f24cac-1111-2222-3333-444444444444-01",
    )
    index = {"e6f24cac-1111-2222-3333-444444444444-01": pred}
    assert resolve_predecessor(change, index) is pred


def test_form_a_index_keyed_by_components() -> None:
    pred = _notice(
        notice_id="pred-pub",
        notice_identifier="e6f24cac-1111-2222-3333-444444444444",
        notice_version="1",
    )
    change = _notice(
        notice_id="change-pub",
        change_notice_version_identifier="e6f24cac-1111-2222-3333-444444444444-01",
    )
    index = {"anything": pred}
    assert resolve_predecessor(change, index) is pred


def test_form_b_publication_number() -> None:
    pred = _notice(notice_id="719096-2026")
    change = _notice(
        notice_id="change-pub",
        change_notice_version_identifier="719096-2026",
    )
    index = {"719096-2026": pred}
    assert resolve_predecessor(change, index) is pred


def test_form_b_index_scan() -> None:
    pred = _notice(notice_id="719096-2026")
    change = _notice(
        notice_id="change-pub",
        change_notice_version_identifier="719096-2026",
    )
    index = {"other-key": pred}
    assert resolve_predecessor(change, index) is pred


def test_missing_predecessor() -> None:
    change = _notice(
        notice_id="change-pub",
        change_notice_version_identifier="does-not-exist",
    )
    index = {}
    assert resolve_predecessor(change, index) is None


def test_no_pointer() -> None:
    notice = _notice(notice_id="plain")
    assert resolve_predecessor(notice, {}) is None


def test_change_of_change_chain() -> None:
    original = _notice(notice_id="orig-pub")
    first_change = _notice(
        notice_id="first-change",
        change_notice_version_identifier="orig-pub",
    )
    second_change = _notice(
        notice_id="second-change",
        change_notice_version_identifier="first-change",
    )
    index = {
        "orig-pub": original,
        "first-change": first_change,
    }
    assert resolve_predecessor(first_change, index) is original
    assert resolve_predecessor(second_change, index) is first_change

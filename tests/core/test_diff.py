"""Tests for suspension and intended-cancellation events from diff."""

import json
from pathlib import Path

import pytest
from src.ted_watch.core.dedupe import event_id
from src.ted_watch.core.diff import diff_notices
from src.ted_watch.core.map import map_raw_to_notice
from src.ted_watch.core.model import Notice, RawNotice
from src.ted_watch.core.source import load_source

REPO_ROOT = Path(__file__).resolve().parents[2]
VISIBLE = REPO_ROOT / "fixtures" / "visible"
SOURCE_PATH = REPO_ROOT / "src" / "ted_watch" / "connectors" / "ted_api" / "source.yaml"

_PERSONAL = (
    "contact-name",
    "buyer-contact-point",
    "organisation-person-name",
    "contact-email",
    "email",
    "touchpoint-email",
    "telephone",
    "contact-phone",
    "phone",
)


def _load(path: Path) -> Notice:
    """Load a visible fixture and map it. No network."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return map_raw_to_notice(RawNotice.model_validate(data))


def _pair(procedure: str, change_name: str) -> tuple[Notice, Notice]:
    """Return the predecessor and change notice for a visible procedure."""
    directory = VISIBLE / procedure
    return _load(directory / "predecessor.json"), _load(directory / change_name)


class TestDiff:
    """susp-review and cancel-intent yield their own events, never deadline_changed."""

    @pytest.mark.parametrize(
        ("procedure", "change_name", "event_name"),
        [
            ("vis-susp-review", "change.susp_review.json", "procedure_suspended"),
            ("vis-cancel-intent", "change.cancel_intent.json", "cancellation_intended"),
        ],
    )
    def test_susp_review_and_cancel_intent(
        self, procedure: str, change_name: str, event_name: str
    ) -> None:
        """A procedure code yields its event, with notice, source URL, coverage and attribution."""
        previous, current = _pair(procedure, change_name)
        source = load_source(SOURCE_PATH)
        assert previous.deadline is not None
        assert current.deadline is not None
        assert previous.deadline != current.deadline
        assert current.url is not None

        events = diff_notices(previous, current)
        again = diff_notices(previous, current)
        alone = diff_notices(None, current)

        assert [event["event"] for event in events] == [event_name]
        assert [event["event"] for event in alone] == [event_name]
        assert "deadline_changed" not in {event["event"] for event in events}
        assert "deadline_changed" not in {event["event"] for event in alone}
        assert "deadline_changed" not in json.dumps(events)

        event = events[0]
        assert event["notice"] == current.notice_id
        assert event["source"] == current.url
        assert event["source"].startswith("https://")
        assert event["coverage"] == source.coverage
        assert event["attribution"] == source.attribution
        assert event["kind"] == current.change_reason_code
        assert event["procedure"] == current.procedure_identifier
        assert event["previous_notice"] == previous.notice_id
        assert event["current_notice"] == current.notice_id
        assert "previous" not in event
        assert "current" not in event
        assert "current_utc" not in event
        for field in _PERSONAL:
            assert field not in event
        assert events == again
        assert events[0] is not again[0]

    def test_susp_review(self) -> None:
        """A notice with change-reason-code susp-review yields procedure_suspended."""
        _previous, current = _pair("vis-susp-review", "change.susp_review.json")
        events = diff_notices(None, current)
        assert current.change_reason_code == "susp-review"
        assert [event["event"] for event in events] == ["procedure_suspended"]
        assert all(event["event"] != "deadline_changed" for event in events)

    def test_cancel_intent(self) -> None:
        """A notice with cancel-intent yields cancellation_intended."""
        _previous, current = _pair("vis-cancel-intent", "change.cancel_intent.json")
        events = diff_notices(None, current)
        assert current.change_reason_code == "cancel-intent"
        assert [event["event"] for event in events] == ["cancellation_intended"]
        assert all(event["event"] != "deadline_changed" for event in events)

    def test_lot_only_code_is_not_a_deadline_changed_event(self) -> None:
        """A lot-level procedure code still does not emit deadline_changed."""
        notice = Notice.model_validate(
            {
                "notice_id": "810199-2024",
                "title": "Lot-level suspension",
                "notice_type": "contract",
                "publication_date": "2024-04-01",
                "deadline": "2024-06-01",
                "country": "DE",
                "authority_name": "Synthetic Authority",
                "authority_country": "DE",
                "url": "https://ted.europa.eu/notice/810199-2024",
                "procedure_identifier": "vis-lot-susp",
                "lots": [
                    {
                        "lot_id": "LOT-9",
                        "deadline": "2024-06-01",
                        "deadline_change_reason_code": "susp-review",
                    }
                ],
            }
        )
        previous = Notice.model_validate(
            {
                "notice_id": "810198-2024",
                "title": "Earlier",
                "notice_type": "contract",
                "publication_date": "2024-03-01",
                "deadline": "2024-05-01",
                "country": "DE",
                "authority_name": "Synthetic Authority",
                "authority_country": "DE",
            }
        )
        events = diff_notices(previous, notice)
        assert [event["event"] for event in events] == ["procedure_suspended"]
        assert "deadline_changed" not in json.dumps(events)
        assert events[0]["notice"] == "810199-2024"
        assert events[0]["source"] == "https://ted.europa.eu/notice/810199-2024"

    def test_personal_data_is_not_copied(self) -> None:
        """Extra contact fields on the notice do not appear on the event."""
        notice = Notice.model_validate(
            {
                "notice_id": "810188-2024",
                "title": "Suspended procedure",
                "notice_type": "contract",
                "publication_date": "2024-04-02",
                "country": "NL",
                "authority_name": "Synthetic Authority",
                "authority_country": "NL",
                "change_reason_code": "cancel-intent",
                "url": "https://ted.europa.eu/notice/810188-2024",
                "contact-name": "Ada Lovelace",
                "contact-email": "person@example.com",
                "telephone": "+32-2-000-0000",
                "email": "person@example.com",
                "phone": "+32-2-000-0000",
            }
        )
        assert notice.model_extra is not None
        assert notice.model_extra["email"] == "person@example.com"
        events = diff_notices(None, notice)
        blob = json.dumps(events)
        assert "person@example.com" not in blob
        assert "Ada Lovelace" not in blob
        assert "+32-2-000-0000" not in blob
        for field in _PERSONAL:
            assert field not in events[0]
        assert events[0]["event"] == "cancellation_intended"
        assert events[0]["notice"] == notice.notice_id
        assert events[0]["source"] == notice.url

    def test_distinct_notices_do_not_share_an_event_id(self) -> None:
        """Dedupe identity includes the current notice, so the two cases stay distinct."""
        _prev_s, susp = _pair("vis-susp-review", "change.susp_review.json")
        _prev_c, cancel = _pair("vis-cancel-intent", "change.cancel_intent.json")
        susp_event = diff_notices(None, susp)[0]
        cancel_event = diff_notices(None, cancel)[0]
        assert event_id(susp_event) != event_id(cancel_event)
        assert event_id(susp_event) == event_id(dict(susp_event))

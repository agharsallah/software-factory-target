"""Tests for the offline connector → link → diff → dedupe pipeline."""

import random
from datetime import date
from pathlib import Path

import pytest
from src.ted_watch.connectors import FakeConnector
from src.ted_watch.core.model import RawNotice
from src.ted_watch.core.pipeline import run
from src.ted_watch.core.source import load_source

REPO_ROOT = Path(__file__).resolve().parents[2]
VISIBLE = REPO_ROOT / "fixtures" / "visible"
HOLDOUT = REPO_ROOT / "fixtures" / "holdout"
SOURCE = load_source(REPO_ROOT / "src" / "ted_watch" / "connectors" / "ted_api" / "source.yaml")

_EVENT_TYPES = {"deadline_changed", "suspension", "cancellation"}


class _OrderedConnector:
    """Replay ``list_changes`` in a caller-supplied order. Still offline."""

    def __init__(self, inner: FakeConnector, order: list[str]) -> None:
        self._inner = inner
        self._order = list(order)

    def list_changes(
        self,
        since: date | str | None = None,
        until: date | str | None = None,
    ) -> list[str]:
        allowed = set(self._inner.list_changes(since, until))
        return [ref for ref in self._order if ref in allowed]

    def fetch(self, ref: str) -> RawNotice:
        return self._inner.fetch(ref)

    def map(self, raw: RawNotice):
        return self._inner.map(raw)


def _procedure_dirs(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.is_dir())


class TestPipeline:
    def test_run_returns_only_contract_event_types(self) -> None:
        events = run(FakeConnector(VISIBLE), None, None)
        assert events
        assert {event["event"] for event in events} <= _EVENT_TYPES
        assert "deadline_changed" in {event["event"] for event in events}
        assert "suspension" in {event["event"] for event in events}
        assert "cancellation" in {event["event"] for event in events}

    def test_visible_events_match_linked_fixtures(self) -> None:
        events = run(FakeConnector(VISIBLE), None, None)
        by_current = {(event["current_notice"], event["lot"]): event for event in events}
        linked = by_current[("810002-2024", "LOT-001")]
        assert linked == {
            "event": "deadline_changed",
            "kind": "cor-buy",
            "lot": "LOT-001",
            "previous": "2024-05-01",
            "current": "2024-05-20",
            "current_utc": "2024-05-20T00:00:00Z",
            "source": "https://ted.europa.eu/notice/810002-2024",
            "coverage": SOURCE.coverage,
            "attribution": SOURCE.attribution,
            "procedure": "vis-form-a-uuid",
            "procedure_identifier": "vis-form-a-uuid",
            "previous_notice": "810001-2024",
            "current_notice": "810002-2024",
        }
        cancelled = by_current[("810062-2024", "LOT-001")]
        assert cancelled["event"] == "cancellation"
        assert cancelled["kind"] == "cancel-intent"
        assert cancelled["previous"] == "2024-03-20"
        assert cancelled["previous_notice"] == "810061-2024"
        assert cancelled["previous"] is not None
        originals = [
            event for event in events if event["current_notice"] in {"810060-2024", "810001-2024"}
        ]
        assert originals == []

    @pytest.mark.parametrize("fixtures_dir", [VISIBLE, HOLDOUT])
    def test_unresolved_predecessor_previous_is_unknown(self, fixtures_dir: Path) -> None:
        events = run(FakeConnector(fixtures_dir), None, None)
        missing = [event for event in events if "missing" in str(event.get("procedure"))]
        assert missing
        for event in missing:
            assert event["event"] == "suspension"
            assert event["previous"] is None
            assert event["previous_notice"] is None
            assert event["current"] is not None
            assert event["previous"] is not event["current"]

    def test_predecessor_outside_the_window_is_not_guessed(self) -> None:
        events = run(FakeConnector(VISIBLE), date(2024, 3, 15), date(2024, 3, 31))
        matched = [event for event in events if event.get("current_notice") == "810002-2024"]
        assert len(matched) == 1
        assert matched[0]["previous"] is None
        assert matched[0]["previous_notice"] is None
        assert matched[0]["current"] == "2024-05-20"
        assert matched[0]["previous"] is not matched[0]["current"]

    def test_none_reason_lot_without_a_predecessor_is_omitted(self) -> None:
        events = run(FakeConnector(VISIBLE), None, None)
        lots = [event for event in events if event.get("current_notice") == "123456-2024"]
        assert [event["lot"] for event in lots] == ["LOT-001"]
        assert lots[0]["event"] == "deadline_changed"
        assert lots[0]["kind"] == "EXT"
        assert lots[0]["previous"] is None

    def test_run_twice_is_identical_and_not_the_same_list(self) -> None:
        connector = FakeConnector(VISIBLE)
        first = run(connector, None, None)
        second = run(connector, None, None)
        assert first == second
        assert first is not second

    @pytest.mark.parametrize("fixtures_dir", [VISIBLE, HOLDOUT])
    @pytest.mark.parametrize("seed", [0, 1, 7, 42])
    def test_shuffled_replay_matches_canonical_output(self, fixtures_dir: Path, seed: int) -> None:
        base = FakeConnector(fixtures_dir)
        canonical = run(base, None, None)
        refs = base.list_changes(None, None)
        shuffled = list(refs)
        random.Random(seed).shuffle(shuffled)
        first = run(_OrderedConnector(base, shuffled), None, None)
        random.Random(seed + 99).shuffle(shuffled)
        second = run(_OrderedConnector(base, list(reversed(shuffled)) + shuffled), None, None)
        assert first == canonical
        assert second == canonical
        assert first == second
        assert first is not second
        assert first is not canonical

    @pytest.mark.parametrize(
        "fixtures_dir",
        _procedure_dirs(VISIBLE) + _procedure_dirs(HOLDOUT),
        ids=lambda path: path.name,
    )
    def test_procedure_directory_shuffle_is_identical(self, fixtures_dir: Path) -> None:
        base = FakeConnector(fixtures_dir)
        canonical = run(base, None, None)
        refs = list(reversed(base.list_changes(None, None)))
        replay = run(_OrderedConnector(base, refs + refs), None, None)
        assert replay == canonical
        assert replay is not canonical
        assert {event["event"] for event in replay} <= _EVENT_TYPES

    def test_run_calls_list_changes_then_fetch_then_map(self) -> None:
        inner = FakeConnector(VISIBLE)
        calls: list[str] = []

        class _Recording:
            def list_changes(self, since=None, until=None):
                calls.append("list_changes")
                return inner.list_changes(since, until)

            def fetch(self, ref: str) -> RawNotice:
                calls.append("fetch")
                return inner.fetch(ref)

            def map(self, raw: RawNotice):
                calls.append("map")
                return inner.map(raw)

        events = run(_Recording(), None, None)
        assert events
        assert calls[0] == "list_changes"
        assert "fetch" in calls
        assert "map" in calls
        assert calls.index("list_changes") < calls.index("fetch") < calls.index("map")

    def test_fake_connector_map_is_pure_and_offline(self) -> None:
        connector = FakeConnector(VISIBLE)
        ref = connector.list_changes(None, None)[0]
        raw = connector.fetch(ref)
        first = connector.map(raw)
        second = connector.map(raw)
        assert first == second
        assert first is not second
        assert first.notice_id == raw.notice_id

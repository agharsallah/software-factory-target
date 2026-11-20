"""Tests for stable event ids and exactly-once dedupe."""

import random

import pytest
from src.ted_watch.core.dedupe import Dedupe, event_id


def _event(**kwargs: object) -> dict:
    base = {
        "event": "deadline_change",
        "kind": "cor-buy",
        "lot": "LOT-1",
        "previous": "2026-03-01",
        "current": "2026-04-01",
        "current_utc": "2026-04-01T00:00:00Z",
        "source": "ted.europa.eu",
        "coverage": "EU tenders",
        "attribution": "TED (ted.europa.eu)",
        "procedure": "proc-1",
        "previous_notice": "111111-2026",
        "current_notice": "222222-2026",
    }
    base.update(kwargs)
    return base


def _window() -> list[dict]:
    return [
        _event(lot="LOT-1", kind="cor-buy"),
        _event(lot="LOT-2", kind="cor-buy"),
        _event(lot="LOT-1", kind="susp-review"),
        _event(
            lot="LOT-3",
            kind="cancel-intent",
            previous_notice="333333-2026",
            current_notice="444444-2026",
        ),
    ]


class TestDedupe:
    def test_event_id_is_deterministic(self) -> None:
        event = _event()
        assert event_id(event) == event_id(dict(event))
        assert event_id(event) == event_id(_event())
        assert len(event_id(event)) == 64

    def test_event_id_hashes_the_five_identity_fields(self) -> None:
        base = event_id(_event())
        assert event_id(_event(procedure="proc-2")) != base
        assert event_id(_event(lot="LOT-9")) != base
        assert event_id(_event(kind="cor-pub")) != base
        assert event_id(_event(previous_notice="999999-2026")) != base
        assert event_id(_event(current_notice="888888-2026")) != base

    def test_deadline_values_are_not_part_of_the_id(self) -> None:
        first = _event(previous="2026-01-01", current="2026-02-01")
        second = _event(previous="2026-05-01", current="2026-06-01")
        assert event_id(first) == event_id(second)

    def test_different_lots_or_kinds_in_one_notice(self) -> None:
        shared = {
            "procedure": "proc-1",
            "previous_notice": "111111-2026",
            "current_notice": "222222-2026",
        }
        lot_a = _event(**shared, lot="LOT-A", kind="cor-buy")
        lot_b = _event(**shared, lot="LOT-B", kind="cor-buy")
        kind_b = _event(**shared, lot="LOT-A", kind="update-add")
        assert event_id(lot_a) != event_id(lot_b)
        assert event_id(lot_a) != event_id(kind_b)
        assert event_id(lot_b) != event_id(kind_b)

    def test_cli_shaped_prev_and_current_are_identity_fallbacks(self) -> None:
        event = {
            "event": "deadline_change",
            "kind": "cor-buy",
            "lot": "LOT-1",
            "previous": "111111-2026",
            "current": "222222-2026",
            "source": "ted.europa.eu",
            "coverage": "EU tenders",
            "attribution": "TED (ted.europa.eu)",
        }
        assert event_id(event) == event_id(dict(event))
        assert event_id(event) != event_id({**event, "previous": "999999-2026"})
        assert event_id(event) != event_id({**event, "current": "999999-2026"})
        assert event_id(event) != event_id({**event, "lot": "LOT-2"})
        assert event_id(event) != event_id({**event, "kind": "info-release"})

    def test_dedupe_emits_each_logical_change_once(self) -> None:
        first = _event(lot="LOT-1")
        second = _event(lot="LOT-2")
        repeat = dict(first)
        events = [first, second, repeat, first, second]
        emitted = list(Dedupe(events))
        assert emitted == [first, second]
        assert emitted[0] is first
        assert len(emitted) == len({event_id(e) for e in events})

    def test_out_of_order_repeats_collapse(self) -> None:
        early = _event(lot="LOT-1", current_notice="200000-2026")
        late = _event(lot="LOT-1", current_notice="300000-2026")
        events = [late, early, late, early]
        emitted = list(Dedupe(events))
        assert emitted == [late, early]
        assert {event_id(e) for e in emitted} == {event_id(early), event_id(late)}

    @pytest.mark.parametrize("seed", [0, 1, 7, 42])
    def test_replay_and_shuffle_give_identical_id_sets(self, seed: int) -> None:
        window = _window()
        replay = window + window
        shuffled = list(window)
        random.Random(seed).shuffle(shuffled)
        shuffled_replay = shuffled + list(reversed(window))

        ids_once = {event_id(e) for e in Dedupe(window)}
        ids_replay = {event_id(e) for e in Dedupe(replay)}
        ids_shuffled = {event_id(e) for e in Dedupe(shuffled)}
        ids_shuffled_replay = {event_id(e) for e in Dedupe(shuffled_replay)}

        assert ids_once == ids_replay == ids_shuffled == ids_shuffled_replay
        assert len(ids_once) == len(window)
        assert len(list(Dedupe(replay))) == len(window)
        assert len(list(Dedupe(shuffled_replay))) == len(window)

    def test_store_replay_emits_nothing_new(self) -> None:
        window = _window()
        store = Dedupe()
        first = list(store.emit(window))
        second = list(store.emit(window))
        third = list(store.emit(list(reversed(window))))
        assert [event_id(e) for e in first] == [event_id(e) for e in window]
        assert second == []
        assert third == []
        assert {event_id(e) for e in store} == {event_id(e) for e in window}
        assert len(store) == len(window)

    def test_same_store_replayed_twice_matches_fresh_windows(self) -> None:
        window = _window()
        shuffled = list(reversed(window))
        store = Dedupe(window)
        store.extend(window)
        store.extend(shuffled)
        fresh = Dedupe(shuffled + window + window)
        assert {event_id(e) for e in store} == {event_id(e) for e in fresh}
        assert len(store) == len(fresh) == len(window)

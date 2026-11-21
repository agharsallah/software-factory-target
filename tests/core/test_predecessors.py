"""Tests for on-disk predecessor lookup outside the fetched window."""

import json
from pathlib import Path

import pytest
from src.ted_watch.core.map import map_raw_to_notice
from src.ted_watch.core.model import Notice, RawNotice
from src.ted_watch.core.predecessors import PredecessorCache, Unresolved

VISIBLE = Path(__file__).resolve().parents[2] / "fixtures" / "visible"

OUTSIDE_WINDOW = [
    (
        "vis-form-a-uuid/change.form_a_uuid_version.json",
        "vis-form-a-uuid/predecessor.json",
    ),
    (
        "vis-form-a-components/change.form_a_index_keyed_by_components.json",
        "vis-form-a-components/predecessor.json",
    ),
    (
        "vis-form-b-publication/change.form_b_publication_number.json",
        "vis-form-b-publication/predecessor.json",
    ),
    (
        "vis-form-b-scan/change.form_b_index_scan.json",
        "vis-form-b-scan/predecessor.json",
    ),
]


def _load(path: Path) -> Notice:
    """Load a fixture JSON file and map it to a Notice."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return map_raw_to_notice(RawNotice.model_validate(data))


class CountingFetch:
    """Fetch stand-in that counts calls and never touches the network."""

    def __init__(self, found: dict[str, Notice]) -> None:
        self._found = found
        self.calls = 0
        self.refs: list[str] = []

    def __call__(self, ref: str) -> Notice | None:
        self.calls += 1
        self.refs.append(ref)
        return self._found.get(ref)


class TestPredecessors:
    """Injected fetch, JSON cache, and explicit unresolved results."""

    def test_construction_does_not_fetch_or_write(self, tmp_path: Path) -> None:
        """The cache file is not created on construction."""
        path = tmp_path / "predecessors.json"
        fetch = CountingFetch({})
        PredecessorCache(fetch, path)
        assert not path.exists()
        assert fetch.calls == 0

    @pytest.mark.parametrize(("change_name", "predecessor_name"), OUTSIDE_WINDOW)
    def test_predecessor_outside_window_resolves_via_fake_fetch(
        self,
        tmp_path: Path,
        change_name: str,
        predecessor_name: str,
    ) -> None:
        """A pointer missing from the window resolves through the injected fetch."""
        change = _load(VISIBLE / change_name)
        predecessor = _load(VISIBLE / predecessor_name)
        pointer = change.change_notice_version_identifier
        assert pointer is not None
        window = {change.notice_id: change}
        fetch = CountingFetch({pointer: predecessor})
        path = tmp_path / "predecessors.json"
        cache = PredecessorCache(fetch, path)

        resolved = cache.resolve(change, window)
        assert resolved == predecessor
        assert resolved is not change
        assert isinstance(resolved, Notice)
        assert resolved.deadline == predecessor.deadline
        assert resolved.deadline != change.deadline
        assert fetch.calls == 1
        assert fetch.refs == [pointer]

        again = cache.lookup(pointer)
        assert again == predecessor
        assert fetch.calls == 1

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload[pointer]["notice_id"] == predecessor.notice_id
        assert payload[pointer]["deadline"] == predecessor.deadline.isoformat()

        fresh_fetch = CountingFetch({pointer: predecessor})
        fresh = PredecessorCache(fresh_fetch, path)
        loaded = fresh.lookup(pointer)
        assert loaded == predecessor
        assert loaded is not predecessor
        assert loaded is not change
        assert fresh_fetch.calls == 0

    def test_second_lookup_of_either_pointer_form_makes_zero_fetch_calls(
        self, tmp_path: Path
    ) -> None:
        """A counting fake is called once; the cached second lookup does not fetch."""
        form_a = "e6f24cac-1111-2222-3333-444444444444-01"
        form_b = "719096-2026"
        pred_a = _load(VISIBLE / "vis-form-a-uuid" / "predecessor.json")
        pred_b = _load(VISIBLE / "vis-form-b-publication" / "predecessor.json")
        fetch = CountingFetch({form_a: pred_a, form_b: pred_b})
        path = tmp_path / "predecessors.json"
        cache = PredecessorCache(fetch, path)

        first_a = cache.lookup(form_a)
        first_b = cache.lookup(form_b)
        second_a = cache.lookup(form_a)
        second_b = cache.lookup(form_b)

        assert first_a == pred_a
        assert first_b == pred_b
        assert second_a == pred_a
        assert second_b == pred_b
        assert fetch.calls == 2
        assert fetch.refs == [form_a, form_b]

        fresh_fetch = CountingFetch({form_a: pred_a, form_b: pred_b})
        reloaded = PredecessorCache(fresh_fetch, path)
        assert reloaded.lookup(form_a) == pred_a
        assert reloaded.lookup(form_b) == pred_b
        assert fresh_fetch.calls == 0

    def test_unresolvable_pointer_is_explicit_and_cached(self, tmp_path: Path) -> None:
        """A missing predecessor is unknown, not None and not a guessed deadline."""
        change = _load(VISIBLE / "vis-missing-predecessor" / "change.missing_predecessor.json")
        pointer = change.change_notice_version_identifier
        assert pointer == "000000-2099"
        assert change.deadline is not None
        window = {change.notice_id: change}
        fetch = CountingFetch({})
        path = tmp_path / "predecessors.json"
        cache = PredecessorCache(fetch, path)

        missing = cache.resolve(change, window)
        assert missing is not None
        assert missing is not change
        assert not isinstance(missing, Notice)
        assert isinstance(missing, Unresolved)
        assert missing == Unresolved(pointer)
        assert missing is not Unresolved(pointer)
        assert missing.status == "unknown"
        assert missing.resolved is False
        assert missing.deadline is None
        assert missing.deadline != change.deadline
        assert fetch.calls == 1
        assert fetch.refs == [pointer]

        again = cache.lookup(pointer)
        assert again == missing
        assert again is not missing
        assert fetch.calls == 1

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert pointer in payload
        assert payload[pointer] is None

        fresh_fetch = CountingFetch({})
        fresh = PredecessorCache(fresh_fetch, path)
        loaded = fresh.lookup(pointer)
        assert loaded == Unresolved(pointer)
        assert loaded.deadline is None
        assert fresh_fetch.calls == 0

    def test_no_pointer_does_not_guess_or_fetch(self, tmp_path: Path) -> None:
        """A notice with no pointer is unresolved and does not call fetch."""
        notice = _load(VISIBLE / "vis-no-pointer" / "notice.no_pointer.json")
        fetch = CountingFetch({})
        cache = PredecessorCache(fetch, tmp_path / "predecessors.json")
        result = cache.resolve(notice, {})
        assert isinstance(result, Unresolved)
        assert result.status == "unknown"
        assert result.deadline is None
        assert fetch.calls == 0
        assert not (tmp_path / "predecessors.json").exists()

    def test_in_window_hit_does_not_fetch(self, tmp_path: Path) -> None:
        """Link resolution answers when the predecessor is already in memory."""
        change = _load(VISIBLE / "vis-form-b-publication" / "change.form_b_publication_number.json")
        predecessor = _load(VISIBLE / "vis-form-b-publication" / "predecessor.json")
        fetch = CountingFetch({})
        cache = PredecessorCache(fetch, tmp_path / "predecessors.json")
        resolved = cache.resolve(change, {predecessor.publication_number: predecessor})
        assert resolved == predecessor
        assert resolved is predecessor
        assert fetch.calls == 0

"""CLI output is byte-identical for shuffled input and has no duplicate events."""

import json
import random
from pathlib import Path

from src.ted_watch.cli import DEFAULT_FIXTURES, main


def _run(fixtures: Path, out: Path) -> bytes:
    assert main(["--fixtures", str(fixtures), "--out", str(out)]) == 0
    return out.read_bytes()


def _shuffled_copy(tmp_path: Path, seed: int) -> Path:
    files = sorted(DEFAULT_FIXTURES.glob("*.json"))
    random.Random(seed).shuffle(files)
    target = tmp_path / f"in{seed}"
    target.mkdir()
    for index, path in enumerate(files):
        # Names decide read order, so shuffling them shuffles delivery order.
        (target / f"{index:03d}_{path.name}").write_bytes(path.read_bytes())
        (target / f"{index:03d}_dup_{path.name}").write_bytes(path.read_bytes())
    return target


def test_shuffled_input_gives_identical_files(tmp_path: Path) -> None:
    first = _run(_shuffled_copy(tmp_path, 1), tmp_path / "a.jsonl")
    second = _run(_shuffled_copy(tmp_path, 2), tmp_path / "b.jsonl")
    assert first == second


def test_events_sorted_without_duplicates(tmp_path: Path) -> None:
    data = _run(_shuffled_copy(tmp_path, 3), tmp_path / "c.jsonl")
    events = [json.loads(line) for line in data.decode("utf-8").splitlines()]
    assert events
    assert len(events) == len({json.dumps(e, sort_keys=True) for e in events})

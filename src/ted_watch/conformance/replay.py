"""Replay check: shuffled and duplicated delivery yields one event per change."""

import random
from pathlib import Path

from ..core.dedupe import event_id
from ..core.model import RawNotice
from ..core.pipeline import run_pipeline
from .runner import notice_records

SHUFFLE_SEEDS: tuple[int, ...] = (0, 1, 7, 42)


def _orders(items: list[RawNotice]) -> list[tuple[str, list[RawNotice]]]:
    """Return named delivery orders: original, reversed, seeded shuffles, doubled."""
    orders: list[tuple[str, list[RawNotice]]] = [
        ("original", list(items)),
        ("reversed", list(reversed(items))),
    ]
    for seed in SHUFFLE_SEEDS:
        shuffled = list(items)
        random.Random(seed).shuffle(shuffled)
        orders.append((f"shuffled-{seed}", shuffled))
    orders.append(("duplicated", [item for item in items for _ in range(2)]))
    return orders


def replay_check(fixtures: str | Path) -> list[str]:
    """Return failure messages from replaying every procedure in ``fixtures``."""
    root = Path(fixtures)
    by_procedure: dict[Path, list[RawNotice]] = {}
    for file_path, item in notice_records(root):
        group = file_path.parent if file_path.parent != root else file_path
        by_procedure.setdefault(group, []).append(RawNotice.model_validate(item))

    failures: list[str] = []
    for group in sorted(by_procedure):
        baseline: list[str] | None = None
        for name, items in _orders(by_procedure[group]):
            ids = [event_id(event) for event in run_pipeline(items)]
            if len(ids) != len(set(ids)):
                failures.append(f"{group.name}: duplicate event ids in {name} order")
            if baseline is None:
                baseline = sorted(set(ids))
            elif sorted(set(ids)) != baseline:
                failures.append(f"{group.name}: {name} order emitted different event ids")
    return failures

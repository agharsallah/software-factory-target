"""Tests for canary metrics and checks on fixture batches."""

import json
from pathlib import Path

from src.ted_watch.canary.metrics import build_links, check, compute
from src.ted_watch.core.map import map_raw_to_notice
from src.ted_watch.core.model import Notice, RawNotice

REPO_ROOT = Path(__file__).resolve().parents[2]
CHAIN = REPO_ROOT / "fixtures" / "visible" / "vis-change-chain"
CANARY = REPO_ROOT / "fixtures" / "canary"

BASELINE = {
    "resolved_pointer_share": 1.0,
    "tolerance": 0.05,
    "field_presence": {"publication_number": 1.0, "lots": 1.0},
    "min_notices": 1,
    "max_notices": 10,
}


def _load(path: Path) -> Notice:
    """Load a fixture and map it. No network."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return map_raw_to_notice(RawNotice.model_validate(data))


def _healthy() -> list[Notice]:
    """Return a predecessor plus a change whose pointer resolves."""
    return [_load(CHAIN / "original.json"), _load(CHAIN / "first_change.json")]


def _broken() -> list[Notice]:
    """Return a predecessor plus a change with an unresolvable pointer."""
    return [_load(CHAIN / "original.json"), _load(CANARY / "broken_pointer.json")]


def test_healthy_batch_has_no_alerts() -> None:
    """A healthy batch resolves every pointer and raises nothing."""
    notices = _healthy()
    metrics = compute(notices, build_links(notices))
    assert metrics["n_notices"] == 2
    assert metrics["n_changes"] == 1
    assert metrics["resolved_pointer_share"] == 1.0
    assert check(metrics, BASELINE) == []


def test_unresolvable_pointer_drops_share_and_alerts() -> None:
    """An unresolvable pointer lowers the share and raises an alert."""
    notices = _broken()
    metrics = compute(notices, build_links(notices))
    assert metrics["resolved_pointer_share"] == 0.0
    assert any("pointer share" in a for a in check(metrics, BASELINE))


def test_empty_batch_alerts() -> None:
    """An empty batch raises an empty-result alert."""
    metrics = compute([], {})
    assert metrics["resolved_pointer_share"] is None
    assert any("empty" in a for a in check(metrics, BASELINE))


def test_missing_field_alerts() -> None:
    """A baseline field now absent raises an alert."""
    notices = _healthy()
    metrics = compute(notices, build_links(notices))
    metrics["field_presence"]["lots"] = 0.0
    assert any("field missing: lots" in a for a in check(metrics, BASELINE))


def test_volume_outside_range_alerts() -> None:
    """Volume above the baseline maximum raises an alert."""
    notices = _healthy()
    metrics = compute(notices, build_links(notices))
    assert any("volume" in a for a in check(metrics, {**BASELINE, "max_notices": 1}))

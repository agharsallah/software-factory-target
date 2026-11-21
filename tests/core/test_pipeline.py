"""Tests for the pure pipeline and the replay conformance check."""

from pathlib import Path

import pytest
from src.ted_watch.conformance.replay import replay_check
from src.ted_watch.conformance.runner import notice_records
from src.ted_watch.core.dedupe import event_id
from src.ted_watch.core.model import RawNotice
from src.ted_watch.core.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[2] / "fixtures"
VISIBLE = ROOT / "visible"
HOLDOUT = ROOT / "holdout"


class TestPipeline:
    @pytest.mark.parametrize("path", [VISIBLE, HOLDOUT])
    def test_replay_check_passes(self, path: Path) -> None:
        assert replay_check(path) == []

    @pytest.mark.parametrize("path", [VISIBLE, HOLDOUT])
    def test_duplicated_delivery_matches_original(self, path: Path) -> None:
        items = [RawNotice.model_validate(item) for _, item in notice_records(path)]
        once = {event_id(e) for e in run_pipeline(items)}
        twice = [event_id(e) for e in run_pipeline(items + items)]
        assert set(twice) == once
        assert len(twice) == len(set(twice))

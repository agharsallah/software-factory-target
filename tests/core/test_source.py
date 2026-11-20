"""Tests for loading connector source.yaml."""

from pathlib import Path

import pytest
import yaml
from src.ted_watch.core.model import Source
from src.ted_watch.core.source import load_source

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = REPO_ROOT / "src" / "ted_watch" / "connectors" / "ted_api" / "source.yaml"

ATTRIBUTION = "Source: TED (ted.europa.eu), © European Union"

_COMPLETE = {
    "id": "ted_api",
    "coverage": "EU tenders",
    "attribution": ATTRIBUTION,
    "reuse": {"terms": "acknowledge the source"},
    "branding": {"unofficial": True, "use_logos": False},
    "access": {"our_budget": {"requests_per_minute": 30, "min_gap_ms": 1000}},
    "paging": {"mode": "iteration-token"},
    "personal_data_fields": ["email", "phone"],
}


def _write_yaml(path: Path, data: dict) -> Path:
    """Write ``data`` as YAML and return ``path``."""
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _drop(data: dict, path: tuple[str, ...]) -> dict:
    """Return a copy of ``data`` with the nested ``path`` removed."""
    clone = yaml.safe_load(yaml.safe_dump(data))
    cursor = clone
    for part in path[:-1]:
        cursor = cursor[part]
    del cursor[path[-1]]
    return clone


class TestSource:
    """Offline checks for the TED source descriptor."""

    def test_load_source_returns_typed_object(self) -> None:
        """load_source returns a Source and does not reuse the same instance."""
        source = load_source(SOURCE_PATH)
        again = load_source(SOURCE_PATH)
        assert isinstance(source, Source)
        assert source.id == "ted_api"
        assert source.coverage == "EU tenders"
        assert source.personal_data_fields
        assert source == again
        assert source is not again

    def test_load_source_attribution(self) -> None:
        """Attribution is the required TED acknowledgement string."""
        source = load_source(SOURCE_PATH)
        assert source.attribution == ATTRIBUTION

    def test_budget_values(self) -> None:
        """The polite budget is 30 requests/minute with a 1000ms gap."""
        source = load_source(SOURCE_PATH)
        budget = source.access.our_budget
        assert budget.requests_per_minute == 30
        assert budget.min_gap_ms == 1000

    @pytest.mark.parametrize(
        "missing",
        [
            ("id",),
            ("reuse",),
            ("attribution",),
            ("branding",),
            ("access",),
            ("paging",),
            ("personal_data_fields",),
            ("coverage",),
            ("access", "our_budget"),
            ("access", "our_budget", "requests_per_minute"),
            ("access", "our_budget", "min_gap_ms"),
        ],
    )
    def test_load_source_raises_on_missing_keys(
        self, tmp_path: Path, missing: tuple[str, ...]
    ) -> None:
        """Missing required keys raise ValueError."""
        path = _write_yaml(tmp_path / "source.yaml", _drop(_COMPLETE, missing))
        with pytest.raises(ValueError, match="missing keys"):
            load_source(path)

    def test_load_source_rejects_non_mapping(self, tmp_path: Path) -> None:
        """A YAML list is not a source document."""
        path = tmp_path / "source.yaml"
        path.write_text("- not-a-mapping\n", encoding="utf-8")
        with pytest.raises(ValueError, match="mapping"):
            load_source(path)

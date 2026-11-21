"""Connectors package for external API integrations."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from ..core.map import map_raw_to_notice
from ..core.model import Notice, RawNotice


def _coerce_date(value: date | datetime | str | None) -> date | None:
    """Return ``value`` as a date, or ``None`` when it is an open bound."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if text == "" or text.upper() == "D":
        return None
    return date.fromisoformat(text[:10])


def _json_files(path: Path) -> list[Path]:
    """Return JSON files in ``path`` and in immediate procedure subdirectories."""
    if path.is_file():
        return [path] if path.suffix == ".json" else []
    if not path.is_dir():
        return []
    files = sorted(path.glob("*.json"))
    for child in sorted(entry for entry in path.iterdir() if entry.is_dir()):
        if child.name.startswith("."):
            continue
        files.extend(sorted(child.glob("*.json")))
    return files


def _default_roots() -> list[Path]:
    """Return the visible and holdout fixture directories."""
    root = Path(__file__).resolve().parents[3]
    return [root / "fixtures" / "visible", root / "fixtures" / "holdout"]


class Connector(Protocol):
    """List, fetch and map notices. ``map`` is pure and does not use the network."""

    def list_changes(
        self,
        since: date | str | None = None,
        until: date | str | None = None,
    ) -> list[str]:
        """Return refs of notices published in the inclusive ``[since, until]`` window."""
        ...

    def fetch(self, ref: str) -> RawNotice:
        """Return the raw notice for ``ref``."""
        ...

    def map(self, raw: RawNotice) -> Notice:
        """Map a raw notice to the internal model. Pure; no network."""
        ...


class FakeConnector:
    """Fixture-backed connector. Reads local JSON only; never touches the network.

    With no path, notices are loaded from ``fixtures/visible`` and
    ``fixtures/holdout``. A file or a procedure directory works the same way.
    """

    def __init__(self, fixtures: str | Path | None = None) -> None:
        roots = [Path(fixtures)] if fixtures is not None else _default_roots()
        self._raw: dict[str, RawNotice] = {}
        self._order: list[str] = []
        for root in roots:
            self._load(root)

    def _load(self, path: Path) -> None:
        """Load every notice object under ``path`` into the in-memory index."""
        for file_path in _json_files(path):
            data = json.loads(file_path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                raw = RawNotice.model_validate(item)
                if raw.notice_id in self._raw:
                    continue
                self._raw[raw.notice_id] = raw
                self._order.append(raw.notice_id)

    def list_changes(
        self,
        since: date | str | None = None,
        until: date | str | None = None,
    ) -> list[str]:
        """Return fixture refs whose publication date falls in the window."""
        since_date = _coerce_date(since)
        until_date = _coerce_date(until)
        refs: list[str] = []
        for ref in self._order:
            published = self._raw[ref].publication_date
            if since_date is not None and published < since_date:
                continue
            if until_date is not None and published > until_date:
                continue
            refs.append(ref)
        return refs

    def fetch(self, ref: str) -> RawNotice:
        """Return the fixture raw notice for ``ref``. Does not use the network."""
        return self._raw[ref]

    def map(self, raw: RawNotice) -> Notice:
        """Map ``raw`` with the pure mapper. No network."""
        return map_raw_to_notice(raw)

"""Conformance runner for visible and holdout fixture sets.

Snapshots are split by procedure-identifier so a change and its predecessor
stay on the same side. Each §3.4 case tag appears in both ``fixtures/visible``
and ``fixtures/holdout``.

§3.4 case tags (README, link-resolution coverage):

- ``form_a_uuid_version`` — UUID + 2-digit version pointer
- ``form_a_index_keyed_by_components`` — UUID + version without zero-padding
- ``form_b_publication_number`` — publication-number pointer
- ``form_b_index_scan`` — publication number resolved via candidate keys
- ``missing_predecessor`` — pointer present, target absent
- ``no_pointer`` — no change-notice-version-identifier
- ``change_of_change_chain`` — chained predecessor pointers
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..cli import _load_notices

SECTION_3_4_CASE_TAGS: tuple[str, ...] = (
    "form_a_uuid_version",
    "form_a_index_keyed_by_components",
    "form_b_publication_number",
    "form_b_index_scan",
    "missing_predecessor",
    "no_pointer",
    "change_of_change_chain",
)

_PROCEDURE_KEYS = (
    "procedureIdentifier",
    "procedure_identifier",
    "procedure-identifier",
)
_CASE_TAG_KEYS = (
    "caseTags",
    "case_tags",
    "case-tags",
    "caseTag",
    "case_tag",
    "case-tag",
)


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


def _items(file_path: Path) -> list[dict[str, Any]]:
    """Return notice objects from a JSON file (object or list of objects)."""
    data = json.loads(file_path.read_text(encoding="utf-8"))
    raw_items = data if isinstance(data, list) else [data]
    return [item for item in raw_items if isinstance(item, dict)]


def notice_records(fixtures_path: str | Path) -> list[tuple[Path, dict[str, Any]]]:
    """Return ``(path, object)`` for every notice object under ``fixtures_path``."""
    path = Path(fixtures_path)
    records: list[tuple[Path, dict[str, Any]]] = []
    for file_path in _json_files(path):
        for item in _items(file_path):
            records.append((file_path, item))
    return records


def _procedure_from_item(item: dict[str, Any]) -> str | None:
    """Extract a procedure-identifier from a raw notice object."""
    for key in _PROCEDURE_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _procedure_from_path(file_path: Path, root: Path) -> str | None:
    """Use the parent directory name when notices are grouped by procedure."""
    parent = file_path.parent
    if parent == root or parent == Path("."):
        return None
    try:
        parent.relative_to(root)
    except ValueError:
        return None
    if parent.name.startswith("."):
        return None
    return parent.name


def procedure_identifiers(fixtures_path: str | Path) -> set[str]:
    """Return procedure-identifiers present under ``fixtures_path``."""
    root = Path(fixtures_path)
    identifiers: set[str] = set()
    for file_path, item in notice_records(root):
        procedure = _procedure_from_item(item) or _procedure_from_path(file_path, root)
        if procedure is not None:
            identifiers.add(procedure)
    return identifiers


def _tags_from_item(item: dict[str, Any]) -> set[str]:
    """Extract §3.4 case tags from a raw notice object."""
    tags: set[str] = set()
    for key in _CASE_TAG_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            tags.add(value.strip())
        elif isinstance(value, list):
            for part in value:
                if isinstance(part, str) and part.strip():
                    tags.add(part.strip())
    return tags


def case_tags(fixtures_path: str | Path) -> set[str]:
    """Return §3.4 case tags present under ``fixtures_path``."""
    tags: set[str] = set()
    for _file_path, item in notice_records(fixtures_path):
        tags |= _tags_from_item(item)
    return tags


def load_notices(fixtures_path: str | Path) -> list[Any]:
    """Load mapped notices from a fixture file or directory.

    A directory may be flat (``*.json``) or grouped by procedure-identifier
    (one subdirectory per procedure). Parsing matches
    :func:`ted_watch.cli._load_notices`.
    """
    path = Path(fixtures_path)
    if path.is_file() or not path.is_dir():
        return _load_notices(path)
    notices = list(_load_notices(path))
    for child in sorted(entry for entry in path.iterdir() if entry.is_dir()):
        if child.name.startswith("."):
            continue
        notices.extend(_load_notices(child))
    return notices


def _grouping_error(path: Path) -> str | None:
    """Return an error when a procedure directory does not match its notices."""
    if not path.is_dir():
        return None
    for child in sorted(entry for entry in path.iterdir() if entry.is_dir()):
        if child.name.startswith("."):
            continue
        found = {
            procedure
            for _file_path, item in notice_records(child)
            if (procedure := _procedure_from_item(item)) is not None
        }
        if not found:
            continue
        if found != {child.name}:
            return f"procedure directory {child.name} has identifiers {sorted(found)}"
    return None


def run(fixtures: str | Path) -> int:
    """Load notices from ``fixtures`` and report whether they parse.

    ``fixtures`` may be a JSON file, a flat directory, or a directory grouped
    by procedure-identifier (``fixtures/visible`` or ``fixtures/holdout``).
    Returns 0 when every notice parses, 1 otherwise.
    """
    path = Path(fixtures)
    if not path.exists():
        print(f"conformance: fixtures path not found: {path}", file=sys.stderr)
        return 1
    try:
        records = notice_records(path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"conformance: failed to read {path}: {exc}", file=sys.stderr)
        return 1
    if not records:
        print(f"conformance: no notices found in {path}", file=sys.stderr)
        return 1
    notices = load_notices(path)
    if len(notices) != len(records):
        print(
            f"conformance: loaded {len(notices)} of {len(records)} notices from {path}",
            file=sys.stderr,
        )
        return 1
    grouping_error = _grouping_error(path)
    if grouping_error is not None:
        print(f"conformance: {grouping_error}", file=sys.stderr)
        return 1
    procedures = procedure_identifiers(path)
    tags = case_tags(path)
    tag_text = ",".join(sorted(tags)) if tags else "-"
    print(
        f"conformance: loaded {len(notices)} notice(s) from {path} "
        f"({len(procedures)} procedure(s), tags={tag_text})"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the conformance runner argument parser."""
    parser = argparse.ArgumentParser(prog="ted_watch.conformance")
    parser.add_argument(
        "--fixtures",
        required=True,
        help="Fixture file or directory (visible, holdout, or flat connector fixtures)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the conformance kit against the directory given by ``--fixtures``."""
    args = build_parser().parse_args(argv)
    return run(args.fixtures)


if __name__ == "__main__":
    raise SystemExit(main())

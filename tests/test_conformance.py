"""Tests for the visible/holdout conformance fixture split."""

from pathlib import Path

import pytest
from src.ted_watch.conformance.coverage import load_manifest, missing_cases, side_tags
from src.ted_watch.conformance.runner import (
    SECTION_3_4_CASE_TAGS,
    case_tags,
    main,
    notice_records,
    procedure_identifiers,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
VISIBLE = REPO_ROOT / "fixtures" / "visible"
HOLDOUT = REPO_ROOT / "fixtures" / "holdout"
FLAT = REPO_ROOT / "fixtures" / "connectors" / "ted_api" / "fixtures"

_POINTER_KEYS = (
    "changeNoticeVersionIdentifier",
    "change_notice_version_identifier",
    "change-notice-version-identifier",
)


def _index_keys(item: dict) -> set[str]:
    """Identifiers under which a notice may be resolved as a predecessor."""
    keys: set[str] = set()
    for field in ("noticeId", "publicationNumber", "noticeIdentifier", "notice_id"):
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            keys.add(value.strip())
    uuid = item.get("noticeIdentifier")
    version = item.get("noticeVersion")
    if isinstance(uuid, str) and uuid.strip() and version is not None:
        version_text = str(version).strip()
        if version_text:
            keys.add(f"{uuid.strip()}-{version_text}")
            if version_text.isdigit():
                keys.add(f"{uuid.strip()}-{version_text.zfill(2)}")
                keys.add(f"{uuid.strip()}-{int(version_text)}")
    return keys


def _pointer(item: dict) -> str | None:
    for key in _POINTER_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def test_no_procedure_appears_in_both_sets() -> None:
    """No procedure-identifier appears in both the visible and holdout sets."""
    visible = procedure_identifiers(VISIBLE)
    holdout = procedure_identifiers(HOLDOUT)
    assert visible
    assert holdout
    assert visible & holdout == set()


def test_each_section_3_4_case_tag_appears_in_both_sets() -> None:
    """Each §3.4 case tag appears in both the visible and holdout sets."""
    visible_tags = case_tags(VISIBLE)
    holdout_tags = case_tags(HOLDOUT)
    for tag in SECTION_3_4_CASE_TAGS:
        assert tag in visible_tags
        assert tag in holdout_tags


def test_fixtures_are_grouped_by_procedure_identifier() -> None:
    """Notices live in a directory named for their procedure-identifier."""
    for root in (VISIBLE, HOLDOUT):
        assert root.is_dir()
        directories = [path for path in root.iterdir() if path.is_dir()]
        assert directories
        for proc_dir in directories:
            assert procedure_identifiers(proc_dir) == {proc_dir.name}


def test_change_and_predecessor_share_a_procedure() -> None:
    """A change and its predecessor, when both present, stay on the same side."""
    for root in (VISIBLE, HOLDOUT):
        records = [item for _path, item in notice_records(root)]
        index: dict[str, dict] = {}
        for item in records:
            for key in _index_keys(item):
                index.setdefault(key, item)
        for item in records:
            pointer = _pointer(item)
            if pointer is None or pointer not in index:
                continue
            predecessor = index[pointer]
            assert predecessor["procedureIdentifier"] == item["procedureIdentifier"]
            assert predecessor["procedureIdentifier"] in procedure_identifiers(root)


@pytest.mark.parametrize("fixtures_dir", [VISIBLE, HOLDOUT, FLAT])
def test_conformance_runner_accepts_fixtures_argument(fixtures_dir: Path) -> None:
    """The runner can be pointed at either split directory via --fixtures."""
    assert main(["--fixtures", str(fixtures_dir)]) == 0


@pytest.mark.parametrize("side, root", [("visible", VISIBLE), ("holdout", HOLDOUT)])
def test_every_section_3_4_case_is_covered_on_each_side(side: str, root: Path) -> None:
    """Each §3.4 case is tagged in the manifest on both the visible and holdout side."""
    manifest = load_manifest(REPO_ROOT / "fixtures" / "cases.yaml")
    missing = missing_cases(side_tags(manifest, root))
    assert not missing, f"{side} side is missing §3.4 case(s): {', '.join(missing)}"


@pytest.mark.parametrize("root", [VISIBLE, HOLDOUT])
def test_manifest_matches_fixture_case_tags(root: Path) -> None:
    """The manifest tags of every procedure equal the caseTags in its fixtures."""
    manifest = load_manifest(REPO_ROOT / "fixtures" / "cases.yaml")
    for proc_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        assert proc_dir.name in manifest, f"{proc_dir.name} missing from cases.yaml"
        assert manifest[proc_dir.name] == case_tags(proc_dir), proc_dir.name

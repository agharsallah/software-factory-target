"""§3.4 case coverage across the visible and holdout fixture sides.

``fixtures/cases.yaml`` maps each procedure directory to its case tags.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# One entry per §3.4 case; "both pointer forms" needs both pointer tags.
SECTION_3_4_CASES: dict[str, tuple[str, ...]] = {
    "both pointer forms": ("form_a_uuid_version", "form_b_publication_number"),
    "change of a change": ("change_of_change_chain",),
    "lot added": ("lot_added",),
    "lot removed": ("lot_removed",),
    "differing lot deadlines": ("differing_lot_deadlines",),
    "no-op change": ("no_op_change",),
    "date without time": ("date_without_time",),
    "offset differs": ("offset_differs",),
    "dangling pointer": ("dangling_pointer",),
    "predecessor outside window": ("predecessor_outside_window",),
    "duplicate delivery": ("duplicate_delivery",),
    "out-of-order delivery": ("out_of_order_delivery",),
}


def load_manifest(manifest_path: str | Path) -> dict[str, set[str]]:
    """Return the manifest as ``{procedure: {case tags}}``."""
    data: Any = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8")) or {}
    return {str(proc): {str(tag) for tag in tags or []} for proc, tags in data.items()}


def side_tags(manifest: dict[str, set[str]], side_root: str | Path) -> set[str]:
    """Return the tags of manifest procedures whose directory is under ``side_root``."""
    root = Path(side_root)
    tags: set[str] = set()
    for procedure, procedure_tags in manifest.items():
        if (root / procedure).is_dir():
            tags |= procedure_tags
    return tags


def missing_cases(tags: set[str]) -> list[str]:
    """Return the names of §3.4 cases not fully covered by ``tags``."""
    return [
        case
        for case, required in SECTION_3_4_CASES.items()
        if not all(tag in tags for tag in required)
    ]

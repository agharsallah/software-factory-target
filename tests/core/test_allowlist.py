"""Tests for the §3.3 field allowlist guard."""

import json
from pathlib import Path

import pytest
from src.ted_watch.core.allowlist import ALLOWLIST, strip_to_allowlist

FIXTURES_ROOT = Path(__file__).parent.parent.parent / "fixtures"
FIXTURE_PATHS = sorted(FIXTURES_ROOT.rglob("*.json"))


def _collect_keys(value: object) -> set[str]:
    """Collect every object key in a JSON value."""
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            found.add(key)
            found.update(_collect_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_collect_keys(item))
    return found


class TestAllowlist:
    """Fixture scan and contact-field stripping."""

    def test_fixture_scan_sees_every_json_file(self) -> None:
        """The scan covers all JSON under fixtures/, not a hand-picked subset."""
        assert FIXTURE_PATHS
        assert FIXTURE_PATHS == sorted(FIXTURES_ROOT.rglob("*.json"))

    @pytest.mark.parametrize("path", FIXTURE_PATHS, ids=lambda path: path.name)
    def test_fixture_keys_are_allowlisted(self, path: Path) -> None:
        """Every key in a fixture JSON file is on the allowlist."""
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        unknown = _collect_keys(data) - ALLOWLIST
        assert unknown == set()
        cleaned, dropped = strip_to_allowlist(data)
        assert dropped == 0
        assert cleaned == data
        assert cleaned is not data

    def test_synthetic_contact_field_is_removed(self) -> None:
        """Unknown and contact-like keys are dropped, counted, and not stored."""
        raw = {
            "noticeId": "123456-2024",
            "title": "Construction of new hospital wing",
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+32 2 000 0000",
            "Email": "also@example.com",
            "PHONE": "+32 2 111 1111",
            "secret": "not-approved",
            "lots": [
                {
                    "id": "LOT-001",
                    "deadline": "2024-02-28",
                    "name": "Lot contact",
                    "email": "lot@example.com",
                }
            ],
        }
        snapshot = json.loads(json.dumps(raw))

        cleaned, dropped = strip_to_allowlist(raw)

        assert cleaned == {
            "noticeId": "123456-2024",
            "title": "Construction of new hospital wing",
            "lots": [{"id": "LOT-001", "deadline": "2024-02-28"}],
        }
        assert "name" not in cleaned
        assert "email" not in cleaned
        assert "phone" not in cleaned
        assert dropped == 8
        assert raw == snapshot
        assert cleaned is not raw

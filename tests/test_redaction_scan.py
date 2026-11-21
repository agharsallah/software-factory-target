"""End-to-end redaction scan: seeded contact fields never reach the CLI output."""

import json
import re
from pathlib import Path

import pytest
from src.ted_watch import cli
from src.ted_watch.cli import main
from src.ted_watch.core.map import map_raw_to_notice
from src.ted_watch.core.model import RawNotice
from src.ted_watch.core.source import load_source

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "fixtures" / "redaction" / "notice_with_contacts.json"
SOURCE_PATH = REPO_ROOT / "src" / "ted_watch" / "connectors" / "ted_api" / "source.yaml"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\+\d[\d\s().-]{6,}\d")


def _raw() -> RawNotice:
    """Load the synthetic raw notice that carries contact fields."""
    return RawNotice.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def _contact_values() -> list[str]:
    """Seeded contact values, taken from the fixture by personal field name."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fields = load_source(SOURCE_PATH).personal_data_fields
    return [data[name] for name in fields if name in data]


def _leaks(notice: object) -> list[str]:
    """Return personal field names or seeded values found on a mapped Notice."""
    dumped = json.dumps(notice.model_dump(mode="json"), default=str)  # type: ignore[attr-defined]
    fields = load_source(SOURCE_PATH).personal_data_fields
    found = [name for name in fields if name in dumped]
    return found + [value for value in _contact_values() if value in dumped]


class TestRedactionScan:
    """Contact name, email and phone never appear in the pipeline output."""

    def test_fixture_carries_contacts(self) -> None:
        """The synthetic raw notice really includes name, email and phone values."""
        values = _contact_values()
        assert len(values) >= 3
        assert any(EMAIL_RE.fullmatch(v) for v in values)
        assert any(PHONE_RE.fullmatch(v) for v in values)

    def test_output_has_no_contact_values(self, tmp_path: Path) -> None:
        """The CLI output is non-empty and holds no seeded value, email or phone."""
        out = tmp_path / "out.jsonl"
        assert main(["--fixtures", str(FIXTURE), "--out", str(out)]) == 0
        text = out.read_text(encoding="utf-8")
        assert text.strip() != ""
        for value in _contact_values():
            assert value not in text
        assert EMAIL_RE.findall(text) == []
        assert PHONE_RE.findall(text) == []

    def test_mapped_notice_has_no_contact_fields(self) -> None:
        """map drops contact fields from the Notice."""
        assert _leaks(map_raw_to_notice(_raw())) == []

    def test_guard_fails_when_map_passes_contacts_through(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A map that copies contact fields onto the Notice is caught by the guard."""

        def leaky(raw: RawNotice):  # type: ignore[no-untyped-def]
            notice = map_raw_to_notice(raw)
            for name, value in (raw.model_extra or {}).items():
                setattr(notice, name, value)
            return notice

        monkeypatch.setattr(cli, "map_raw_to_notice", leaky)
        notices = cli._load_notices(FIXTURE)
        assert _leaks(notices[0]) != []

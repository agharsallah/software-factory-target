"""Command-line interface for writing a sample of deadline changes as JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .core.dedupe import event_id
from .core.diff import diff_notices
from .core.map import map_raw_to_notice
from .core.model import RawNotice

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES = REPO_ROOT / "fixtures" / "connectors" / "ted_api" / "fixtures"

ISO3_TO_ISO2 = {
    "POL": "PL",
    "DEU": "DE",
    "FRA": "FR",
    "ITA": "IT",
    "ESP": "ES",
    "GBR": "GB",
    "NLD": "NL",
    "BEL": "BE",
    "AUT": "AT",
    "PRT": "PT",
    "SWE": "SE",
    "DNK": "DK",
    "FIN": "FI",
    "IRL": "IE",
    "GRC": "GR",
    "CZE": "CZ",
    "HUN": "HU",
    "ROU": "RO",
    "BGR": "BG",
    "HRV": "HR",
    "SVK": "SK",
    "SVN": "SI",
    "LTU": "LT",
    "LVA": "LV",
    "EST": "EE",
    "LUX": "LU",
    "MLT": "MT",
    "CYP": "CY",
}


def _parse_date(value: str | None) -> date | None:
    """Parse a date string, treating 'D' as no bound."""
    if value is None:
        return None
    value = value.strip()
    if value.upper() == "D" or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None


def _normalize_country(code: str) -> str:
    code = code.strip().upper()
    if len(code) == 3:
        return ISO3_TO_ISO2.get(code, code[:2])
    return code


def _load_notices(fixtures_path: Path) -> list[Any]:
    path = Path(fixtures_path)
    files: list[Path] = []
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(path.glob("*.json"))
    else:
        return []

    notices: list[Any] = []
    for file_path in files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                raw = RawNotice.model_validate(item)
            except Exception:  # noqa: BLE001
                continue
            notices.append(map_raw_to_notice(raw))
    return notices


def _matches_cpv(notice: Any, cpv_division: str | None) -> bool:
    if cpv_division is None:
        return True
    division = str(cpv_division).strip()
    for code in notice.cpv_codes or []:
        if str(code).strip()[: len(division)] == division:
            return True
    return False


def _matches_country(notice: Any, countries: list[str]) -> bool:
    if not countries:
        return True
    wanted = {_normalize_country(c) for c in countries}
    actual = {str(notice.country).upper(), str(notice.authority_country).upper()}
    return bool(wanted & actual)


def _matches_dates(notice: Any, since: str | None, until: str | None) -> bool:
    since_date = _parse_date(since)
    until_date = _parse_date(until)
    pub = notice.publication_date
    if since_date is not None and pub < since_date:
        return False
    if until_date is not None and pub > until_date:
        return False
    return True


def _build_events(notices: list[Any]) -> list[dict[str, Any]]:
    """Build events sorted by (publication, lot, kind), one per logical change."""
    tagged: list[tuple[tuple[str, str, str, str], dict[str, Any]]] = []
    seen: set[str] = set()
    for notice in notices:
        events = _notice_events(notice)
        for event in events:
            sort_key = (
                notice.publication_date.isoformat(),
                str(event.get("lot") or ""),
                str(event.get("kind") or ""),
                json.dumps(event, sort_keys=True, ensure_ascii=False, default=str),
            )
            identity = event_id(
                {
                    **event,
                    "procedure": notice.procedure_identifier,
                    "current_notice": notice.publication_number or notice.notice_id,
                }
            )
            if identity in seen:
                continue
            seen.add(identity)
            tagged.append((sort_key, event))
    tagged.sort(key=lambda item: item[0])
    return [event for _, event in tagged]


def _notice_events(notice: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    # susp-review / cancel-intent are procedure events, never deadline rows.
    procedure_events = diff_notices(
        None,
        notice,
        coverage="EU tenders",
        attribution="TED (ted.europa.eu)",
    )
    if procedure_events:
        for procedure_event in procedure_events:
            events.append(dict(procedure_event))
        return events

    reason_code = notice.change_reason_code
    kind = reason_code if reason_code is not None else "none"

    if notice.lots:
        for lot in notice.lots:
            lot_reason = lot.deadline_change_reason_code
            lot_kind = lot_reason if lot_reason is not None else kind
            if lot_kind is None or str(lot_kind).strip().lower() == "none":
                continue
            current = lot.deadline
            if current is None:
                continue
            events.append(
                {
                    "event": "deadline_change",
                    "kind": lot_kind,
                    "lot": lot.lot_id,
                    "previous": None,
                    "current": current.isoformat() if current is not None else None,
                    "current_utc": (
                        current.isoformat() + "T00:00:00Z" if current is not None else None
                    ),
                    "source": notice.url if notice.url else "ted.europa.eu",
                    "coverage": "EU tenders",
                    "attribution": "TED (ted.europa.eu)",
                }
            )
    elif notice.deadline is not None:
        if kind is None or str(kind).strip().lower() == "none":
            return events
        current = notice.deadline
        events.append(
            {
                "event": "deadline_change",
                "kind": kind,
                "lot": None,
                "previous": None,
                "current": current.isoformat(),
                "current_utc": current.isoformat() + "T00:00:00Z",
                "source": notice.url if notice.url else "ted.europa.eu",
                "coverage": "EU tenders",
                "attribution": "TED (ted.europa.eu)",
            }
        )
    return events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tenders.cli")
    parser.add_argument("--cpv-division", dest="cpv_division", default=None)
    parser.add_argument("--country", action="append", default=[])
    parser.add_argument("--since", default=None)
    parser.add_argument("--until", default=None)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--fixtures",
        nargs="?",
        const=str(DEFAULT_FIXTURES),
        default=None,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fixtures_path = args.fixtures if args.fixtures is not None else DEFAULT_FIXTURES
    notices = _load_notices(Path(fixtures_path))
    filtered = [
        n
        for n in notices
        if _matches_cpv(n, args.cpv_division)
        and _matches_country(n, args.country)
        and _matches_dates(n, args.since, args.until)
    ]
    events = _build_events(filtered)

    out_path = Path(args.out)
    if out_path.parent and str(out_path.parent) not in ("", "."):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

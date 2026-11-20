"""Hypothesis strategies that mutate TED fixture JSON."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import hypothesis.strategies as st

from ..core.model import RawNotice

REPO_ROOT = Path(__file__).resolve().parents[3]

# Fields RawNotice can omit. Required aliases (noticeId, title, ...) stay put
# so mutated payloads still follow the validation_alias paths.
OPTIONAL_FIELDS = frozenset(
    {
        "deadline",
        "authorityCity",
        "authority_city",
        "cpvCodes",
        "cpv_codes",
        "lots",
        "changeReasonCode",
        "change_reason_code",
        "changeReason",
        "change_reason",
        "noticeIdentifier",
        "notice_identifier",
        "noticeVersion",
        "notice_version",
        "publicationNumber",
        "publication_number",
        "procedureIdentifier",
        "procedure_identifier",
        "changeNoticeVersionIdentifier",
        "change_notice_version_identifier",
        "url",
        "buyer-country",
        "classification-cpv",
        "links",
        "change-reason-code",
        "change-notice-version-identifier",
        "notice-identifier",
        "notice-version",
        "publication-number",
        "procedure-identifier",
    }
)

# Lot-aligned deadline arrays from the TED search API. Truncated independently
# so conformance can see arrays of unequal length.
DATE_TIME_ARRAY_KEYS = (
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-tender-time-lot",
    "deadline-receipt-request-date-lot",
)

CONNECTORS = ("ted_api",)

_FIXTURE_CACHE: dict[str, tuple[dict, ...]] = {}


def fixture_dir(connector: str) -> Path:
    """Return the on-disk fixture directory for ``connector``."""
    if connector not in CONNECTORS:
        raise KeyError(f"unknown connector: {connector}")
    return REPO_ROOT / "fixtures" / "connectors" / connector / "fixtures"


def load_fixture_payloads(connector: str) -> tuple[dict, ...]:
    """Load connector fixture JSON objects, cached for strategy draws."""
    cached = _FIXTURE_CACHE.get(connector)
    if cached is not None:
        return cached
    directory = fixture_dir(connector)
    payloads: list[dict] = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            payloads.append(data)
    if not payloads:
        raise FileNotFoundError(f"no fixtures for connector {connector}")
    cached = tuple(payloads)
    _FIXTURE_CACHE[connector] = cached
    return cached


def is_date_time_array_key(key: str) -> bool:
    """True when ``key`` names a lot-aligned date or time array."""
    normalized = key.replace("_", "-").lower()
    if normalized in {"deadline", "publication-date", "publicationdate"}:
        return False
    return "date" in normalized or "time" in normalized


def _lot_value(lot: dict, *keys: str) -> object:
    for key in keys:
        if key in lot and lot[key] not in (None, ""):
            return lot[key]
    return None


def ensure_date_time_arrays(payload: dict) -> None:
    """Attach parallel deadline arrays when the fixture has none to truncate."""
    lots = payload.get("lots")
    if not isinstance(lots, list):
        lots = []
    dates: list[object] = []
    times: list[object] = []
    requests: list[object] = []
    for lot in lots:
        if not isinstance(lot, dict):
            continue
        deadline = _lot_value(lot, "deadline", "submissionDeadline")
        dates.append(deadline)
        times.append(_lot_value(lot, "time", "deadlineTime", "submissionTime") or "17:00:00")
        requests.append(_lot_value(lot, "requestDeadline", "deadlineReceiptRequest") or deadline)
    defaults = {
        "deadline-receipt-tender-date-lot": dates,
        "deadline-receipt-tender-time-lot": times,
        "deadline-receipt-request-date-lot": requests,
    }
    for key, value in defaults.items():
        if key not in payload:
            payload[key] = list(value)


def mutate_fixture_json(
    payload: dict,
    *,
    drop_fields: list[str],
    lot_order: list[int] | None = None,
    truncate_lengths: dict[str, int] | None = None,
) -> dict:
    """Drop optional fields, shuffle lots, and truncate date/time arrays.

    Required RawNotice fields are never removed. Date and time arrays are
    shortened independently, which yields arrays of unequal length.
    """
    data = copy.deepcopy(payload)
    for key in drop_fields:
        if key in OPTIONAL_FIELDS:
            data.pop(key, None)
    lots = data.get("lots")
    if isinstance(lots, list) and lot_order is not None and len(lot_order) == len(lots):
        data["lots"] = [lots[index] for index in lot_order]
    ensure_date_time_arrays(data)
    for key, value in list(data.items()):
        if not isinstance(value, list) or not is_date_time_array_key(key):
            continue
        if not truncate_lengths or key not in truncate_lengths:
            continue
        length = truncate_lengths[key]
        if length < 0:
            length = 0
        data[key] = value[:length]
    return data


def _optional_present(payload: dict) -> list[str]:
    return [key for key in payload if key in OPTIONAL_FIELDS]


@st.composite
def mutated_fixture_json(draw, connector: str = "ted_api") -> dict:
    """Draw a fixture and mutate it: drop optionals, shuffle lots, truncate arrays."""
    payloads = load_fixture_payloads(connector)
    index = draw(st.integers(min_value=0, max_value=len(payloads) - 1))
    payload = payloads[index]

    present = _optional_present(payload)
    if present:
        drop_fields = draw(st.lists(st.sampled_from(present), unique=True, max_size=len(present)))
    else:
        drop_fields = []

    lots = payload.get("lots")
    lot_order = None
    if isinstance(lots, list) and len(lots) >= 2 and "lots" not in drop_fields:
        lot_order = list(draw(st.permutations(range(len(lots)))))

    source_lots = lots if isinstance(lots, list) and "lots" not in drop_fields else []
    lengths: dict[str, int] = {}
    seen: dict[str, int] = {}
    for key, value in payload.items():
        if isinstance(value, list) and is_date_time_array_key(key):
            seen[key] = len(value)
    for key in DATE_TIME_ARRAY_KEYS:
        seen.setdefault(key, len(source_lots) if isinstance(source_lots, list) else 0)
    for key, size in seen.items():
        if size <= 0:
            lengths[key] = 0
            continue
        lengths[key] = draw(st.integers(min_value=0, max_value=size - 1))

    return mutate_fixture_json(
        payload,
        drop_fields=drop_fields,
        lot_order=lot_order,
        truncate_lengths=lengths,
    )


@st.composite
def mutated_raw_notice(draw, connector: str = "ted_api") -> RawNotice:
    """Yield a RawNotice built from mutated fixture JSON."""
    payload = draw(mutated_fixture_json(connector))
    return RawNotice.model_validate(payload)

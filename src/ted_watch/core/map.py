"""Pure mapping functions from raw TED API data to internal models."""

import re
from datetime import date
from typing import Any

from .model import LotDeadline, Notice, RawNotice

# TED change-reason-code vocabulary. Anything else is reported, never dropped.
_KNOWN_CHANGE_REASON_CODES = frozenset(
    {
        "update-add",
        "cor-buy",
        "cor-pub",
        "info-release",
        "susp-review",
        "cancel-intent",
        "none",
    }
)

# change-notice-version-identifier: UUID + version, or a publication number.
_UUID_VERSION_POINTER = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}-\d{1,2}$"
)
_PUBLICATION_POINTER = re.compile(r"^\d+-\d{4}$")

# Parallel lot arrays that must share one length. Canonical TED name, then aliases.
_LOT_ARRAY_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("identifier-lot", ("identifier-lot", "identifierLot", "identifier_lot")),
    (
        "deadline-receipt-tender-date-lot",
        (
            "deadline-receipt-tender-date-lot",
            "deadlineReceiptTenderDateLot",
            "deadline_receipt_tender_date_lot",
        ),
    ),
    (
        "deadline-receipt-tender-time-lot",
        (
            "deadline-receipt-tender-time-lot",
            "deadlineReceiptTenderTimeLot",
            "deadline_receipt_tender_time_lot",
        ),
    ),
    (
        "deadline-receipt-request-date-lot",
        (
            "deadline-receipt-request-date-lot",
            "deadlineReceiptRequestDateLot",
            "deadline_receipt_request_date_lot",
        ),
    ),
)


def _parse_date(value: Any) -> date | None:
    """Parse date from various formats used in TED API."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        # TED API uses YYYY-MM-DD format
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _texts(value: Any) -> list[str]:
    """Flatten a scalar or list field to stripped strings, skipping nulls."""
    if value is None:
        return []
    items = value if isinstance(value, list) else [value]
    texts: list[str] = []
    for item in items:
        if item is None:
            continue
        texts.append(str(item).strip())
    return texts


def _unknown_reason(code: str) -> dict[str, str] | None:
    """Return an unknown entry when ``code`` is not a recognised reason code."""
    if code.lower() in _KNOWN_CHANGE_REASON_CODES:
        return None
    return {"kind": "change-reason-code", "value": code}


def _is_recognised_pointer(value: str) -> bool:
    """True for UUID+version and publication-number pointer shapes."""
    return bool(_UUID_VERSION_POINTER.match(value) or _PUBLICATION_POINTER.match(value))


def _unknown_pointer(value: str) -> dict[str, str] | None:
    """Return an unknown entry when a pointer is present but not a known shape."""
    if _is_recognised_pointer(value):
        return None
    return {"kind": "pointer", "value": value}


def _lot_reason_code(lot: dict) -> Any:
    """Resolve the per-lot change-reason code using the fixture field names."""
    return lot.get("deadlineChangeReasonCode") or lot.get("changeReasonCode")


def _extra_map(raw: RawNotice) -> dict[str, Any]:
    """Return undeclared TED fields carried on the raw notice."""
    extra = raw.model_extra or {}
    return extra if isinstance(extra, dict) else {}


def _lookup_list(data: dict[str, Any], aliases: tuple[str, ...]) -> list[Any] | None:
    """Return the first alias that holds a list, if any."""
    for name in aliases:
        if name not in data or data[name] is None:
            continue
        value = data[name]
        if isinstance(value, list):
            return value
        return None
    return None


def _lot_array_unknowns(raw: RawNotice) -> list[dict[str, str]]:
    """Record one unknown when parallel lot arrays have different lengths."""
    extra = _extra_map(raw)
    present: list[tuple[str, int]] = []
    for canonical, aliases in _LOT_ARRAY_FIELDS:
        values = _lookup_list(extra, aliases)
        if values is not None:
            present.append((canonical, len(values)))
    if len(present) < 2:
        return []
    lengths = {length for _, length in present}
    if len(lengths) == 1:
        return []
    signature = ",".join(f"{name}:{length}" for name, length in present)
    return [{"kind": "lot-arrays", "value": signature}]


def _parse_lots(raw_lots: list[dict]) -> tuple[list[LotDeadline], list[dict[str, str]]]:
    """Extract lot deadlines and any unrecognised per-lot reason codes."""
    result: list[LotDeadline] = []
    unknowns: list[dict[str, str]] = []
    for lot in raw_lots:
        for code in _texts(_lot_reason_code(lot)):
            unknown = _unknown_reason(code)
            if unknown is not None:
                unknowns.append(unknown)

        lot_id = lot.get("id") or lot.get("lotId") or lot.get("lot_id")
        if not lot_id:
            continue

        deadline = _parse_date(lot.get("deadline") or lot.get("submissionDeadline"))

        if deadline is None:
            continue

        result.append(
            LotDeadline(
                lot_id=str(lot_id),
                deadline=deadline,
                deadline_change_reason_code=_lot_reason_code(lot),
                deadline_change_reason=lot.get("deadlineChangeReason") or lot.get("changeReason"),
            )
        )
    return result, unknowns


def _collect_unknowns(raw: RawNotice, lot_unknowns: list[dict[str, str]]) -> list[dict[str, str]]:
    """Collect unknowns in a stable order.

    Notice-level reason codes, then pointer shape, then unequal lot arrays,
    then per-lot reason codes. Pure: no globals and no mutation of ``raw``.
    """
    unknowns: list[dict[str, str]] = []
    seen_reasons: set[str] = set()
    for code in _texts(raw.change_reason_code):
        seen_reasons.add(code)
        unknown = _unknown_reason(code)
        if unknown is not None:
            unknowns.append(unknown)
    # Kebab-case TED payloads land in extras when the alias did not consume them.
    for code in _texts(_extra_map(raw).get("change-reason-code")):
        if code in seen_reasons:
            continue
        unknown = _unknown_reason(code)
        if unknown is not None:
            unknowns.append(unknown)

    seen_pointers: set[str] = set()
    for pointer in _texts(raw.change_notice_version_identifier):
        seen_pointers.add(pointer)
        unknown = _unknown_pointer(pointer)
        if unknown is not None:
            unknowns.append(unknown)
    for pointer in _texts(_extra_map(raw).get("change-notice-version-identifier")):
        if pointer in seen_pointers:
            continue
        unknown = _unknown_pointer(pointer)
        if unknown is not None:
            unknowns.append(unknown)

    unknowns.extend(_lot_array_unknowns(raw))
    unknowns.extend(lot_unknowns)
    return unknowns


def map_raw_to_notice(raw: RawNotice) -> Notice:
    """
    Pure function mapping RawNotice to internal Notice.

    Zero network calls, zero side effects. Transforms TED search API v3
    JSON structure to normalized internal representation. Unrecognised
    change-reason codes, unrecognisable pointer shapes and unequal lot
    arrays are returned on ``Notice.unknowns`` and are never dropped.
    """
    lots, lot_unknowns = _parse_lots(raw.lots)
    unknowns = _collect_unknowns(raw, lot_unknowns)

    return Notice(
        notice_id=raw.notice_id,
        title=raw.title,
        notice_type=raw.notice_type,
        publication_date=raw.publication_date,
        deadline=raw.deadline,
        country=raw.country,
        authority_name=raw.authority_name,
        authority_city=raw.authority_city,
        authority_country=raw.authority_country,
        cpv_codes=raw.cpv_codes,
        lots=lots,
        change_reason_code=raw.change_reason_code,
        change_reason=raw.change_reason,
        notice_identifier=raw.notice_identifier,
        notice_version=raw.notice_version,
        publication_number=raw.publication_number,
        procedure_identifier=raw.procedure_identifier,
        change_notice_version_identifier=raw.change_notice_version_identifier,
        url=raw.url,
        unknowns=unknowns,
    )

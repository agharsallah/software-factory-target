"""Pure mapping functions from raw TED API data to internal models."""

from datetime import date
from typing import Any

from .model import LotDeadline, Notice, RawNotice


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


def _parse_lots(raw_lots: list[dict]) -> list[LotDeadline]:
    """Extract and normalize lot deadline information."""
    result: list[LotDeadline] = []
    for lot in raw_lots:
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
                deadline_change_reason_code=lot.get("deadlineChangeReasonCode")
                or lot.get("changeReasonCode"),
                deadline_change_reason=lot.get("deadlineChangeReason") or lot.get("changeReason"),
            )
        )
    return result


def map_raw_to_notice(raw: RawNotice) -> Notice:
    """
    Pure function mapping RawNotice to internal Notice.

    Zero network calls, zero side effects. Transforms TED search API v3
    JSON structure to normalized internal representation.
    """
    lots = _parse_lots(raw.lots)

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
    )

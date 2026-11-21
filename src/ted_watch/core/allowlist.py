"""Strip captured notices to the §3.3 field allowlist.

Only approved notice fields are kept. Contact data (name, email, phone) is
never stored. ``strip_to_allowlist`` is the guard for fixtures and for a
future capture path: call it before constructing a model.
"""

from typing import Any

# §3.3 approved TED search API v3 fields. ``deadline-receipt-*`` is the
# per-lot deadline family named in the plan.
SECTION_3_3_FIELDS = {
    "publication-number",
    "notice-identifier",
    "notice-version",
    "procedure-identifier",
    "change-notice-version-identifier",
    "change-reason-code",
    "identifier-lot",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-tender-time-lot",
    "deadline-receipt-request-date-lot",
    "buyer-country",
    "classification-cpv",
    "notice-type",
    "links",
}

# RawNotice / Notice fields (python names and validation aliases) plus lot
# keys already present in fixtures and read by map.
MODEL_FIELDS = {
    "notice_id",
    "noticeId",
    "title",
    "notice_type",
    "noticeType",
    "publication_date",
    "publicationDate",
    "deadline",
    "country",
    "authority_name",
    "authorityName",
    "authority_city",
    "authorityCity",
    "authority_country",
    "authorityCountry",
    "cpv_codes",
    "cpvCodes",
    "lots",
    "change_reason_code",
    "changeReasonCode",
    "change_reason",
    "changeReason",
    "notice_identifier",
    "noticeIdentifier",
    "notice_version",
    "noticeVersion",
    "publication_number",
    "publicationNumber",
    "procedure_identifier",
    "procedureIdentifier",
    "change_notice_version_identifier",
    "changeNoticeVersionIdentifier",
    "url",
    "lot_id",
    "lotId",
    "id",
    "submissionDeadline",
    "deadline_change_reason_code",
    "deadlineChangeReasonCode",
    "deadline_change_reason",
    "deadlineChangeReason",
}

ALLOWLIST = SECTION_3_3_FIELDS | MODEL_FIELDS

# Contact-like keys are always dropped, even if a future edit adds them above.
CONTACT_KEYS = {"name", "email", "phone"}


def _is_contact_key(key: str) -> bool:
    """Return True when ``key`` is a contact-like field name."""
    return key.lower() in CONTACT_KEYS


def _is_allowed_key(key: str) -> bool:
    """Return True when ``key`` is on the §3.3 allowlist."""
    if key.startswith("deadline-receipt-"):
        return True
    return key in ALLOWLIST


def _strip(value: Any) -> tuple[Any, int]:
    """Return a stripped copy of ``value`` and how many keys were dropped."""
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        dropped = 0
        for key, item in value.items():
            key_text = key if isinstance(key, str) else str(key)
            if _is_contact_key(key_text) or not _is_allowed_key(key_text):
                dropped += 1
                continue
            stripped, nested = _strip(item)
            cleaned[key] = stripped
            dropped += nested
        return cleaned, dropped
    if isinstance(value, list):
        cleaned_list: list[Any] = []
        dropped = 0
        for item in value:
            stripped, nested = _strip(item)
            cleaned_list.append(stripped)
            dropped += nested
        return cleaned_list, dropped
    return value, 0


def strip_to_allowlist(raw: dict) -> tuple[dict, int]:
    """Return ``raw`` reduced to the allowlist, plus how many keys were dropped.

    Unknown keys and contact-like keys (``name``, ``email``, ``phone``,
    matched case-insensitively) are removed and counted. Nested objects and
    lists are stripped the same way. The input mapping is never mutated.
    """
    cleaned, dropped = _strip(raw)
    return cleaned, dropped

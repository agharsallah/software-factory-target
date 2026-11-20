"""Core domain models for TED notice processing."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class LotDeadline(BaseModel):
    """Deadline information for a specific lot within a notice."""

    lot_id: str = Field(..., description="Unique identifier for the lot")
    deadline: date = Field(..., description="Submission deadline for this lot")
    deadline_change_reason_code: str | None = Field(
        None, description="Code indicating reason for deadline change"
    )
    deadline_change_reason: str | None = Field(
        None, description="Human-readable reason for deadline change"
    )


class RawNotice(BaseModel):
    """Raw notice as received from TED search API v3."""

    model_config = ConfigDict(extra="allow")

    notice_id: str = Field(
        ..., validation_alias="noticeId", description="Unique notice identifier (TED ID)"
    )
    title: str = Field(..., description="Notice title")
    notice_type: str = Field(
        ...,
        validation_alias="noticeType",
        description="Type of notice (e.g., 'contract', 'planning')",
    )
    publication_date: date = Field(
        ..., validation_alias="publicationDate", description="Date notice was published"
    )
    deadline: date | None = Field(None, description="Overall submission deadline")
    country: str = Field(..., description="Country code (ISO 3166-1 alpha-2)")
    authority_name: str = Field(
        ..., validation_alias="authorityName", description="Contracting authority name"
    )
    authority_city: str | None = Field(
        None, validation_alias="authorityCity", description="Authority city"
    )
    authority_country: str = Field(
        ..., validation_alias="authorityCountry", description="Authority country code"
    )
    cpv_codes: list[str] = Field(
        default_factory=list, validation_alias="cpvCodes", description="CPV classification codes"
    )
    lots: list[dict] = Field(default_factory=list, description="Raw lot data from API")
    change_reason_code: str | None = Field(
        None,
        validation_alias="changeReasonCode",
        description="Code for deadline change reason at notice level",
    )
    change_reason: str | None = Field(
        None,
        validation_alias="changeReason",
        description="Human-readable deadline change reason at notice level",
    )
    notice_identifier: str | None = Field(
        None, validation_alias="noticeIdentifier", description="TED notice UUID identifier"
    )
    notice_version: str | int | None = Field(
        None, validation_alias="noticeVersion", description="TED notice version (2-digit)"
    )
    publication_number: str | None = Field(
        None, validation_alias="publicationNumber", description="TED publication number"
    )
    procedure_identifier: str | None = Field(
        None, validation_alias="procedureIdentifier", description="Shared procedure identifier"
    )
    change_notice_version_identifier: str | None = Field(
        None,
        validation_alias="changeNoticeVersionIdentifier",
        description="Pointer to predecessor notice (UUID+version or publication number)",
    )
    url: str | None = Field(None, description="Link to full notice on TED")


class Notice(BaseModel):
    """Internal normalized notice representation."""

    model_config = ConfigDict(extra="allow")

    notice_id: str = Field(..., description="Unique notice identifier (TED ID)")
    title: str = Field(..., description="Notice title")
    notice_type: str = Field(..., description="Type of notice")
    publication_date: date = Field(..., description="Date notice was published")
    deadline: date | None = Field(None, description="Overall submission deadline")
    country: str = Field(..., description="Country code (ISO 3166-1 alpha-2)")
    authority_name: str = Field(..., description="Contracting authority name")
    authority_city: str | None = Field(None, description="Authority city")
    authority_country: str = Field(..., description="Authority country code")
    cpv_codes: list[str] = Field(default_factory=list, description="CPV classification codes")
    lots: list[LotDeadline] = Field(default_factory=list, description="Per-lot deadlines")
    change_reason_code: str | None = Field(
        None, description="Code for deadline change reason at notice level"
    )
    change_reason: str | None = Field(
        None, description="Human-readable deadline change reason at notice level"
    )
    notice_identifier: str | None = Field(None, description="TED notice UUID identifier")
    notice_version: str | int | None = Field(None, description="TED notice version (2-digit)")
    publication_number: str | None = Field(None, description="TED publication number")
    procedure_identifier: str | None = Field(None, description="Shared procedure identifier")
    change_notice_version_identifier: str | None = Field(
        None, description="Pointer to predecessor notice (UUID+version or publication number)"
    )
    url: str | None = Field(None, description="Link to full notice on TED")
    unknowns: list[dict[str, str]] = Field(
        default_factory=list,
        description="Unrecognised values observed while mapping ({kind, value})",
    )

"""Predecessor link resolution for TED notices."""

from .model import Notice


def _text(value: object) -> str | None:
    """Return a stripped string for ``value`` or ``None`` when empty."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _version_text(value: object) -> str | None:
    """Normalize a notice version to a zero-padded two-digit string."""
    text = _text(value)
    if text is None:
        return None
    if text.isdigit():
        return text.zfill(2)
    return text


def _pointer(notice: Notice) -> str | None:
    """Extract the predecessor pointer from a notice, if any."""
    return _text(getattr(notice, "change_notice_version_identifier", None))


def _candidate_keys(notice: Notice) -> set[str]:
    """Build the set of identifiers under which ``notice`` may be found."""
    keys: set[str] = set()

    notice_id = _text(getattr(notice, "notice_id", None))
    if notice_id is not None:
        keys.add(notice_id)

    publication_number = _text(getattr(notice, "publication_number", None))
    if publication_number is not None:
        keys.add(publication_number)

    uuid = _text(getattr(notice, "notice_identifier", None))
    version_raw = _text(getattr(notice, "notice_version", None))
    version_padded = _version_text(getattr(notice, "notice_version", None))
    if uuid is not None:
        if version_padded is not None:
            keys.add(f"{uuid}-{version_padded}")
        if version_raw is not None:
            keys.add(f"{uuid}-{version_raw}")

    return keys


def _pointer_variants(pointer: str) -> set[str]:
    """Expand a pointer into the forms it may appear under in an index."""
    variants: set[str] = {pointer}
    if "-" in pointer:
        head, _, tail = pointer.rpartition("-")
        if tail.isdigit() and head:
            variants.add(f"{head}-{tail.zfill(2)}")
            variants.add(f"{head}-{int(tail)}")
    return variants


def resolve_predecessor(notice: Notice, index: dict[str, Notice]) -> Notice | None:
    """Resolve the predecessor notice referenced by ``notice`` using ``index``.

    ``index`` maps arbitrary string keys to :class:`Notice` instances. The
    predecessor pointer may take either supported form (UUID+version or
    publication number); both are handled. Returns ``None`` when the pointer
    resolves to nothing.
    """
    pointer = _pointer(notice)
    if pointer is None:
        return None

    variants = _pointer_variants(pointer)

    for variant in variants:
        if variant in index:
            return index[variant]

    for candidate in index.values():
        if _candidate_keys(candidate) & variants:
            return candidate

    return None

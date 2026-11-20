"""On-disk predecessor lookup for pointers outside the fetched window."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .link import _candidate_keys, _pointer, _pointer_variants, resolve_predecessor
from .model import Notice

_MISSING = object()

Fetch = Callable[[str], Notice | None]


class Unresolved:
    """Explicit unresolved predecessor.

    ``status`` is ``unknown``. The pointing notice's deadline is never copied
    here and no deadline is guessed.
    """

    status = "unknown"

    def __init__(self, ref: str) -> None:
        self.ref = ref
        self.resolved = False

    @property
    def deadline(self) -> None:
        """Always ``None``; an unresolved pointer has no deadline."""
        return None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Unresolved):
            return False
        return self.ref == other.ref

    def __repr__(self) -> str:
        return f"Unresolved({self.ref!r}, status={self.status!r})"


class PredecessorCache:
    """Resolve a predecessor ref with an injected fetch and a JSON cache.

    ``fetch`` is called as ``fetch(ref) -> Notice | None``. This module does
    not open a network connection. The cache file is a JSON object
    ``{pointer: notice | null}`` and is written only after a lookup, never on
    import or construction. Resolved notices and not-found results are both
    stored, so a later lookup of the same ref does not call ``fetch``.
    """

    def __init__(
        self,
        fetch: Fetch,
        cache_path: str | Path,
        *,
        index: dict[str, Notice] | None = None,
    ) -> None:
        self._fetch = fetch
        self._cache_path = Path(cache_path)
        self._index = index
        self._entries: dict[str, Notice | None] | None = None

    def lookup(self, ref: str | Notice) -> Notice | Unresolved:
        """Resolve ``ref`` in either pointer form.

        UUID+version and publication-number pointers are both accepted. Returns
        the predecessor :class:`Notice`, or an :class:`Unresolved` result when
        nothing resolves.
        """
        return self._resolve(ref, self._index)

    def resolve(
        self,
        ref: str | Notice,
        index: dict[str, Notice] | None = None,
    ) -> Notice | Unresolved:
        """Resolve ``ref``, using ``index`` before fetch when the predecessor is in window."""
        window = self._index if index is None else index
        return self._resolve(ref, window)

    def _resolve(
        self,
        ref: str | Notice,
        index: dict[str, Notice] | None,
    ) -> Notice | Unresolved:
        pointer = _as_pointer(ref)
        if pointer is None:
            return Unresolved("")

        cached = self._cached(pointer)
        if cached is not _MISSING:
            if cached is None:
                return Unresolved(pointer)
            return cached

        found = _from_index(ref, pointer, index)
        if found is None:
            found = _coerce(self._fetch(pointer))
        self._store(pointer, found)
        if found is None:
            return Unresolved(pointer)
        return found

    def _cached(self, pointer: str) -> Notice | None | object:
        """Return a cached notice, ``None`` for a known miss, or ``_MISSING``."""
        entries = self._load()
        if pointer in entries:
            return entries[pointer]
        for variant in _pointer_variants(pointer):
            if variant in entries and entries[variant] is not None:
                return entries[variant]
        return _MISSING

    def _load(self) -> dict[str, Notice | None]:
        """Load the cache file on first use. Missing file means an empty cache."""
        if self._entries is not None:
            return self._entries
        path = self._cache_path
        if not path.exists():
            self._entries = {}
            return self._entries
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"predecessor cache must be a mapping: {path}")
        entries: dict[str, Notice | None] = {}
        for key, value in data.items():
            if value is None:
                entries[str(key)] = None
            elif isinstance(value, dict):
                entries[str(key)] = Notice.model_validate(value)
            else:
                raise ValueError(f"invalid cache entry: {key}")
        self._entries = entries
        return entries

    def _store(self, pointer: str, notice: Notice | None) -> None:
        """Remember ``pointer`` and write the JSON cache atomically."""
        entries = self._load()
        entries[pointer] = notice
        payload: dict[str, Any] = {}
        for key, value in entries.items():
            if value is None:
                payload[key] = None
            else:
                payload[key] = value.model_dump(mode="json")
        path = self._cache_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)


def _as_pointer(ref: str | Notice) -> str | None:
    """Return the predecessor pointer carried by ``ref``."""
    if isinstance(ref, Notice):
        return _pointer(ref)
    text = str(ref).strip()
    return text or None


def _from_index(
    ref: str | Notice,
    pointer: str,
    index: dict[str, Notice] | None,
) -> Notice | None:
    """Resolve ``pointer`` from an in-memory window, if it is present."""
    if not index:
        return None
    if isinstance(ref, Notice):
        return resolve_predecessor(ref, index)
    variants = _pointer_variants(pointer)
    for variant in variants:
        if variant in index:
            return index[variant]
    for candidate in index.values():
        if _candidate_keys(candidate) & variants:
            return candidate
    return None


def _coerce(value: Any) -> Notice | None:
    """Normalize a fetch result to a :class:`Notice` or ``None``."""
    if value is None:
        return None
    if isinstance(value, Notice):
        return value
    if isinstance(value, dict):
        return Notice.model_validate(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json")
        if isinstance(dumped, dict):
            return Notice.model_validate(dumped)
    return None

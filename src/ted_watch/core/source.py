"""Load connector source metadata from a source.yaml file."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from .model import Source

_MISSING = object()


def _model_type(annotation: Any) -> type[BaseModel] | None:
    """Return ``annotation`` when it is a pydantic model class."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    return None


def _required_paths(model: type[BaseModel], prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    """Collect dotted paths of required fields, including nested models."""
    paths: list[tuple[str, ...]] = []
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue
        path = prefix + (name,)
        paths.append(path)
        nested = _model_type(field.annotation)
        if nested is not None:
            paths.extend(_required_paths(nested, path))
    return paths


def _lookup(data: Any, path: tuple[str, ...]) -> Any:
    """Return the value at ``path``, or a sentinel when any step is missing."""
    cursor = data
    for part in path:
        if not isinstance(cursor, dict) or part not in cursor or cursor[part] is None:
            return _MISSING
        cursor = cursor[part]
    return cursor


def _missing_keys(data: dict[str, Any], model: type[BaseModel] = Source) -> list[str]:
    """Return required key paths that are absent or null."""
    missing: list[str] = []
    for path in _required_paths(model):
        if _lookup(data, path) is _MISSING:
            label = ".".join(path)
            if label not in missing:
                missing.append(label)
    return missing


def load_source(path: str | Path) -> Source:
    """Load ``path`` and return a typed :class:`Source`.

    Raises ``ValueError`` when the file is not a mapping or required keys
    are missing. Parsing uses a safe YAML loader and does not touch the network.
    """
    source_path = Path(path)
    try:
        data = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid source yaml: {source_path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"source file must be a mapping: {source_path}")
    missing = _missing_keys(data)
    if missing:
        raise ValueError(f"missing keys: {', '.join(missing)}")
    return Source.model_validate(data)

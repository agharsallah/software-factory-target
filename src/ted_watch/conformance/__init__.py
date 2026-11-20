"""Conformance checking for tender data.

The runner loads a visible or holdout fixture directory given by ``--fixtures``
and validates every emitted event against ``core/event.schema.json``.
"""

from .runner import load_schema, main, run, validate_event, validate_events

__all__ = [
    "load_schema",
    "main",
    "run",
    "validate_event",
    "validate_events",
]

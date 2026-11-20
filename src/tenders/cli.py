"""CLI entry point for tenders."""

try:
    from ted_watch.cli import *  # noqa: F401,F403
    from ted_watch.cli import main
except ImportError:  # pragma: no cover
    from src.ted_watch.cli import *  # noqa: F401,F403
    from src.ted_watch.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

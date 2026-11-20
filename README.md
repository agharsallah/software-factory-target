# ted-watch

EU tender deadline-change watch on TED (ted.europa.eu).

## Status

This project is **unofficial** and **not affiliated** with TED or the European Union.
No TED or EU logos are used.

**Attribution:** TED (ted.europa.eu)
**Coverage:** EU tenders

## Usage

Run tests:
```bash
uv run pytest -q
```

Run linter:
```bash
uv run ruff check .
```

Run formatter check:
```bash
uv run ruff format --check .
```

Run the CLI in fixture mode (offline, no network calls):
```bash
uv run python -m src.ted_watch.cli --fixtures fixtures/connectors/ted_api/fixtures --out sample.jsonl
```

The CLI reads JSON fixtures from `fixtures/connectors/ted_api/fixtures/`, maps them through the pure `map_raw_to_notice` function, diffs per-lot deadlines, and writes deadline-change events as JSONL to the output file.

Run the conformance runner against either split (offline, no network calls):
```bash
uv run python -m src.ted_watch.conformance --fixtures fixtures/visible
uv run python -m src.ted_watch.conformance --fixtures fixtures/holdout
```

`fixtures/visible/` and `fixtures/holdout/` group notices by procedure-identifier. A change and its predecessor stay on the same side, and each §3.4 case tag appears in both sets. The flat connector fixtures remain usable.

## §3.4 Conformance cases

The link resolution (`resolve_predecessor`) handles both pointer forms used by TED:

1. **Form A — UUID + 2-digit version** (e.g. `e6f24cac-1111-2222-3333-444444444444-01`)
2. **Form A — index keyed by components** (UUID + version without zero-padding, e.g. `...-1`)
3. **Form B — publication number** (e.g. `719096-2026`)
4. **Form B — index scan** (resolves via candidate keys when not directly indexed)
5. **Missing predecessor** (pointer exists but target not in index → returns `None`)
6. **No pointer** (no `change-notice-version-identifier` → returns `None`)
7. **Change-of-change chain** (A→B→C resolution via chained pointers)

## Rate budget

Polite access budget for live TED queries (not used in tests/fixtures):
- **1 request / second**
- **30 requests / minute**

All tests run offline from fixtures; no network calls are made during `uv run pytest -q`.
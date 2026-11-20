# ted-watch

EU tender deadline-change watch on TED (ted.europa.eu).

It turns TED notices into deadline-change events: map a raw notice, resolve its predecessor pointer, and emit one event per logical change. Today that path runs offline from JSON fixtures. There is no live TED client.

This project is **unofficial** and **not affiliated** with TED or the European Union.
No TED or EU logos are used.

**Attribution:** TED (ted.europa.eu). `connectors/ted_api/source.yaml` records `Source: TED (ted.europa.eu), © European Union`. The CLI still writes the shorter string `TED (ted.europa.eu)`.
**Coverage:** EU tenders

## Status

### What works today

- `core/model.py` — `RawNotice`, `Notice`, `LotDeadline`, and the `Source` descriptor (budget, branding, reuse, paging, personal-data fields).
- `core/map.py` — pure `map_raw_to_notice`. No network, no side effects.
- `core/link.py` — `resolve_predecessor` for both TED pointer forms (UUID+version and publication number), one hop per call.
- `core/dedupe.py` — stable `event_id` and an exactly-once `Dedupe` store. Identity is procedure, lot, kind, previous notice, current notice. Deadlines are not part of the id.
- `core/source.py` — `load_source` reads `connectors/ted_api/source.yaml` with a safe YAML loader and rejects missing required keys.
- `cli.py` — fixture mode: load JSON, map, filter, write deadline-change JSONL. `previous` is always null. It does not call link, dedupe, or `load_source`.
- `tenders/` — thin entry that calls the same CLI.

### What is next

Named by the pipeline and by `source.yaml`, and not in the tree yet:

- **list** and **fetch** of the TED search API. `source.yaml` records the endpoint, iteration-token paging, and the polite budget. No HTTP client exists.
- **diff** of a linked predecessor deadline against the current notice. The CLI emits an event when a change-reason code is set; it does not compare two deadlines.
- Calling link resolution and dedupe from the event path.
- A conformance kit under `conformance/`. That package is a docstring only.

## Quickstart

From the repository root. These commands do not call TED.

```bash
uv run pytest -q
```

```bash
uv run ruff check .
```

```bash
uv run ruff format --check .
```

Write a sample of deadline changes from the offline fixtures:

```bash
uv run python -m ted_watch.cli --fixtures fixtures/connectors/ted_api/fixtures --out sample.jsonl
```

The same program is `uv run python -m tenders.cli`. `--out` is required. Omitting `--fixtures` uses `fixtures/connectors/ted_api/fixtures`. Optional filters: `--cpv-division`, `--country` (repeatable), `--since`, `--until`. A date of `D` means no bound.

## Module map

Every top-level module under `src/`. Nothing else is a product module.

- `ted_watch/` — EU tender deadline-change watch package (`__version__` 0.1.0).
- `connectors/` — connectors package for external API integrations. The only connector is `connectors/ted_api/` (source metadata in `source.yaml`; no fetch code).
- `core/` — core domain logic for tender watching: `model.py`, `map.py`, `link.py`, `source.py`, `dedupe.py`.
- `conformance/` — conformance checking for tender data. Docstring only; no cases and no checker.
- CLI — `ted_watch/cli.py` writes a sample of deadline changes as JSONL. `tenders/` re-exports that entry point.

See [docs/architecture.md](docs/architecture.md) for the deadline-change data flow.

## Tests

```bash
uv run pytest -q
```

Tests live under `tests/` and are parametrized over JSON fixtures in `fixtures/connectors/ted_api/fixtures/`. No live TED calls. `uv run pytest -q` does not exercise the CLI.

## Insights

Factory metrics for the last 30 days, as of 2026-11-20T17:37 UTC.

| Metric | Value |
| --- | --- |
| prs_merged | 9 |
| pr_lead_time_h | 0.01 |
| merge_rate | 1.0 |
| ci_success_rate | 1.0 |
| change_failure_rate | 0.0 |
| stories_open | 22 |
| stories_closed | 9 |
| story_cycle_h | 0.34 |
| automation_share | 1.0 |
| spend_today_usd | 82.4295 |

Run the conformance runner against either split (offline, no network calls):
```bash
uv run python -m src.ted_watch.conformance --fixtures fixtures/visible
uv run python -m src.ted_watch.conformance --fixtures fixtures/holdout
```

`fixtures/visible/` and `fixtures/holdout/` group notices by procedure-identifier. A change and its predecessor stay on the same side, and each §3.4 case tag appears in both sets. The flat connector fixtures remain usable.

## §3.4 Conformance cases

`resolve_predecessor` handles both pointer forms. All seven cases are covered by `tests/core/test_link.py`. They are not implemented inside `conformance/`.

1. **Form A — UUID + 2-digit version** (e.g. `e6f24cac-1111-2222-3333-444444444444-01`) — covered (`test_form_a_uuid_version`)
2. **Form A — index keyed by components** (UUID + version without zero-padding, e.g. `...-1`) — covered (`test_form_a_index_keyed_by_components`)
3. **Form B — publication number** (e.g. `719096-2026`) — covered (`test_form_b_publication_number`)
4. **Form B — index scan** (resolves via candidate keys when not directly indexed) — covered (`test_form_b_index_scan`)
5. **Missing predecessor** (pointer exists but target not in index → returns `None`) — covered (`test_missing_predecessor`)
6. **No pointer** (no `change-notice-version-identifier` → returns `None`) — covered (`test_no_pointer`)
7. **Change-of-change chain** (A→B→C, one hop per call) — covered (`test_change_of_change_chain`)

## Rate budget

Polite access budget in `connectors/ted_api/source.yaml`. Not used by tests or the CLI.

- **1 request / second** (`min_gap_ms: 1000`)
- **30 requests / minute**

All tests run offline from fixtures; no network calls are made during `uv run pytest -q`.

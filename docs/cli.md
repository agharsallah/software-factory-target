# CLI

Command-line interface for writing a sample of deadline changes as JSONL.

Two entry points, one program:

- `ted_watch/cli.py` — `main`, argument parser, fixture load, filters, `_build_events`.
- `tenders/` — tenders CLI package. `tenders/cli.py` imports `main` from `ted_watch.cli` and exits with its status. `prog` is `tenders.cli`.

## Run

From the repository root. No network.

```bash
uv run python -m ted_watch.cli --fixtures fixtures/connectors/ted_api/fixtures --out sample.jsonl
```

```bash
uv run python -m tenders.cli --cpv-division 72 --country DE --since 2024-01-01 --until 2024-12-31 --out sample.jsonl
```

`--out` is required. `--fixtures` defaults to `fixtures/connectors/ted_api/fixtures` (resolved from the `cli.py` file location, two parents up). `--country` may be repeated. `--since` and `--until` take `YYYY-MM-DD`; `D` or empty means no bound.

## What it does

1. Read `*.json` from the fixtures path (or one JSON file). Invalid JSON and objects that are not a `RawNotice` are skipped.
2. `map_raw_to_notice` on each object. This is the **map** stage. There is no **list** or **fetch**.
3. Keep notices whose CPV codes start with `--cpv-division`, whose country matches, and whose `publication_date` is inside the date window. ISO3 country codes in a fixed table are folded to ISO2 before the compare.
4. `_build_events` — the stand-in for **diff**. A row is written when a change-reason code is set and not `none`, and a deadline is present. Lot reason wins over the notice reason. `previous` is always `null`. No predecessor is loaded, so **link** is not on this path.
5. Write JSONL. Event name is `suspension` if the reason contains `susp`, `cancellation` if it contains `cancel`, otherwise `deadline_change`. `current_utc` is the date plus `T00:00:00Z`. `coverage` is `EU tenders`. `attribution` is `TED (ted.europa.eu)`, not the longer string in `source.yaml`.

`load_source` and `Dedupe` are not called. Pytest does not import this module; the skeleton test does not run it.

Personal-data field names listed in `source.yaml` are not stripped here, because the CLI never reads that file. The fixture JSON does not carry those fields.

# Pilot runbook

Owner decisions, sample procedure and analyst-test steps for the TED deadline-change pilot.

Capture (live TED pull) and the summary report are **not built yet**. Those steps are marked pending below. Only the fixture run works today.

## 1. Owner decisions

Fill every field before the live run. Do not start without them.

| Decision | Value | Notes |
| --- | --- | --- |
| CPV division | `__` | 2 digits. Used as `--cpv-division`. Matches the start of each CPV code. |
| Buyer country 1 | `__` | ISO2 preferred, used as `--country`. |
| Buyer country 2 (optional) | `__` | Repeat `--country`. Matches notice country or authority country. |
| Approved field list | `__` | Subset of event keys: `event`, `kind`, `lot`, `previous`, `current`, `current_utc`, `source`, `coverage`, `attribution`. |
| Retention period | `__` | How long sample files and any cache are kept. |
| Request budget confirmation | `__` | Confirm `access.our_budget.requests_per_minute` and `min_gap_ms` in `src/ted_watch/connectors/ted_api/source.yaml`, or write new values. |

Rules that hold whatever the owner picks:

- No personal data. The names in `personal_data_fields` in `source.yaml` are never in the approved list.
- `--country` folds ISO3 only for codes in `ISO3_TO_ISO2` in `cli.py`. Any other 3-letter code is cut to its first two characters and can silently mismatch. Use ISO2.
- `--since` and `--until` filter on `publication_date`, not on the deadline.

Brief §8 and §12 and the three existing monitors are not in this repo. Their values stay blank here until the owner supplies them.

## 2. Sample procedure

All commands run from the repository root.

### Check the tree

```bash
uv run pytest -q
```

Expected: all tests pass. Pytest does not run the CLI.

### Capture

NOT AVAILABLE. The allowlisted capture script (#43) and the fetch layer with checkpoint (#42) are not built. `docs/architecture.md` states there is no HTTP client, no rate limiter and no sockets. Do not run a live pull until these land. Add the exact command here when they do.

### Sample run

Fixture input only, no network.

```bash
uv run python -m ted_watch.cli --fixtures fixtures/connectors/ted_api/fixtures --cpv-division <DIV> --country <CC> --since <YYYY-MM-DD> --until <YYYY-MM-DD> --out <path>
```

Expected:

- Exit code 0 and nothing on stdout.
- `<path>` holds JSONL, one event per line, with keys in the order of `sample.jsonl`: `event`, `kind`, `lot`, `previous`, `current`, `current_utc`, `source`, `coverage`, `attribution`.
- `previous` is always `null` on this path. `current_utc` is the date plus `T00:00:00Z`, not a TED value.
- `attribution` is `TED (ted.europa.eu)`. The longer string in `source.yaml` is not written by the CLI.

`sample.jsonl` at the repo root is derived from fixtures. It is not pilot data.

### Summary report

NOT BUILT (#36 open). Manual fallback:

```bash
wc -l <path>
head -n 1 <path>
```

Expected: the event count, then the first event as one JSON line in the shape above. Record both in section 4.

## 3. Expected outputs

| Step | Exit | Output |
| --- | --- | --- |
| `uv run pytest -q` | 0 | Pass line from pytest |
| Sample run | 0 | No stdout; JSONL at `--out` |
| `wc -l` | 0 | `<count> <path>` |
| `head -n 1` | 0 | First event as JSON |

## 4. Analyst-test comparison

Run the same window for every method. Write the window here: `__` to `__`.

1. Current method: `__` (describe how the analyst finds deadline changes today).
2. Minutes: `__` per week with the current method. Minutes for the sample run: `__`.
3. Missed changes: count `__`, notice ids `__`. A miss is a change in the window that one method reported and the other did not.
4. Existing monitors on the same window. The three monitors are not in this repo.

| Monitor | Window | Events found | Missed vs sample |
| --- | --- | --- | --- |
| `__` | `__` | `__` | `__` |
| `__` | `__` | `__` | `__` |
| `__` | `__` | `__` | `__` |

5. Compare: list notice ids from the sample (`source` field) against each monitor's list. Note differences in section 4, row 3.

## 5. Known gaps

- #43 capture script, #42 last-run checkpoint, #36 summary report, #56 429 back-off and request counter, #66 unresolved-predecessor report. These gate the live pilot.
- The CLI does not set `previous`, so the old deadline is not in the sample.
- Pytest does not exercise the CLI.

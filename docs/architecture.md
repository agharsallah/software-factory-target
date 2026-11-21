# Architecture and data flow

ted-watch watches EU tender notices on TED for deadline changes. The pipeline for one change is:

```text
list → fetch → map → link → diff → event
```

Only some of those stages exist as code. The rest are the shape of the pipeline, recorded here so a reader can see what is missing. No stage calls the network today.

## Stages

### list

Not implemented. `connectors/ted_api/source.yaml` says paging is `iteration-token` and the token field is `iterationNextToken`. There is no list client and no code that reads that token.

### fetch

Not implemented. The same file records the search endpoint `https://api.ted.europa.eu/v3/notices/search` and `access.our_budget` (30 requests/minute, 1000 ms gap). A comment says fetch would use that budget. No HTTP client, no rate limiter, and no notice downloader exist. Tests and the CLI never open a socket.

The offline stand-in is a directory of JSON fixtures at `fixtures/connectors/ted_api/fixtures/`. The CLI reads those files instead of listing or fetching.

### map

Implemented in `core/map.py`. `map_raw_to_notice` takes a `RawNotice` (pydantic, `extra=allow`, TED search API v3 field aliases) and returns a `Notice`. It parses lot deadlines from `id` / `lotId` / `lot_id` and `deadline` / `submissionDeadline`, and copies change-reason and predecessor-pointer fields. Lots with no id or no deadline are dropped. Pure: no I/O, same input yields an equal but not identical `Notice`.

### link

Implemented in `core/link.py`, not called by the CLI. `resolve_predecessor(notice, index)` reads `change_notice_version_identifier` and looks it up in a `dict[str, Notice]`.

Two pointer forms:

- Form A: UUID plus version (`e6f24cac-1111-2222-3333-444444444444-01`). A trailing numeric version is also tried zero-padded and unpadded.
- Form B: publication number (`719096-2026`).

Lookup is direct, then a scan of candidate keys on each indexed notice (`notice_id`, `publication_number`, `notice_identifier` plus version). No pointer, or a pointer that misses, returns `None`. One hop per call. A change-of-change chain is walked by calling it again on the predecessor.

### diff

Implemented in `core/diff.py`. `diff_notices(previous, current)` reads the change-reason code on the current notice and on its lots.

- `susp-review` yields one `procedure_suspended` event.
- `cancel-intent` yields one `cancellation_intended` event.

Those events are never `deadline_changed`, even when the deadline moved. Each carries `notice` (the notice id), `source` (the notice URL), `coverage` and `attribution`, plus dedupe identity (`kind`, `procedure`, `previous_notice`, `current_notice`). Personal-data fields are not copied. Coverage and attribution default to the strings in `connectors/ted_api/source.yaml`. Other reason codes yield nothing; a deadline-to-deadline compare is not emitted yet.

The CLI calls `diff_notices` for those two codes and does not attach deadline fields. Other codes still go through `_build_events` as `deadline_change` rows. `previous` on those rows is still `null`. The CLI does not call `resolve_predecessor`.

### event

The CLI writes one JSON object per line. Deadline rows use `event`, `kind`, `lot`, `previous`, `current`, `current_utc` (`YYYY-MM-DDT00:00:00Z`), `source` (notice URL, or `ted.europa.eu`), `coverage` (`EU tenders`), `attribution` (`TED (ted.europa.eu)`). The CLI hardcodes coverage and attribution; it does not read `source.yaml`.

Procedure events (`procedure_suspended`, `cancellation_intended`) come from `diff_notices`. They carry `notice`, `source`, `coverage` and `attribution`, and no deadline fields. The CLI passes its shorter attribution string into that call.

`core/dedupe.py` can stamp a stable id and drop repeats. `event_id` is SHA-256 over procedure, lot, kind, previous notice, and current notice, in that order. Deadline strings are not part of the id. `Dedupe` remembers ids already emitted and yields each logical change once, in any order. The CLI does not call it. Procedure events include `procedure`, `kind` and `current_notice`, so they are dedupe-ready. Deadline rows still omit those fields.

## What the CLI runs today

```text
fixtures → map_raw_to_notice → filter → _build_events → JSONL
```

Filters, all optional: CPV division is a prefix of `cpv_codes`; country is matched against `country` and `authority_country` (a fixed ISO3→ISO2 map); `--since` / `--until` bound `publication_date`.

## Modules

| Path | Role in the flow |
| --- | --- |
| `connectors/` | Source metadata for a future list/fetch. No client. |
| `core/` | Models, map, link, diff, source loader, dedupe. |
| `conformance/` | Empty package. Cases live in `tests/core/test_link.py`. |
| CLI (`ted_watch/cli.py`, `tenders/`) | Fixture load, map, filter, JSONL. Skips link and dedupe. |

Pages: [connectors](connectors.md), [core](core.md), [conformance](conformance.md), [cli](cli.md).

## Conformance cases

The seven link cases below are what the README calls §3.4. Each is covered by a test in `tests/core/test_link.py`. `conformance/` does not contain them.

| Case | Covered | Test |
| --- | --- | --- |
| Form A — UUID + 2-digit version | yes | `test_form_a_uuid_version` |
| Form A — index keyed by components (unpadded version) | yes | `test_form_a_index_keyed_by_components` |
| Form B — publication number | yes | `test_form_b_publication_number` |
| Form B — index scan via candidate keys | yes | `test_form_b_index_scan` |
| Missing predecessor (pointer set, target absent) → `None` | yes | `test_missing_predecessor` |
| No pointer → `None` | yes | `test_no_pointer` |
| Change-of-change chain, one hop per call | yes | `test_change_of_change_chain` |

Other offline checks, not part of that list:

- Map fixtures in `tests/core/test_map.py`: `notice_contract_with_lots.json`, `notice_planning_without_lots.json`, `notice_contract_change_reason.json`, `notice_contract_alternate_fields.json`. The two `notice_contract_cpv72_*.json` files are CLI inputs only; map tests do not parametrize over them.
- `tests/core/test_source.py` loads `connectors/ted_api/source.yaml` and rejects missing required keys.
- `tests/core/test_dedupe.py` checks id stability, order independence, and exactly-once emit.
- `tests/core/test_diff.py` checks `susp-review` and `cancel-intent` fixtures under `fixtures/visible/`.

Property tests for map and diff live in `conformance/properties.py` (Hypothesis, bounded `max_examples`). Events are checked by `validate_event` there; the other event schema is the `Event` TypedDict in `dedupe.py`.

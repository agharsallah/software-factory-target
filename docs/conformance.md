# conformance/

Conformance runner for the visible and holdout fixture sets.

- `runner.py` — `main(argv)` takes `--fixtures` (a JSON file, a flat directory, or a directory grouped by procedure). `run` fails if the path is missing, no notices are found, any notice does not map, or a procedure directory holds notices with a different `procedureIdentifier`. Otherwise it prints the notice count, procedure count and case tags. Helpers: `notice_records`, `case_tags`, `procedure_identifiers`, `load_notices`. `SECTION_3_4_CASE_TAGS` lists the seven tags.
- `__main__.py` — `python -m ted_watch.conformance`.
- `__init__.py` — package docstring.

```bash
uv run python -m ted_watch.conformance --fixtures fixtures/visible
uv run python -m ted_watch.conformance --fixtures fixtures/holdout
```

The runner does not resolve links or compare events. It is exercised by `tests/test_conformance.py`.

## Fixture split

Notices are split by procedure so a change and its predecessor stay on the same side. `fixtures/visible/` has 12 procedure directories (20 notices) and `fixtures/holdout/` has 10 (16 notices). Running the runner reports all seven §3.4 tags present in both.

## Cases

The seven §3.4 link cases are resolved by `resolve_predecessor` and tested in `tests/core/test_link.py`:

| Case | Tag | Covered | Test |
| --- | --- | --- | --- |
| Form A — UUID + 2-digit version | `form_a_uuid_version` | yes | `test_form_a_uuid_version` |
| Form A — index keyed by components | `form_a_index_keyed_by_components` | yes | `test_form_a_index_keyed_by_components` |
| Form B — publication number | `form_b_publication_number` | yes | `test_form_b_publication_number` |
| Form B — index scan | `form_b_index_scan` | yes | `test_form_b_index_scan` |
| Missing predecessor → `None` | `missing_predecessor` | yes | `test_missing_predecessor` |
| No pointer → `None` | `no_pointer` | yes | `test_no_pointer` |
| Change-of-change chain | `change_of_change_chain` | yes | `test_change_of_change_chain` |

Fixture directories: `vis-*` and `hold-*` for each case (for example `hold-form-b-scan`, `hold-change-chain`), plus `hold-copied-*` and `vis-copied-*` copies of the connector fixtures, and `vis-susp-review` and `vis-cancel-intent` for diff.

The runner also replays every procedure through `core.pipeline` in original, reversed, seeded-shuffled (seeds 0, 1, 7, 42) and doubled delivery order, and requires the same event ids with no duplicates (`conformance/replay.py`).

Not covered: property tests and an event-schema check beyond the `Event` TypedDict.

# conformance/

Conformance checking for tender data.

`conformance/coverage.py` holds the twelve-case §3.4 list (`SECTION_3_4_CASES`). `fixtures/cases.yaml` maps each procedure directory to its case tags. `tests/test_conformance.py` fails naming any case missing from the visible or the holdout side, and checks the manifest against the `caseTags` in the fixtures. The date-without-time, offset-differs, and delivery-order fixtures are synthetic and raw-only: the model carries a date, not a time or offset.

The cases that exist today are link-resolution cases in `tests/core/test_link.py`, documented as §3.4 in the README and in [architecture](architecture.md). All seven are covered there:

| Case | Covered | Test |
| --- | --- | --- |
| Form A — UUID + 2-digit version | yes | `test_form_a_uuid_version` |
| Form A — index keyed by components | yes | `test_form_a_index_keyed_by_components` |
| Form B — publication number | yes | `test_form_b_publication_number` |
| Form B — index scan | yes | `test_form_b_index_scan` |
| Missing predecessor → `None` | yes | `test_missing_predecessor` |
| No pointer → `None` | yes | `test_no_pointer` |
| Change-of-change chain (one hop per call) | yes | `test_change_of_change_chain` |

Map, source-loader, and dedupe checks live under `tests/core/` as well. They are not conformance-package cases.

Not covered anywhere: a conformance runner, property tests, and an event-schema check beyond the `Event` TypedDict.

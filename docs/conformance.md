# conformance/

Conformance checking for tender data.

The package is `conformance/__init__.py` and a one-line docstring. No checker, no case list, no fixtures, and no tests import it.

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

## Property checks

`src/ted_watch/conformance/properties.py` mutates the `fixtures/connectors/ted_api/fixtures/` notices with Hypothesis (drops optional fields, shuffles lots, truncates date strings). Map must never raise on input `RawNotice` accepts. Every `diff_notices` event is checked by `validate_event` (required keys, non-empty strings); a failing event is reported as unresolved. `run_properties(max_examples=25)` is the bounded kit entry point; tests are in `tests/test_conformance_hypothesis.py`.

Not covered anywhere: a full JSON-schema check beyond `validate_event` and the `Event` TypedDict.

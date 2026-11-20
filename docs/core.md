# core/

Core domain logic for tender watching. Pure functions and pydantic models. No network and no CLI I/O.

## model.py

Core domain models for TED notice processing.

- `LotDeadline` — lot id, deadline, optional change-reason code and text.
- `RawNotice` — raw TED search API v3 notice. `extra=allow`. Camel-case aliases (`noticeId`, `publicationDate`, `changeNoticeVersionIdentifier`, and the rest).
- `Notice` — normalized notice. Same fields, snake_case, `extra=allow`. Lots are `LotDeadline` values.
- `Source` and the nested budget, access, reuse, branding, and paging models. `extra=allow`. This is the type `load_source` returns.

## map.py

Pure mapping from raw TED API data to internal models. `map_raw_to_notice(raw) -> Notice`. Copies notice fields, parses `YYYY-MM-DD` dates, and keeps lots that have both an id and a deadline. Alternate lot keys (`lotId`, `submissionDeadline`, `changeReasonCode`) are accepted. This is the **map** stage.

## link.py

Predecessor link resolution for TED notices. `resolve_predecessor(notice, index) -> Notice | None`. This is the **link** stage. See [architecture](architecture.md) for the two pointer forms and the seven covered cases. One hop per call. Not used by the CLI.

## diff.py

Pure diff of a predecessor notice against the current notice. `diff_notices(previous, current) -> list[Event]`. No I/O.

`susp-review` yields `procedure_suspended`. `cancel-intent` yields `cancellation_intended`. Those events are never `deadline_changed`, even when the deadline moved. Each carries `notice` (notice id), `source` (notice URL), `coverage` and `attribution`. Deadline values and personal-data fields are not copied. Coverage and attribution default to the strings in `connectors/ted_api/source.yaml`; callers may override them. Other reason codes yield nothing.

## source.py

Load connector source metadata from a `source.yaml` file. `load_source(path) -> Source`. Rejects a non-mapping file and any missing required key, including nested ones (`access.our_budget`). Does not fetch.

## dedupe.py

Stable event ids and exactly-once dedupe for deadline changes.

- `Event` — `TypedDict` for a CLI-shaped row plus logical-change identity fields. The only TypedDict in the package.
- `event_id` — SHA-256 hex of procedure, lot, kind, previous notice, current notice. Aliases cover CLI names (`previous` / `current`) and notice names (`previous_notice` / `current_notice`); explicit notice fields win when both are set. Deadline values are not hashed.
- `Dedupe` — remembers ids and emits each logical change once (`extend`, `emit`). Order and repeats do not matter.

Dedupe sits after **event** construction. The CLI does not call it.

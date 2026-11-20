# connectors/

Connectors package for external API integrations.

The only connector is `connectors/ted_api/`. Its docstring says source metadata lives in `source.yaml`. There is no list client, no fetch client, and no request code in this package.

## ted_api/source.yaml

Loaded by `core/source.py` (`load_source`), not by the CLI. Safe YAML load, no network. Missing required keys raise `ValueError`.

Required by the `Source` model:

- `id` — `ted_api`
- `attribution` — `Source: TED (ted.europa.eu), © European Union`
- `coverage` — `EU tenders`
- `reuse.terms`
- `branding.unofficial`, `branding.use_logos` (both set so this client stays unofficial and logo-free)
- `access.our_budget.requests_per_minute` — 30
- `access.our_budget.min_gap_ms` — 1000 (1 request/second)
- `paging.mode` — `iteration-token`
- `personal_data_fields` — names that must never be stored (`contact-name`, emails, phones, and the other keys in the file)

Extra keys the model allows and the file sets: `reuse.licence`, `reuse.attribution_required`, `branding.affiliated`, `branding.statement`, `access.endpoint` (`https://api.ted.europa.eu/v3/notices/search`), `paging.token_field` (`iterationNextToken`).

Those endpoint and paging fields describe a future list/fetch step. Nothing in the repo calls them.

Fixture JSON used in place of a fetch lives outside this package, at `fixtures/connectors/ted_api/fixtures/`.

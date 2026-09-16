# The `dirty_output/` folder

**Scope: what the error-injection pipeline writes to
`data/poc/dirty_output/<BATCH_DATE>/`** — the folder layout, and the format
of the two manifest files that record what the pipeline changed. It doesn't
cover the pipeline's internals (injectors, config, catalogue) — see
[injection-internals.md](injection-internals.md) for that.

## Layout

```
dirty_output/<BATCH_DATE>/
├── csv/                    18 CSVs, same filenames/columns as clean_input's csv/
├── manifest.jsonl          one JSON record per injected change
└── manifest_summary.json   aggregated counts over the same run
```

`<BATCH_DATE>` matches the `clean_input/<BATCH_DATE>/` batch the run was
generated from — a dirty batch is always traceable to the exact clean batch
it came from (`pipeline.py`). `csv/` holds the same 18 tables documented in
[../schema/](../schema/); only cell values, row counts, and referential
integrity differ from the clean input, per whatever injectors were enabled.

If `withhold_manifest = true` is set in `injection_config.toml`, the
manifest is written to `.manifest_withheld/manifest.jsonl` under the batch
folder instead of at the top level — same format, just hidden from casual
listing (e.g. for a blind-eval use case where the ground truth of what was
injected shouldn't be immediately visible alongside the data). The POC
dataset committed in this repo does **not** withhold its manifest.

## `manifest.jsonl`

One JSON object per line, one line per individual change the pipeline made.
Every record has `injector`, `tier`, `action`, and `table`; the remaining
fields depend on `action`. Keys are written alphabetically
(`json.dumps(..., sort_keys=True)`), not in the order below.

- **`injector`** — which injector made the change: one of `missing_values`,
  `typos`, `duplicates`, `formatting`, `type_mismatch`, `date_issues` (tier
  `row`), or `orphan_fk`, `key_format_drift`, `cardinality_break` (tier
  `join`).
- **`tier`** — `"row"` for row-level injectors, `"join"` for join-breaking
  injectors. Row-level injectors always run first, so a join-breaking
  injector can land on a row a row-level one already touched
  (`pipeline.py`).
- **`table`** — which of the 18 tables the change was made in.
- **`action`** — `"edit_cell"` or `"duplicate_row"`, determining which of
  the fields below are present.

### `action: "edit_cell"`

A single cell's value was changed.

- **`row_id`** — identifies the row. For 8 tables with a usable dedicated
  key column (`patients`, `organizations`, `providers`, `payers`,
  `encounters`, `careplans`, `claims`, `claims_transactions`; `Id`/`ID`),
  this is that key's value. For the other 10 tables — the 8 keyless
  clinical event logs, plus `imaging_studies` (whose `Id` isn't unique) and
  `payer_transitions` — it's the row's 0-based line index in the source CSV
  instead (`catalogue.py::KEYED_TABLES`/`KEYLESS_TABLES`,
  `manifest.py::row_id_for`). See [../schema/overview.md](../schema/overview.md)
  for why these particular tables lack a usable key.
- **`column`** — the column that was edited.
- **`original`** — the value before injection.
- **`new`** — the value after injection (e.g. `""` for a value the
  `missing_values` injector blanked out).

Example (from the committed POC manifest):

```json
{"action": "edit_cell", "column": "MARITAL", "injector": "missing_values", "new": "", "original": "M", "row_id": "d3cb6736-0991-40ed-a220-7c714aba4c37", "table": "patients", "tier": "row"}
```

### `action: "duplicate_row"`

The `duplicates` injector copied an existing row and appended it as a new
row.

- **`source_row_id`** — the row that was copied, identified the same way as
  `edit_cell`'s `row_id`.
- **`new_row_id`** — the identifier of the newly-appended duplicate row. For
  keyed tables this is often identical to `source_row_id` (the duplicate
  carries the same key value — a realistic exact-duplicate-row pattern, not
  a bug); for keyless tables it's the new row's own line index.

Example:

```json
{"action": "duplicate_row", "injector": "duplicates", "new_row_id": "7811dc30-8c86-8164-6c33-6b6f464745ef", "source_row_id": "7811dc30-8c86-8164-6c33-6b6f464745ef", "table": "patients", "tier": "row"}
```

## `manifest_summary.json`

A single JSON object aggregating the same run's manifest into counts —
nothing in it isn't derivable from `manifest.jsonl`, it's just pre-tallied
for a quick look without parsing the full JSONL file.

- **`total_changes`** — total number of manifest records (edits +
  duplications combined) across the whole run.
- **`by_injector`** — change count per injector name, summed across all
  tables.
- **`by_table`** — change count per table, summed across all injectors.
- **`detail`** — one `{"injector", "table", "count"}` object per
  injector/table pair that had at least one change — the finest-grained
  breakdown the summary provides (still coarser than `manifest.jsonl`,
  which has one entry per individual change, not per pair).

All three of `by_injector`, `by_table`, and `detail` are sorted by key for
stable diffs across regenerations.

# Error-injection pipeline internals

**Scope: how `src/dirty_data_factory/` actually works** — the module
responsibilities, the design decisions behind them, and how the pieces fit
together into a full run. For the *output* this pipeline produces (folder
layout, manifest format), see
[dirty-output-structure.md](dirty-output-structure.md); this doc covers what
generates that output. For the *input* schema it operates on, see
[../schema/](../schema/).

## Data flow

```
injection_config.toml → config.py → pipeline.py → row-level injectors → join-breaking injectors → csv_io.py + manifest.py
                                          ↑                    ↑
                                    catalogue.py         catalogue.py
```

`pipeline.run()` loads the clean CSVs, mutates them in place through a fixed
sequence of injectors, then writes the dirty CSVs and a manifest of every
change. Two decisions shape everything downstream of that:

1. **Config vs. catalogue is a deliberate split.** `injection_config.toml`
   (loaded by `config.py`) only holds knobs: which injectors are on, what
   rate they fire at. `catalogue.py` holds facts about the Synthea schema
   itself — which tables have keys, which FK edges exist, which columns are
   eligible targets for which injector. Config tunes behavior; catalogue
   defines what's structurally eligible. Mixing them would let a config
   change accidentally redefine the schema.
2. **Everything is deterministic from one seed, but injectors can't step on
   each other's randomness.** `seeding.py` derives an independent
   `random.Random` per injector from the run seed, so enabling/disabling one
   injector never changes another's draws.

## `config.py` — knobs

Parses `injection_config.toml` into a frozen `Config` dataclass. Each
injector gets an `InjectorConfig(enabled, rate, overrides)`; `rate_for(table,
column)` checks `overrides["table.column"]` first, falling back to the
injector's default `rate`. Validation is strict and fails fast: `run.seed` is
required, every rate must be a 0–1 float, and an unknown injector name in the
TOML (a typo) raises `ConfigError` rather than silently doing nothing.

## `catalogue.py` — facts

The schema knowledge base every injector reads from:

- **`KEYED_TABLES`** — `table → key column` for the 8 tables with a genuine
  unique ID (`patients`, `organizations`, `providers`, `payers`,
  `encounters`, `careplans`, `claims`, `claims_transactions`).
  `imaging_studies.Id` is deliberately excluded even though the column
  exists: one imaging study spans multiple series/instance rows, so `Id`
  isn't unique there and isn't a safe cardinality-break target.
- **`KEYLESS_TABLES`** — the 10 remaining tables, identified by 0-based line
  index instead, because their natural composite keys can legitimately
  repeat (e.g. multiple `observations` rows for the same
  patient/encounter/code).
- **Per-injector target dicts** — `MISSING_VALUE_TARGETS`, `TYPO_TARGETS`,
  `DATE_FORMAT_TARGETS`, `NUMBER_FORMAT_TARGETS`, `TYPE_MISMATCH_TARGETS`,
  `DATE_ISSUE_TARGETS`, each mapping `table → [columns]` that are fair game
  for that injector. Curated to exclude columns already legitimately blank
  or irregular in clean Synthea output (documented in
  [../synthea-quirks/synthea-clean-input.md](../synthea-quirks/synthea-clean-input.md)),
  so an injector adds a *new* kind of dirtiness rather than inflating a
  baseline quirk.
- **`FK_EDGES`** — the FK graph as `FkEdge(child_table, child_column,
  parent_table, skip_values)`. `skip_values` protects legitimate sentinels
  (e.g. `encounters.PAYER = "NO_INSURANCE"`) from ever being treated as an
  orphan/drift/collision target. Not exhaustive against every FK in the
  schema — a representative slice across the hub tables, enough to exercise
  join-breaking meaningfully.
- **`CARDINALITY_BREAK_TARGETS`** — all of `KEYED_TABLES` (every table whose
  key is genuinely unique in clean data).
- **`KEY_FORMAT_DRIFT_TARGETS`** — a narrower list (just `encounters.PATIENT`
  and `claims.PATIENTID`) of FK edges eligible for surface-format mangling.
- **`DUPLICATE_TARGET_TABLES`** — tables where a whole-row duplicate is
  realistic (a source system re-sending a record); small reference tables
  (`organizations`, `providers`, `payers`) are excluded as low-value.

## `seeding.py` — per-injector RNG isolation

```python
def derive_rng(top_seed: int, injector_name: str) -> random.Random:
    digest = hashlib.sha256(f"{top_seed}:{injector_name}".encode()).digest()
    sub_seed = int.from_bytes(digest[:8], byteorder="big")
    return random.Random(sub_seed)
```

Five lines doing one job: hash `"{seed}:{injector_name}"` to derive a
sub-seed, so each injector draws from its own independent stream. This is
about isolating injectors from each other, not about cross-machine
reproducibility — `random.Random` with an integer seed is deterministic
within CPython, which is what the "seeded, not byte-reproducible" convention
in the repo's `CLAUDE.md` actually relies on.

## `csv_io.py` — the I/O layer

`Table(name, fieldnames, rows)` is the in-memory representation — everything
stays as strings, since CSV has no types and injectors work on string values
directly (e.g. `type_mismatch` tries `float(value)` to check "is this
numeric-looking" rather than relying on a schema type).

Uses stdlib `csv`, not pandas: full control over quoting/formatting, and a
cell the pipeline never touched comes back out value-identical (not
necessarily byte-identical — `csv.QUOTE_MINIMAL` may quote slightly
differently than Synthea's own writer — which is enough, since this repo
doesn't treat byte-for-byte reproducibility as a goal).

`resolve_clean_input(input_dir)` handles the batch-dated folder structure:
if `input_dir` already has `patients.csv` directly in it (test fixtures,
explicit `--input` overrides), treat it as a flat CSV directory. Otherwise
treat it as a `clean_input`-style root containing dated batch subfolders and
pick the lexicographically-latest one (ISO dates sort correctly as
strings). Returns `(csv_dir, batch_label)`; `batch_label` is `None` in the
flat case, which is what tells `pipeline.run()` not to nest the output under
a date folder either.

`load_all_tables()` requires all 18 CSVs from `catalogue.ALL_TABLES` to
exist — fails fast on incomplete Synthea output rather than proceeding with
partial data.

## `manifest.py` — the change log

Every mutation any injector makes is recorded here; it's the ground truth
for what a downstream consumer (Project Hadur) can use to know what was
injected. Full field-by-field format is documented in
[dirty-output-structure.md](dirty-output-structure.md#manifestjsonl) — this
section covers the module's internals instead.

`row_id_for(table_name, row, line_index)` centralizes the keyed-vs-keyless
lookup from `catalogue.py` so every injector identifies rows the same way.
`ManifestWriter` streams JSONL to disk as it goes (one line per call, not
accumulated in memory) and tracks a `Counter` of `(injector, table) → count`
as a side effect; `close()` flushes and returns those counts. Two record
shapes: `record_edit` (cell-level) and `record_duplicate_row` (row-level,
since duplication isn't a "column changed" event). `write_summary()` turns
the closed counts into `manifest_summary.json`, a human-skimmable rollup
separate from the full JSONL log.

## `pipeline.py` — orchestration

`run(config)`, top to bottom:

1. Resolve the batch and load all 18 tables into memory. From here on,
   everything mutates these `Table` objects **in place** — no copying. Every
   run always regenerates from `clean_input/` (never reads an existing
   `dirty_output/`), which is what makes a run idempotent given the same
   seed and config, despite the in-place mutation.
2. Mirror the batch-dated structure on the output side
   (`dirty_output/<BATCH_DATE>/`), so a dirty batch stays traceable to the
   exact clean batch it came from, and regenerating a later clean batch
   doesn't clobber an earlier dirty one.
3. Open the manifest. If `withhold_manifest = true`, it's still written —
   just tucked under a dot-prefixed `.manifest_withheld/` subfolder instead
   of the normal location (e.g. for a blind-eval use case where the ground
   truth of what was injected shouldn't be immediately visible alongside the
   data).
4. **Run injectors in a fixed order** — two tuples, `ROW_LEVEL_ORDER` and
   `JOIN_BREAKING_ORDER`, not just "these injectors run" but *in this exact
   sequence every time*. This matters because **a later injector always sees
   every earlier injector's edits**: `duplicates` runs before
   `formatting`/`type_mismatch`/`date_issues` within row-level, so a
   duplicated row can also get its dates reformatted afterward; row-level
   runs entirely before join-breaking, so e.g. `cardinality_break` can
   collide keys on rows `missing_values` already blanked fields in. This is
   deliberate layering — real dirty data has compounding problems, not
   isolated ones. Every injector shares the exact signature `(tables, cfg,
   rng, manifest) -> None`, which is what lets the loop be a two-line
   dispatch table (`INJECTORS[name](...)`) instead of a chain of
   `if`/`elif`.
5. Close the manifest (flushing JSONL, returning change counts) before
   writing the dirty CSVs, then write `manifest_summary.json` from those
   counts.

## `injectors/row_level.py` — per-cell corruption

Five of the six injectors share one driver, `_edit_targets(tables, targets,
cfg, rng, manifest, injector, transform)`: for each catalogue target
`(table, column)`, walk every currently-populated cell, roll the configured
rate per cell, and on a hit call `transform(value, rng) -> str | None`.
Rules that apply to every injector built this way:

- Empty cells are always skipped — you can't corrupt what's already missing,
  and this keeps the rate meaning "chance per populated cell," not "chance
  per row" (so sparse columns don't get an inflated effective rate).
- `transform` returning `None` means "not eligible, skip silently" (e.g.
  `_reformat_date` returns `None` if the value doesn't match the ISO date
  regex) — the rate roll still happened, so RNG state advances consistently
  regardless of eligibility, but no edit is recorded.
- `new_value == original` is also a no-op (guards a transform that
  round-trips to the same string, e.g. case-swapping a value with no
  letters).
- The manifest only records an *applied* change, so `manifest_summary.json`
  counts are true mutation counts, not rate-hit-attempt counts.

The six injectors:

| Injector | Transform | Notes |
|---|---|---|
| `missing_values` | blanks the cell (`""`) | targets curated to exclude columns already legitimately blank in clean Synthea output |
| `typos` | one of transpose / substitute / case-swap / insert-whitespace, chosen uniformly | requires `len(value) >= 2`; models the range of human/OCR typo classes, not one canonical kind |
| `formatting` | `_reformat_date` (ISO → US/EU/dot) or `_reformat_number` (comma/no-decimal/extra-precision) | two target dicts, one injector name — same value, different surface representation, not actually wrong data |
| `type_mismatch` | replaces a numeric value with a stray string (`N/A`, `unknown`, `--`, `null`, `TBD`) | only fires if `float(value)` succeeds, i.e. the column really was numeric |
| `date_issues` | bad day (31), bad month (13), or 2-digit year | same ISO regex as `formatting`, but produces genuinely invalid dates instead of a cosmetic rewrite — meant to fail downstream date parsing outright |
| `duplicates` | appends a copy of the row | doesn't use `_edit_targets` — it's a row action, not a cell edit. `list(table.rows)` snapshots the row list before iterating, so a duplicate is never itself re-duplicated in the same pass. For keyed tables the duplicate **shares the source row's key value** (a realistic exact-resend scenario) |

## `injectors/join_breaking.py` — relationship corruption

Targets relationships between tables rather than individual values —
exercising what a downstream join/ingestion step has to defend against.
Each injector follows the same shape as row-level (skip empty/sentinel →
roll rate → transform → skip no-ops → mutate → log) but doesn't share a
generic driver, since each needs different context around it:

- **`orphan_fk`** — for every `FkEdge` in `FK_EDGES`, builds the set of real
  parent-table keys, then on a rate hit replaces the child's FK value with a
  freshly-generated UUID guaranteed not to be in that set
  (`_fresh_orphan_id`). Skips empty values and anything in `edge.skip_values`
  (the `NO_INSURANCE` sentinel).
- **`key_format_drift`** — a narrower target list
  (`KEY_FORMAT_DRIFT_TARGETS`). Not "break the join" but "break an
  *exact-string* join while the logical identity stays recoverable": on a
  hit, `_drift_format` uppercases the value, strips its hyphens, or wraps it
  in braces (`{uuid}` — the classic Windows GUID string format, a plausible
  real-world drift). A naive `child.fk == parent.id` string match fails; a
  human or fuzzy join could still tell what it pointed to.
- **`cardinality_break`** — targets `CARDINALITY_BREAK_TARGETS` (all of
  `KEYED_TABLES`). On a hit, picks a *different* existing key value from the
  same table and overwrites this row's key with it, so two rows now share a
  key. `all_keys` is snapshotted before the row loop, so a row that already
  had its key collided-onto can itself be picked as a collision target for a
  later row — collisions can chain. The manifest records `line_index` as the
  row id here, since after the collision the key alone can no longer
  uniquely identify the row.

Join-breaking runs after all row-level injectors (see the ordering note in
`pipeline.py` above), so a row already corrupted by e.g. `typos` can also get
its FK orphaned — the same deliberate layering as within row-level.

## `__main__.py` — CLI

`python -m dirty_data_factory [--config PATH] [--seed N] [--input DIR]
[--output DIR]`. Parses args, loads the TOML config, applies any CLI
overrides via `dataclasses.replace`, calls `pipeline.run()`, and prints the
output dir, manifest path, and total change count.

## Testing strategy (`tests/`)

`tests/conftest.py` hand-builds a small but complete 18-table fixture
(`build_tiny_tables()`) with real Synthea headers and FK values that
genuinely resolve to each other — so any orphan/drift/collision a test
observes was injected by the code under test, not already present in the
fixture. Two fixtures build on it: `tiny_input_dir` (written to real CSVs
under `tmp_path`, for pipeline-level tests) and `tiny_tables` (read back via
`load_all_tables`, for injector-level tests) — routing even injector tests
through a real CSV round-trip exercises `csv_io.py` on every test run.

Two layers of coverage:

- **Unit tests** (`test_config.py`, `test_seeding.py`, `test_row_level.py`,
  `test_join_breaking.py`) pin each piece's specific, documented behavior:
  one test per `ConfigError` path, the three determinism/isolation
  properties `derive_rng` promises, one test per injector asserting the
  exact transformation it claims to make (including negative cases like "the
  `NO_INSURANCE` sentinel is never touched even at rate 1.0" and "rate 0
  changes nothing"), plus a statistical test (`test_rate_is_honoured_within_tolerance`)
  that fires `missing_values` across 5000 rows and checks the observed rate
  lands within ±0.02 of the configured rate.
- **Integration tests** (`test_pipeline.py`) verify properties that only
  emerge from a full `run()`: same seed twice produces byte-identical CSVs
  *and* manifest; different seeds diverge; a disabled injector produces
  zero changes; an untargeted column survives even a rate=1.0 run; and —
  the most thorough test in the suite —
  `test_manifest_accounts_for_every_changed_cell` diffs clean vs. dirty
  output and asserts every cell *not* named in the manifest is
  byte-identical, i.e. the manifest is a complete and accurate diff, which
  is exactly the property Project Hadur's downstream use depends on.

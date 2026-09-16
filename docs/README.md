# Project documentation

Reference documentation for this repo: the clean Synthea dataset, and the
error-injection pipeline that turns it into the dirty output.

## Contents

### `schema/` — the 18-CSV schema, by domain cluster

- **[schema/overview.md](schema/overview.md)** — start here. Dataset summary,
  the coding vocabularies and shared concepts used across tables (SNOMED CT,
  LOINC, RxNorm, CVX, DICOM, UDI, and more), and the documentation
  conventions.
- **[schema/core-entities.md](schema/core-entities.md)** — `patients`,
  `organizations`, `providers`, `payers`: the entities every other table
  references.
- **[schema/clinical-events.md](schema/clinical-events.md)** — `encounters`
  and the ten clinical tables keyed off it (`conditions`, `observations`,
  `procedures`, `medications`, `immunizations`, `allergies`, `careplans`,
  `devices`, `supplies`, `imaging_studies`).
- **[schema/financial-billing.md](schema/financial-billing.md)** — `claims`,
  `claims_transactions`, `payer_transitions`: the revenue-cycle layer.

### `synthea-quirks/`

- **[synthea-quirks/synthea-clean-input.md](synthea-quirks/synthea-clean-input.md)**
  — Synthea's own data-quality quirks in this dataset, and the legitimate
  null / business-logic patterns that can be mistaken for defects.

### `pipeline/` — the error-injection pipeline

- **[pipeline/injection-internals.md](pipeline/injection-internals.md)** —
  how `src/dirty_data_factory/` works: module responsibilities, the
  config/catalogue split, seeding, injector ordering, and what each of the
  nine injectors does and why. Start here for the pipeline's internals.
- **[pipeline/dirty-output-structure.md](pipeline/dirty-output-structure.md)**
  — the `dirty_output/` folder layout and the `manifest.jsonl` /
  `manifest_summary.json` format: what each field means, with examples from
  the committed POC output.

## Scope

`schema/` and `synthea-quirks/` describe the clean Synthea output only (the
committed POC run: 100 patients seeded for New York, seed 42/42, 112 patient
rows including deceased — sample values throughout are drawn from that run).
`pipeline/` describes this repo's own error-injection stage and its output
instead.

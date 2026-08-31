# Dataset documentation

Reference documentation for the POC dataset in `data/poc/clean_input/` — the
clean synthetic healthcare data Synthea produces, before this repo's
error-injection stage runs against it.

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

### `data-quality/`

- **[data-quality/synthea-clean-input.md](data-quality/synthea-clean-input.md)**
  — Synthea's own data-quality quirks in this dataset, and the legitimate
  null / business-logic patterns that can be mistaken for defects.

## Scope

Everything here describes the clean Synthea output only. The dataset is the
committed POC run: 100 patients seeded for New York (seed 42/42), producing
112 patient rows including deceased. Sample values throughout are drawn from
that run.

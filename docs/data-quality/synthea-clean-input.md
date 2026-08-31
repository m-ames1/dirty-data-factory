# Data-quality notes: Synthea's clean input

**Scope: the data-quality characteristics of the clean Synthea dataset**
(`data/poc/clean_input/csv/`) — quirks and null patterns noted while
documenting the schema (`../schema/overview.md`, `../schema/core-entities.md`,
`../schema/clinical-events.md`, `../schema/financial-billing.md`). It covers
the clean Synthea output only, not the error-injected output produced from
it.

The point of the file is to record, in one place, which values in the
"clean" baseline are already imperfect and which apparent gaps are
legitimate — the two are easy to confuse, and both matter for any
downstream use of this data.

Two categories, kept separate because they matter for different reasons:

- **Existing Synthea quirks** — values in the "clean" input that look like
  defects and probably are (unintentional artifacts of Synthea's own
  export code). Matters because injected errors shouldn't duplicate a quirk
  that already exists, and because the clean baseline shouldn't be
  presented as flawless when it isn't.
- **Legitimate nulls / business-logic gaps** — values that look like
  missing data but are actually correct, structural, or intentional.
  Matters so these aren't misrepresented as defects, and so injected
  sparsity can imitate real patterns rather than inventing unrealistic
  ones.

## Existing Synthea quirks (look like defects in the clean input)

- **`organizations.REVENUE`** — `0.0` for all 322 rows. Synthea's exporter
  calls a real revenue accessor, so this looks like an unpopulated
  accumulator rather than a hardcoded zero — not confirmed against Synthea
  source. (core-entities.md)
- **`providers.PROCEDURES`** — `0` for all 322 rows; same pattern as
  `organizations.REVENUE` (real accessor, empty result). Not confirmed
  against source. (core-entities.md)
- **`patients.FIPS`** — blank for 11 of 112 rows. Looks like a gap in
  Synthea's own output rather than intentional optionality, though not
  confirmed against source. Not an injected value. (core-entities.md)
- **`payers.QOLS_AVG`** — the `NO_INSURANCE` row's value is `1.00196...`,
  slightly *above* 1 on a supposedly ~0–1 scale — small-sample
  rounding/aggregation quirk. (core-entities.md)
- **`allergies.SYSTEM`** — always literally the string `Unknown` across all
  160 rows. The `CODE` values themselves still follow Synthea's real rule
  (SNOMED CT for most allergens, RxNorm for the 10 medication-category
  rows) — only the `SYSTEM` label is uninformative. In tables where
  `SYSTEM` is populated correctly it reads `SNOMED-CT`. (clinical-events.md)
- **`claims_transactions.MODIFIER1`/`MODIFIER2`** — always blank, 0 of
  98,160 rows populated. Real CPT modifier fields, structurally present,
  never used in this dataset. (financial-billing.md)
- **`claims_transactions.LINENOTE`** — always blank, 0 of 98,160 rows
  populated. Same situation as `MODIFIER1`/`MODIFIER2`. (financial-billing.md)
- **`claims_transactions.UNITS`** — always `1` across all 98,160 rows; no
  bulk-quantity billing ever occurs (contrast with `supplies.QUANTITY`,
  which does vary). (financial-billing.md)
- **`claims_transactions.FEESCHEDULEID`** — always `1` across all 98,160
  rows; a hardcoded `// TODO` constant in the exporter, not a real
  single-fee-schedule choice (same class as `MODIFIER1`/`MODIFIER2`).
  (financial-billing.md)
- **`imaging_studies.SOP_CODE` / `SOP_DESCRIPTION`** — the SOP Class UID
  `1.2.840.10008.5.1.4.1.1.1.1` carries two different description strings
  in the data ("Digital X-Ray Image Storage" on 19 rows, an en-dash
  "Digital X-Ray Image Storage – for Presentation" variant on 10). Minor
  inconsistency in Synthea's own output. (clinical-events.md)
- **`claims.REFERRINGPROVIDERID`** — blank for all 11,794 rows, and would
  be in any Synthea v4.0.0 run: the CSV exporter writes this column
  unconditionally empty (a `// TODO` placeholder, no logic behind it). Not
  a population-scale artifact. (financial-billing.md)
- **Exact-duplicate rows in the clean baseline** — `observations.csv` has
  7 rows that are byte-identical to another row (a single encounter's
  whole basic-metabolic panel written twice), and `supplies.csv` has 10
  (a "Blood glucose testing strips", qty 50, row doubled within an
  encounter — 10 different encounters, each affected once). These are real
  duplicates already present before any error injection, so injected
  duplicate-record errors won't be the only ones in the dataset and any
  dedup logic downstream has to expect a small baseline rate.
  `medications.csv` additionally has 9 rows that share
  `PATIENT`+`ENCOUNTER`+`CODE`+`START` with another row but differ in
  `STOP`/cost — distinct fills, not duplicates. (clinical-events.md)

## Legitimate nulls / business-logic gaps (not defects)

- **`payers.NO_INSURANCE`** — an intentional sentinel payer row
  (`OWNERSHIP = NO_INSURANCE`), not a null/missing payer. Patients with no
  coverage FK to this row rather than having a blank `PAYER`.
  (core-entities.md)
- **`encounters.REASONCODE`/`REASONDESCRIPTION`** — blank for ~40% of rows
  (2,555 / 6,443). Routine visits (e.g. `wellness`) don't need a
  triggering condition. (clinical-events.md)
- **`conditions.STOP`** — blank for 986 / 3,969 rows. Chronic/ongoing
  conditions never get a stop date. (clinical-events.md)
- **`conditions.csv` (and 8 other tables) have no `Id` column at all** —
  see `overview.md`'s UUID section for the full list. The fallback
  identifier is the composite `PATIENT` + `ENCOUNTER` + `CODE` (+ date),
  which uniquely identifies a row for `conditions`, `procedures`,
  `immunizations`, `allergies`, and `devices` — but **not** for
  `observations`, `medications`, or `supplies`, where it repeats. Duplicate
  detection here can't rely on comparing an `Id`, and can't assume the
  composite is unique either. (clinical-events.md)
- **`observations.ENCOUNTER`** — blank specifically for `QALY`/`DALY`/
  `QOLS` rows (3,090 of them). These are yearly rollup calculations, not
  tied to a single visit — legitimately encounter-less, unlike every other
  row in this table. (clinical-events.md)
- **`procedures.REASONCODE`** — blank for ~53% of rows (9,596 / 17,964).
  Routine/preventive procedures (screenings, reconciliations) don't need a
  triggering diagnosis. (clinical-events.md)
- **`procedures.STOP`** — by contrast, *never* blank (0 / 17,964) — a
  procedure is always a discrete, bounded event, unlike a condition.
  Worth remembering as the inverse pattern to `conditions.STOP`.
  (clinical-events.md)
- **`allergies.csv`'s wide-table shape** — fixed at exactly 2 reaction
  slots (`REACTION1`/`REACTION2` with paired `DESCRIPTION`/`SEVERITY`)
  rather than a one-row-per-reaction child table. Structural ceiling: this
  table cannot represent a 3rd reaction at all, by design. (clinical-events.md)

## Realistic natural variation (not defects)

- **Near-duplicate organization names** — e.g. `CALLEN LORDE COMM HEALTH
  CENTER` vs. `CALLEN LORDE COMMUNITY HEALTH CENTER` both exist as
  separate, legitimate rows in `organizations.csv`. A realistic
  fuzzy-duplicate pattern for duplicate-record injection to model.
  (core-entities.md)

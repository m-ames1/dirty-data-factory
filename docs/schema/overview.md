# Synthea POC data schema

Reference documentation for the 18 CSVs Synthea produces in
`data/poc/clean_input/csv/`. Each cluster file covers one real-world domain:
what each table represents, what its columns mean, and how it foreign-keys to
the rest.

These docs describe the **clean** Synthea output — the input to this repo's
error-injection stage, not the dirty output that stage produces.

## Clusters

- [core-entities.md](core-entities.md) — `patients`, `organizations`,
  `providers`, `payers`. The "who/where" that every other table hangs off
  of.
- [clinical-events.md](clinical-events.md) — `encounters`, `conditions`,
  `observations`, `procedures`, `immunizations`, `allergies`, `medications`,
  `careplans`, `devices`, `supplies`, `imaging_studies`. The actual clinical
  activity, mostly keyed off `encounters`.
- [financial-billing.md](financial-billing.md) — `claims`,
  `claims_transactions`, `payer_transitions`. The revenue-cycle layer that
  shadows the clinical events.

## Data-quality notes

[../data-quality/synthea-clean-input.md](../data-quality/synthea-clean-input.md)
catalogues Synthea's own data-quality quirks in this dataset, and the
legitimate null / business-logic patterns that can be mistaken for defects.

## Concepts and terminology

Background concepts that come up across multiple tables, so they're
explained once here instead of repeated per-table.

### UUID (Universally Unique Identifier)

A 128-bit number, conventionally written as 32 hex digits in five dashed
groups (e.g. `ba419d35-0dfe-8af7-347c-eebf02485a56`). Defined by a general
IETF standard (RFC 4122 / RFC 9562) — **not specific to healthcare or to
Synthea.** It's used throughout software wherever independent systems need
to generate IDs without a central authority coordinating "what's the next
number," because the odds of two independently-generated UUIDs colliding
are astronomically small.

Synthea uses UUIDs (not sequential integers) for the primary keys it does
assign, because it generates each patient's history independently rather
than counting from a central authority. The 18 tables fall into three
groups by how a row is identified:

**9 tables carry a dedicated key column.** `patients`, `organizations`,
`providers`, `payers`, `encounters`, `careplans`, `claims`, and
`imaging_studies` name it `Id`; `claims_transactions` names it `ID`
(uppercase). One asterisk: `imaging_studies.Id` is **not unique** — a
single study spans multiple rows that repeat it (Synthea's own data
dictionary documents this), so even here the id alone isn't a row key.

**8 tables are keyless clinical event logs:** `conditions`,
`observations`, `procedures`, `immunizations`, `allergies`, `medications`,
`devices`, `supplies`. Each row is an append-only record of one clinical
event, tied to its context only through `PATIENT` and `ENCOUNTER` foreign
keys; no other table holds a key reference back to these rows (the only
inbound links are soft *code* matches — see `clinical-events.md`'s
Relationships section), so Synthea assigns them no id. Their natural
identifier is the composite `PATIENT` + `ENCOUNTER` + `CODE` (+ date) —
but that composite is only actually unique in this dataset for
`conditions`, `procedures`, `immunizations`, `allergies`, and `devices`.
It is **not** unique for `observations`, `medications`, or `supplies`
(`observations` and `supplies` even contain a handful of fully identical
rows — see the data-quality notes). Duplicate detection here has to reason
about that composite rather than an `Id`, and can't assume it's unique.

**`payer_transitions` is keyless too, but not an event log.** It records
date-ranged insurance-coverage spans (`START_DATE`/`END_DATE`), and unlike
the eight above it *is* a reference target: `claims_transactions.PATIENTINSURANCEID`
joins to its `MEMBERID` (which is itself non-unique per row — see
`financial-billing.md`). Its own natural composite (`PATIENT` +
`START_DATE` + `END_DATE` + `PAYER`) is unique across all 3,837 rows.

Contrast with real-world healthcare identifiers, which are usually *not*
raw UUIDs at the point a clinician or biller sees them:
- **MRN (Medical Record Number)** — assigned by a specific hospital/EHR
  system, meaningful only within that institution.
- **NPI (National Provider Identifier)** — a real, government-issued
  10-digit ID for licensed providers. Notably, Synthea's `providers.csv`
  does *not* include one.
- **SSN** — present in `patients.csv`; healthcare-adjacent mainly because
  it's often (problematically, in real systems) used as a de facto patient
  identifier.

UUIDs do appear under the hood in modern healthcare data standards (FHIR
resources are commonly UUID-keyed), so Synthea's choice isn't unrealistic —
just a layer below what a human user would typically interact with.

### SNOMED CT (Systematized Nomenclature of Medicine — Clinical Terms)

The dominant clinical coding vocabulary used throughout this dataset (first
appears in `encounters.csv`'s `CODE`/`REASONCODE` columns, and recurs in
`conditions.csv`, `procedures.csv`, `observations.csv`, and others). It's a
real, internationally-maintained ontology used by actual EHR systems — not
something Synthea invented.

Key thing to understand: SNOMED CT is **not a flat code list** — it's a
single ontology spanning many semantically distinct categories (procedures,
disorders, findings, body structures, organisms, and more), each concept
tagged with a parenthetical qualifier showing which category it belongs to,
e.g. `183452005 = Emergency hospital admission (procedure)` vs.
`82423001 = Chronic pain (finding)`. That's why a single encounter row can
have *two* SNOMED CT-coded columns (`CODE` for "what kind of clinical act
was this" and `REASONCODE` for "why did it happen") without being
redundant — they're pulling from different sections of the same dictionary
to answer two different questions.

Implication for error injection: a corrupted SNOMED code reads as a
plausible real-world error only if it respects this category structure — a
`(procedure)` code miscoded as another `(procedure)`, say, rather than as a
`(finding)`. Ignore the structure and the corruption is just obvious
nonsense.

### LOINC (Logical Observation Identifiers Names and Codes)

The standard vocabulary specifically for lab tests, measurements, and
clinical observations — used as `observations.csv`'s `CODE` column (e.g.
`8302-2` = Body Height). A real, internationally-maintained standard,
distinct from SNOMED CT: LOINC covers *what was measured/asked*, while
SNOMED CT (seen in `encounters`/`conditions`) covers procedures, diagnoses,
and findings more broadly. Different code systems for different jobs, both
genuine healthcare standards.

### QALY, DALY, and QOLS

Three related but distinct health-outcome metrics, all appearing as
category-less rows in `observations.csv` (and `QOLS_AVG` also appears
directly in `payers.csv`):

- **QALY (Quality-Adjusted Life Year)** — combines *how long* someone lives
  with *how healthy* that time was. One QALY = one year lived in perfect
  health. The standard metric behind cost-effectiveness analysis for
  medical treatments.
- **DALY (Disability-Adjusted Life Year)** — roughly the inverse framing:
  measures *disease burden* rather than health gained. One DALY = one year
  of healthy life lost to premature death or disability. The metric behind
  the WHO's Global Burden of Disease studies.
- **QOLS (Quality of Life Score)** — a simpler, more direct self-assessed
  or computed quality-of-life score, roughly 0–1.

These are **yearly rollup calculations** computed from a patient's overall
health trajectory across that year, not measurements taken during a
specific visit — which is why their `observations.csv` rows have a blank
`ENCOUNTER` and blank `CATEGORY`. Conceptually closer to
`patients.HEALTHCARE_EXPENSES` (a lifetime aggregate) than to a lab result.

### CVX (Vaccine Administered Code Set)

The CDC's official standard code set for identifying *which specific
vaccine product* was administered — used as `immunizations.csv`'s `CODE`
column (e.g. `140` = "Influenza, split virus, trivalent, PF"). A third
distinct coding system alongside SNOMED CT (procedures/diagnoses/findings)
and LOINC (labs/measurements): SNOMED CT and LOINC never appear in
`immunizations.csv`, and CVX doesn't appear anywhere else in this dataset —
each table in this cluster picks whichever standard vocabulary actually
fits what it's recording.

### RxNorm

The US National Library of Medicine's standard vocabulary specifically for
medications — used as `medications.csv`'s `CODE` column (e.g. `1000126` =
"1 ML medroxyprogesterone acetate 150 MG/ML Injection"). A fourth distinct
coding system in this dataset, alongside SNOMED CT (procedures/diagnoses/
findings), LOINC (labs/measurements), and CVX (vaccines) — each table uses
whichever standard actually fits what it's recording, and none of these
four vocabularies overlap with each other in this dataset.

### UDI (Unique Device Identifier)

A real, FDA-mandated barcode standard (in effect since 2013) for tracking
medical devices, used as `devices.csv`'s `UDI` column. Encoded in GS1
barcode syntax as bracketed segments, e.g.
`(01)81486702245262(11)160905(17)410920(10)3343689389795064(21)36240480647274`:
`(01)` = device identifier (GTIN), `(11)` = manufacture date, `(17)` =
expiration date, `(10)` = lot/batch number, `(21)` = serial number. Not an
arbitrary string: a realistic corruption of this column breaks one of these
bracketed segments specifically, rather than randomizing characters (see
`clinical-events.md`'s `devices.csv` section).

### DICOM (Digital Imaging and Communications in Medicine) UIDs

DICOM is the real, universal standard for medical imaging — used in
`imaging_studies.csv`'s `SERIES_UID`, `INSTANCE_UID`, and `SOP_CODE`
columns. DICOM UIDs are dotted-decimal identifiers (e.g.
`1.2.840.99999999.1.84815171.1474896978928`), a completely different
scheme from the UUIDs (see above) used everywhere else in this dataset as
primary keys — easy to confuse given both are "unique identifiers," but
they're unrelated standards serving different registries (DICOM UIDs are
globally registered under an OID hierarchy; UUIDs are randomly generated
with no registry at all). `MODALITY_CODE` (`DX`, `CR`, `US`, `OP`, `OPT`)
and the `SOP_CODE` (e.g. `1.2.840.10008.5.1.4.1.1.1.1` = "Digital X-Ray
Image Storage") are likewise real, registered DICOM values, not
Synthea-invented.

### SDOH (Social Determinants of Health)

The standard public-health umbrella term (used by CDC, WHO, Healthy People
2030) for *non-medical* factors that shape health outcomes: economic
stability, education, social/community context, healthcare access,
neighborhood/housing conditions. Shows up twice in this dataset through two
different mechanisms — as entries in `conditions.csv` (e.g. "Social
isolation (finding)", "Full-time employment (finding)") and as survey
answers in `observations.csv` (category `survey`, many tagged
`[PRAPARE]`). SDOH is the general concept; PRAPARE (below) is one specific
tool for measuring it.

### PRAPARE (Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences)

A real, standardized national SDOH screening tool developed by the National
Association of Community Health Centers (NACHC) and partners. Gives
providers — especially community health centers — a consistent, structured
way to collect social-risk data during a visit. Appears in
`observations.csv` as individual questionnaire items tagged `[PRAPARE]` in
their `DESCRIPTION` (e.g. "Do you feel physically and emotionally safe
where you currently live [PRAPARE]").

## Conventions used in these docs

- Where a table has a dedicated key column, it's a Synthea-generated UUID
  named `Id` (spelled `ID` in `claims_transactions`), never meaningful or
  sequential. 9 of the 18 tables have one; `imaging_studies.Id` is present
  but non-unique. The other 9 are keyless — 8 clinical event logs plus
  `payer_transitions` — and their natural composite identifier isn't
  guaranteed unique everywhere. See "UUID" under Concepts for the full
  breakdown.
- Column names are given exactly as they appear in the CSV header (Synthea's
  own casing/spelling, including its quirks — e.g. `SPECIALITY` not
  `SPECIALTY`).
- Sample values are pulled from the actual committed POC dataset
  (`data/poc/clean_input/csv/`, a 100-patient New York run, seed 42/42,
  producing 112 patient rows including deceased) unless noted otherwise.

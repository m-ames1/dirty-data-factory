# Core entities

The "who/where" tables. Every clinical and financial table elsewhere in the
dataset foreign-keys back into one or more of these four. Order below
reflects join direction: `patients` and `organizations` are the two roots;
`providers` hangs off `organizations`; `payers` stands alone but is
referenced by nearly everything financial.

## patients.csv

**What it represents:** one row per synthetic person Synthea generated —
their demographics, identity, and lifetime financial summary. This is the
"master patient index" — every clinical and financial event elsewhere in the
dataset traces back to a `Id` here.

**Real-world activity represented:** patient registration/demographics as
they'd exist in an EHR's master patient record — data captured once at
intake and updated occasionally, as opposed to per-visit clinical data.

**Columns:**

| Column | Meaning |
|---|---|
| `Id` | UUID primary key. Everything else joins to this as `PATIENT`. |
| `BIRTHDATE`, `DEATHDATE` | Blank `DEATHDATE` means still alive at generation time. |
| `SSN`, `DRIVERS`, `PASSPORT` | Synthetic government ID numbers. `SSN` is always populated (0/112 blank — a required field). `DRIVERS` (~20% blank) and `PASSPORT` (~29% blank) are the ones frequently blank — e.g. an infant has no driver's license or passport. |
| `PREFIX`/`FIRST`/`MIDDLE`/`LAST`/`SUFFIX`/`MAIDEN` | Synthea appends a numeric suffix to first/middle/last names (e.g. `Corie618`) to guarantee uniqueness across fake-name collisions — by design, not an error. |
| `MARITAL` | Single-letter code: `M`/`S`/`D`/`W` (married/single/divorced/widowed); blank for anyone under age 28 — Synthea only assigns a marital status starting at 28, so adults aged 18–27 are blank too, not just minors. |
| `RACE`, `ETHNICITY` | Separate US Census-style axes — `RACE` and `ETHNICITY` (hispanic/nonhispanic) are independent fields, not one combined field. `RACE` shows `white`/`black`/`asian`/`hawaiian`/`other` in this POC; Synthea's full domain also includes `native` (6 categories), which just doesn't appear in this small NY sample. |
| `GENDER` | `M`/`F`. |
| `BIRTHPLACE` | Free-text "City  State  Country" (double space is Synthea's literal formatting, not a typo). |
| `ADDRESS`/`CITY`/`STATE`/`COUNTY`/`FIPS`/`ZIP`/`LAT`/`LON` | Current residence. `FIPS` (county code) is blank for 11 of 112 rows — noted so a blank here isn't mistaken for injected corruption. Looks like a gap in Synthea's own output rather than intentional optionality, though not confirmed against Synthea source. |
| `HEALTHCARE_EXPENSES` | Lifetime total the patient actually **paid out of pocket** (Synthea's `getTotalOutOfPocketExpenses()`) — not gross charges billed. Distinct from what insurance paid (next row). |
| `HEALTHCARE_COVERAGE` | Lifetime total actually paid by insurance (payers) on their behalf. |
| `INCOME` | Synthetic annual income. Appears to feed Synthea's insurance-affordability logic (the source has income-based plan-eligibility classes), but the exact mechanism isn't confirmed. |

**Sample row** (`data/poc/clean_input/2026-09-01/csv/patients.csv`):
```
Id: ba419d35-0dfe-8af7-347c-eebf02485a56
BIRTHDATE: 1998-07-20
MARITAL: M
RACE: white | ETHNICITY: hispanic | GENDER: F
CITY: Albany | STATE: New York
HEALTHCARE_EXPENSES: 82974.69 | HEALTHCARE_COVERAGE: 269772.75 | INCOME: 28756
```

## organizations.csv

**What it represents:** one row per healthcare facility in Synthea's
simulated world — hospitals, urgent care centers, primary/specialty
practices, community health centers. This is the "where" side of care
delivery: places patients go, and where `providers.csv` clinicians work.

**Real-world activity represented:** a facility/practice registry, the kind
of thing that'd back a "find a provider" directory or a hospital system's
list of its own sites.

**Columns:**

| Column | Meaning |
|---|---|
| `Id` | UUID primary key. Referenced directly by `providers.ORGANIZATION` and by `encounters.ORGANIZATION` (every value in that column is a valid `organizations.Id`). |
| `NAME` | Facility name — real-sounding but synthetic (`CALLEN LORDE COMM HEALTH CENTER`). Note there are near-duplicate names in the data (`CALLEN LORDE COMM HEALTH CENTER` vs `CALLEN LORDE COMMUNITY HEALTH CENTER`) — a realistic fuzzy-duplicate pattern for error injection to model. |
| `ADDRESS`/`CITY`/`STATE`/`ZIP`/`LAT`/`LON` | Facility location. All 322 orgs in this POC are `STATE = NY`, consistent with the Synthea run being seeded for New York. |
| `PHONE` | Facility contact number. |
| `REVENUE` | **`0.0` for all 322 rows.** Synthea's exporter calls a real revenue accessor here, so this looks like an export-side issue (the accumulator never populated in this run) rather than a hardcoded zero — but that's not confirmed against Synthea source. Don't read anything into this column as-is. |
| `UTILIZATION` | Count of encounters conducted at this facility. Ranges from 1 up to several hundred — a rough proxy for facility size/activity level. |

**Sample row** (`data/poc/clean_input/2026-09-01/csv/organizations.csv`):
```
Id: df6473cf-a70b-3401-b1ac-8d213ab31d86
NAME: CALLEN LORDE COMM HEALTH CENTER
CITY: NEW YORK | STATE: NY
REVENUE: 0.0 | UTILIZATION: 159
```

**Relationship to `patients.csv`:** no direct FK — organizations don't
reference patients. The link is transitive, through `encounters` (which
references both a `PATIENT` and an `ORGANIZATION`).

## providers.csv

**What it represents:** one row per individual clinician — the actual
person (doctor, nurse practitioner, etc.) who delivers care, as opposed to
`organizations.csv` which is the facility they work at. This is the
"who provides care" registry, analogous to a hospital's staff directory or
credentialing database.

**Real-world activity represented:** provider credentialing/staff data —
who works where, what they specialize in, how active they are.

**Columns:**

| Column | Meaning |
|---|---|
| `Id` | UUID primary key. Referenced by `encounters.PROVIDER` and other clinical tables' provider-attribution columns. |
| `ORGANIZATION` | FK → `organizations.Id`. The facility this provider is affiliated with. |
| `NAME` | Provider's synthetic full name (same numeric-suffix convention as patient names). |
| `GENDER` | `M`/`F`. |
| `SPECIALITY` | Note the spelling — Synthea's actual column name, not a typo in this documentation. Every provider in this POC is `GENERAL PRACTICE`; the field is free descriptive text, so larger/less-restricted runs likely produce a wider mix, though that's not confirmed here. |
| `ADDRESS`/`CITY`/`STATE`/`ZIP`/`LAT`/`LON` | Mirrors the provider's organization's location — providers don't have an independent address in this model. |
| `ENCOUNTERS` | Count of encounters this provider has conducted. Ranges up to 600+ in this dataset. |
| `PROCEDURES` | **`0` for all 322 rows** — same pattern as `organizations.REVENUE` (a real accessor that comes back empty in this run). Looks like an export-side issue, not confirmed against Synthea source. Not real signal. |

**Sample row** (`data/poc/clean_input/2026-09-01/csv/providers.csv`):
```
Id: a3e5bfbd-414d-365f-a611-34f61a0ed0cc
ORGANIZATION: df6473cf-a70b-3401-b1ac-8d213ab31d86  (CALLEN LORDE COMM HEALTH CENTER)
NAME: Julio255 Olmos892 | GENDER: M | SPECIALITY: GENERAL PRACTICE
ENCOUNTERS: 159 | PROCEDURES: 0
```

**Cardinality note (POC-specific):** this dataset has exactly 322 providers
and 322 organizations, one-to-one. That's a small-dataset artifact, not a
general rule — a real health system (and larger Synthea runs) would have
multiple providers per organization, e.g. a hospital with dozens of
doctors sharing one `ORGANIZATION` id.

**Relationship to `organizations.csv`:** many-to-one via `ORGANIZATION` →
`organizations.Id` (many-to-one in general; this POC happens to be 1:1).

## payers.csv

**What it represents:** one row per insurance payer — government programs
(Medicare, Medicaid), private insurers (Aetna, Cigna, etc.), and a special
`NO_INSURANCE` sentinel row representing patients with no coverage. This is
the payer side of the revenue cycle: who's financially responsible for
care, aggregated at the payer level (not per-patient — that's what
`claims.csv` and `payer_transitions.csv` in the financial-billing cluster
will cover).

**Real-world activity represented:** an insurance-payer master list, plus
lifetime aggregate financial/utilization statistics per payer — closer to
what an insurer's own book-of-business reporting would look like than
anything a clinician would see.

**Columns:**

| Column | Meaning |
|---|---|
| `Id` | UUID primary key. Referenced by encounter/claim-level `PAYER` columns elsewhere. |
| `NAME` | Payer name. Only 10 rows in this POC: `Medicare`, `Medicaid`, `Dual Eligible`, `Humana`, `Blue Cross Blue Shield`, `UnitedHealthcare`, `Aetna`, `Cigna Health`, `Anthem`, `NO_INSURANCE`. |
| `OWNERSHIP` | `GOVERNMENT`, `PRIVATE`, or `NO_INSURANCE`. **`NO_INSURANCE` is a real, intentional sentinel payer** — not missing/null data. A patient with no coverage still gets a `PAYER` FK, it just points at this row. This is legitimate signal, not a gap: join-breaking error injection should preserve rows like this rather than treat them as missing data. |
| `ADDRESS`/`CITY`/`STATE_HEADQUARTERED`/`ZIP`/`PHONE` | Payer's registered address — **blank for all 10 payers in this dataset**, including every private insurer, not just government payers and `NO_INSURANCE`. |
| `AMOUNT_COVERED` | Total dollar amount this payer has paid out, lifetime, across all its members. |
| `AMOUNT_UNCOVERED` | Total dollar amount billed to members that this payer did *not* cover (patient's out-of-pocket responsibility). `NO_INSURANCE` naturally has `AMOUNT_COVERED = 0.00` and a large `AMOUNT_UNCOVERED`. |
| `REVENUE` | Payer's own revenue (premiums collected), distinct from `AMOUNT_COVERED`/`AMOUNT_UNCOVERED` which are claims paid/unpaid. `0.00` for `NO_INSURANCE`, as expected. |
| `COVERED_ENCOUNTERS` / `UNCOVERED_ENCOUNTERS` | Count of encounters this payer did/didn't cover. |
| `COVERED_MEDICATIONS` / `UNCOVERED_MEDICATIONS` | Same idea, for medication fills. |
| `COVERED_PROCEDURES` / `UNCOVERED_PROCEDURES` | Same idea, for procedures. |
| `COVERED_IMMUNIZATIONS` / `UNCOVERED_IMMUNIZATIONS` | Same idea, for immunizations. |
| `UNIQUE_CUSTOMERS` | Distinct patient count ever covered by this payer. |
| `QOLS_AVG` | Average Quality-Of-Life Score across this payer's members — a Synthea-internal synthetic health-outcome metric, roughly 0–1. Note the `NO_INSURANCE` row shows `1.00196...`, slightly *above* 1 — a rounding/aggregation quirk in Synthea's own output on a small sample, not something to read real meaning into. |
| `MEMBER_MONTHS` | Total member-months of coverage accumulated (sum across all members of how many months each was covered) — a standard insurance-industry utilization metric. Notably `NO_INSURANCE` still accrues member-months (`8472`), i.e. Synthea tracks "months spent uninsured" the same way. |

**Sample row** (`data/poc/clean_input/2026-09-01/csv/payers.csv`):
```
Id: a735bf55-83e9-331a-899d-a82a60b9f60c
NAME: Medicare | OWNERSHIP: GOVERNMENT
AMOUNT_COVERED: 6485208.67 | AMOUNT_UNCOVERED: 225204.55 | REVENUE: 671044.50
COVERED_ENCOUNTERS: 2428 | UNIQUE_CUSTOMERS: 33 | QOLS_AVG: 0.6596...
```

**Relationship to `patients.csv`:** no direct FK in this table — patients
don't reference a single payer here (coverage can change over time). That
relationship lives in `payer_transitions.csv` (financial-billing cluster),
which is the per-patient, time-sliced record of which payer covered them
when.

## Relationships within this cluster

- `providers.ORGANIZATION` → `organizations.Id` (many-to-one; 1:1 in this
  POC specifically).
- `patients.csv` and `payers.csv` have **no direct FK to each other or to
  `organizations`/`providers`** within this cluster — all of those links
  are transitive, made concrete in the clinical-events and
  financial-billing clusters (e.g. `encounters` ties a `PATIENT` to an
  `ORGANIZATION` and a `PROVIDER` for one visit; `payer_transitions` ties a
  `PATIENT` to a `PAYER` for a date range).
- In other words: this cluster defines the four *entities*, but the
  *relationships between them* are recorded as attributes on rows in other
  clusters, not here. `encounters.csv` (clinical-events cluster) is the hub
  that most of this cluster's join logic runs through.

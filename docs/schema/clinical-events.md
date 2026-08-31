# Clinical events

The actual clinical activity: encounters, conditions, observations,
procedures, immunizations, allergies, medications, careplans, devices,
supplies, and imaging studies. `encounters.csv` is the hub — almost every
other table in this cluster references a specific `ENCOUNTER` to say when
and in what context it happened.

## encounters.csv

**What it represents:** one row per patient visit/interaction with the
healthcare system — an ER trip, a wellness checkup, an outpatient procedure
visit, etc. This is the **central fact table** of the clinical side: almost
every other clinical table (conditions, observations, procedures,
immunizations, allergies, medications, careplans, devices, supplies,
imaging_studies) references a specific `ENCOUNTER` to say *when and in what
context* that thing happened.

**Real-world activity represented:** an actual patient visit as it would
generate a record in an EHR/scheduling system — check-in to check-out,
tagged with why the patient was there and what it cost.

**Columns:**

| Column | Meaning |
|---|---|
| `Id` | UUID primary key. Referenced as `ENCOUNTER` by nearly every other clinical table. |
| `START`, `STOP` | ISO 8601 timestamps. Most encounter classes are short — median well under two hours (`wellness` ≈ 36 min, `ambulatory` ≈ 64 min). Only `inpatient` (≈ 4 days), `snf` (≈ 11 days), and `hospice` (≈ 22 days) genuinely span longer. |
| `PATIENT` | FK → `patients.Id`. |
| `ORGANIZATION` | FK → `organizations.Id` — where the visit happened. |
| `PROVIDER` | FK → `providers.Id` — who saw the patient. |
| `PAYER` | FK → `payers.Id` — who was financially responsible for this specific visit. 249 of 6,443 encounters here point to the `NO_INSURANCE` sentinel row — a legitimate, real value, not a gap. |
| `ENCOUNTERCLASS` | The visit type — see breakdown below. |
| `CODE`, `DESCRIPTION` | A SNOMED CT code + human-readable description identifying the specific type of encounter, drawn from SNOMED CT's *procedure* concepts (e.g. `183452005` = "Emergency hospital admission (procedure)"). See "Why CODE and REASONCODE are both SNOMED CT" below. |
| `BASE_ENCOUNTER_COST` | The standard/list cost for this type of visit, before any procedures/services performed during it. |
| `TOTAL_CLAIM_COST` | What was actually billed for the whole encounter, including any procedures/services rendered during the visit — always ≥ `BASE_ENCOUNTER_COST` (every row in this POC). |
| `PAYER_COVERAGE` | How much of `TOTAL_CLAIM_COST` the payer actually covered. `TOTAL_CLAIM_COST − PAYER_COVERAGE` is the patient's out-of-pocket share for this encounter. |
| `REASONCODE`, `REASONDESCRIPTION` | SNOMED CT code for the diagnosis/condition that prompted the visit, drawn from SNOMED CT's *disorder*/*finding* concepts — **blank for 2,555 of 6,443 rows** (~40%). That's real and expected: routine `wellness` visits, for example, don't need a triggering condition. Not a data-quality gap to treat as missing. |

**`ENCOUNTERCLASS` values** (distribution in this POC, and what each represents in the real world):

| Value | Count | Real-world meaning |
|---|---|---|
| `ambulatory` | 3,346 | A general clinic/office visit — seeing a doctor at their practice for a specific complaint or follow-up, no overnight stay. |
| `wellness` | 1,291 | A routine preventive visit — annual physical, well-child checkup, screening. Nothing acute is being treated. |
| `outpatient` | 1,007 | A scheduled, hospital-or-facility-based visit for a specific service (e.g. an outpatient surgery center, a diagnostic imaging appointment) — affiliated with a larger facility, but the patient goes home the same day. |
| `urgentcare` | 378 | A visit to an urgent care center — needs same-day attention but isn't life-threatening. |
| `emergency` | 275 | An ER visit — acute, potentially life-threatening. |
| `inpatient` | 105 | A hospital admission — formally admitted to a bed, stays at least one night. |
| `snf` | 17 | **Skilled Nursing Facility** — short-term rehab/nursing care, typically right after a hospital stay, not acute hospital-level care. |
| `virtual` | 12 | A telehealth encounter — video/phone visit, no physical location involved. |
| `hospice` | 12 | End-of-life palliative care — comfort-focused, not curative. |

**Why `CODE`/`DESCRIPTION` and `REASONCODE`/`REASONDESCRIPTION` are separate pairs, even though both use SNOMED CT:**

They answer two different questions about the same encounter, and SNOMED CT
is a single, very broad vocabulary that covers both:
- `CODE`/`DESCRIPTION` answers **"what kind of clinical act was this
  encounter?"** — drawn from SNOMED CT's *procedure* concepts (note the
  `(procedure)` suffix, e.g. `183452005 = Emergency hospital admission
  (procedure)`).
- `REASONCODE`/`REASONDESCRIPTION` answers **"why did this happen?"** —
  drawn from SNOMED CT's *disorder*/*finding* concepts (note the
  `(finding)`/`(disorder)` suffix, e.g. `82423001 = Chronic pain
  (finding)`).

SNOMED CT isn't one flat code list — it's a single ontology spanning many
semantically distinct categories (procedures, disorders, findings, body
structures, organisms, and more, each tagged by that parenthetical suffix).
So it's not redundant that both columns use SNOMED CT; both are pulling
from different sections of the same dictionary. This pattern — one
vocabulary, multiple independent-axis columns — recurs in `conditions.csv`,
`procedures.csv`, and `observations.csv`.

**Sample row** (`data/poc/clean_input/csv/encounters.csv`):
```
Id: ba419d35-0dfe-8af7-2d0c-110156324066
START: 2012-08-22T11:35:06Z | STOP: 2012-08-22T12:35:06Z
PATIENT: ba419d35-0dfe-8af7-347c-eebf02485a56
ENCOUNTERCLASS: emergency | CODE: 183452005 (Emergency hospital admission (procedure))
BASE_ENCOUNTER_COST: 99.00 | TOTAL_CLAIM_COST: 99.00 | PAYER_COVERAGE: 0.00
REASONCODE: 82423001 (Chronic pain (finding))
```

## conditions.csv

**What it represents:** one row per diagnosis, finding, or health-status
entry recorded for a patient — the ongoing "problem list" style data an EHR
maintains, as opposed to `encounters.csv` which is the visit itself. A
single encounter can produce multiple condition entries (e.g. a visit where
two separate things get diagnosed or noted).

**Real-world activity represented:** clinical diagnosis and problem-list
documentation — what a provider determined was going on with the patient
during a given visit, and whether it's ongoing or resolved.

**Columns:**

| Column | Meaning |
|---|---|
| `START`, `STOP` | Date the condition was first noted / resolved. **986 of 3,969 rows have a blank `STOP`** — the condition is still active/unresolved as of dataset generation. Expected for chronic conditions, not a gap. |
| `PATIENT` | FK → `patients.Id`. |
| `ENCOUNTER` | FK → `encounters.Id` — the visit where this was diagnosed/recorded. |
| `SYSTEM` | The coding vocabulary used — always `SNOMED-CT` in this dataset. |
| `CODE`, `DESCRIPTION` | The SNOMED CT code + description for the specific condition/finding. |

**No `Id` column.** Unlike every table in the core-entities cluster, this
table has no dedicated primary key. The natural key is `PATIENT` +
`ENCOUNTER` + `CODE` + `START` together — and for `conditions` that
composite *is* unique across all 3,969 rows (unlike `observations`,
`medications`, and `supplies`, where the equivalent composite repeats —
see `overview.md`'s UUID section). Matters for duplicate detection: logic
here can't just compare an `Id` column, it has to reason about that
composite.

**Social determinants of health (SDOH) show up as conditions, not just
diseases.** A large share of this table isn't medical disorders at all —
the single most common entry is "Medication review due (situation)" (833
rows), and SDOH findings like "Stress (finding)" (307) rank near the top
too, above clinical disorders like "Gingivitis" (282). It isn't a clean
sweep: "Full-time employment (finding)" (270) outranks "Viral sinusitis"
(111) but not Gingivitis, and other SDOH findings ("Social isolation" 108,
"Not in labor force" 98, "Limited social contact" 93) sit below both. The
point still stands — non-medical factors (employment, housing, social
connection) are recorded in the same "conditions" list as actual
diagnoses, mirroring real EHR practice. Not a Synthea quirk.

**Co-occurrence is not the same as a recorded causal link.** Rows that
share the same `PATIENT` + `ENCOUNTER` + date range often look causally
related — e.g. patient `ba419d35-0dfe-8af7-347c-eebf02485a56` has "Not in
labor force (finding)", "Social isolation (finding)", and "Stress
(finding)" all recorded together under one `ENCOUNTER`
(`ba419d35-0dfe-8af7-ba89-1669b0dd9027`, 2020-10-05 to 2021-10-11) — a
believable real-world pattern (unemployment/isolation contributing to
stress). But **the table has no column that structurally encodes "this
condition caused that one."** Each row is independent; the only thing
tying related rows together is that they share `PATIENT` + `ENCOUNTER` +
overlapping dates. Any causal story has to be inferred, not read directly
off the schema. (Contrast with `encounters.csv`'s `REASONCODE`, which *is*
an explicit structural link from one encounter to the one condition that
prompted it — `conditions.csv` has no equivalent link between conditions
themselves.)

**Sample row:**
```
START: 2012-08-22 | STOP: (blank — still active)
PATIENT: ba419d35-0dfe-8af7-347c-eebf02485a56
ENCOUNTER: ba419d35-0dfe-8af7-2d0c-110156324066
SYSTEM: SNOMED-CT | CODE: 82423001 | DESCRIPTION: Chronic pain (finding)
```

## observations.csv

**What it represents:** one row per individual clinical measurement, lab
result, survey answer, or screening-tool score recorded for a patient. If
`conditions.csv` is "what's wrong," `observations.csv` is "what was
measured/asked" — vitals, labs, and questionnaires, whether or not they
point to a diagnosis. This is a big, dense table — 81,636 rows in this POC.

**Real-world activity represented:** the raw measurement/data-capture layer
of an EHR — vital signs taken at check-in, lab panel results, and
increasingly, structured screening questionnaires (depression, anxiety,
substance use, social risk) that real health systems now administer
routinely.

**Columns:**

| Column | Meaning |
|---|---|
| `DATE` | ISO 8601 timestamp of the measurement. |
| `PATIENT` | FK → `patients.Id`. |
| `ENCOUNTER` | FK → `encounters.Id` — **can be blank.** Some observations (notably `QALY`/`DALY`/`QOLS` — see glossary) are yearly rollup calculations, not tied to a single visit. Legitimate, not a data-quality gap — but worth remembering that a blank `ENCOUNTER` here is normal while it would be an error in most other tables. |
| `CATEGORY` | The broad type of observation: `laboratory` (35,830), `survey` (25,404), `vital-signs` (15,217), *(blank)* (3,090 — the QALY/DALY/QOLS rows), `social-history` (1,562), `exam` (385), `imaging` (91), `procedure` (52), `therapy` (5). |
| `CODE`, `DESCRIPTION` | The code + description identifying exactly what was measured. **No `SYSTEM` column here** (unlike `conditions.csv`) — the code format (e.g. `8302-2` = Body Height) is **LOINC**, not SNOMED CT — see glossary. |
| `VALUE` | The actual result — numeric (`159.4`) or free text (`Never smoked tobacco (finding)`), depending on `TYPE`. |
| `UNITS` | Unit of measure — usually a physical unit on numeric rows (`cm`, `kg`, `mmol/L`, `mm[Hg]`) and blank on text rows, but not reliably: ~31% of text rows carry a non-blank `UNITS` (often `{nominal}`, `/a`, `{logmar}`), and a handful of numeric rows are blank. |
| `TYPE` | `numeric` (49,273 rows) or `text` (32,363 rows) — tells you how to interpret `VALUE`. (Synthea's source also defines `boolean`, absent from this sample.) |

**No `Id` column, and no reliable natural key either.** `PATIENT` +
`ENCOUNTER` + `CODE` + `DATE` is the closest thing, but ~250 rows repeat
it (multiple components of one panel share a patient/encounter/timestamp),
and 7 rows are *fully* identical to another row — a whole basic-metabolic
panel written twice for one encounter (logged in the data-quality notes).
Duplicate detection here can't assume any column combination is unique.

**What's actually in here**, by category:
- **`laboratory`** — standard panels: basic metabolic panel (sodium,
  potassium, glucose, creatinine...), CBC (hemoglobin, platelets, white
  cell differential...), lipid panel (cholesterol, LDL, HDL, triglycerides),
  urinalysis, allergen-specific IgE tests, HbA1c, etc.
- **`survey`** — validated clinical screening instruments: PHQ-2/PHQ-9
  (depression), GAD-7 (anxiety), AUDIT-C (alcohol use), DAST-10 (drug use),
  HARK (domestic violence), Morse Fall Scale (fall risk) — plus **PRAPARE**
  (see glossary), which explains why many SDOH-flavored items also show up
  in `conditions.csv`.
- **`vital-signs`** — height, weight, BMI, blood pressure, heart rate,
  respiratory rate, pain score.
- **`social-history`** — e.g. tobacco smoking status.
- Smaller categories (`exam`, `imaging`, `procedure`, `therapy`) hold more
  specialized findings tied to those specific activities.

**Sample rows:**
```
Numeric: DATE=2016-09-12T11:35:06Z | CATEGORY=vital-signs | CODE=8302-2
         DESCRIPTION=Body Height | VALUE=159.4 | UNITS=cm | TYPE=numeric

Text:    DATE=2016-09-12T11:35:06Z | CATEGORY=social-history | CODE=72166-2
         DESCRIPTION=Tobacco smoking status
         VALUE=Never smoked tobacco (finding) | UNITS=(blank) | TYPE=text
```

## procedures.csv

**What it represents:** one row per specific clinical procedure or
intervention performed during an encounter — everything from a quick
screening to a full medical procedure. Where `conditions.csv` is "what's
wrong" and `observations.csv` is "what was measured," `procedures.csv` is
"what was *done* to/for the patient."

**Real-world activity represented:** the procedure/intervention log that
would back procedural billing — the line items a clinician actually
performed during a visit.

**Columns:**

| Column | Meaning |
|---|---|
| `START`, `STOP` | Start/end timestamps for the procedure. **Unlike `conditions.csv`, `STOP` is never blank here** (0 of 17,964 rows) — a procedure is a discrete event with a defined duration, not an ongoing state like a chronic condition. |
| `PATIENT` | FK → `patients.Id`. |
| `ENCOUNTER` | FK → `encounters.Id` — the visit during which this was performed. |
| `SYSTEM` | Always `SNOMED-CT`. |
| `CODE`, `DESCRIPTION` | SNOMED CT code + description, drawn from the *procedure* category (note the `(procedure)` suffix, same pattern as `encounters.CODE`). This is the **action that was taken**. |
| `BASE_COST` | Cost of this specific procedure. |
| `REASONCODE`, `REASONDESCRIPTION` | SNOMED CT disorder/finding code — the **pre-existing diagnosis that justified performing this procedure**. Blank for 9,596 of 17,964 rows (~53%): routine/preventive procedures (screenings, reconciliations) don't need a triggering diagnosis. |

**How to read `CODE` vs. `REASONCODE` — direction matters:** `REASONCODE`
is the diagnosis that already existed; `CODE` is the action taken *in
response to* that diagnosis. Neither column is something "found" during
this row — the diagnosis itself was already recorded separately, as its
own row in `conditions.csv`. This table is purely the action log. Real
example — one dental encounter
(`8cbb5751-6fd0-b2b4-7814-cba64e9459a4`) where seven procedure rows all
carry `REASONCODE = 66383009 (Gingivitis (disorder))`:
```
CODE 34043003    Dental consultation and report (procedure)
CODE 225362009   Dental care (regime/therapy)
CODE 1260009003  Removal of supragingival plaque and calculus from all teeth... (procedure)
CODE 1260010008  Removal of subgingival plaque and calculus from all teeth... (procedure)
CODE 274788003   Examination of gingivae (procedure)
CODE 68071007    Dental fluoride treatment (procedure)
CODE 243085009   Oral health education (procedure)
```
Read as: *"Because the patient has Gingivitis (`REASONCODE`), the provider
performed a cleaning, fluoride treatment, and oral-health education
(`CODE`)."* Diagnosis → justifies → procedure. (`66383009` is a common
reason code — 2,038 procedure rows across 571 encounters carry it, in
per-encounter groups of 1, 5, 6, or 7.)
Same directional pattern as `encounters.csv`'s `CODE`/`REASONCODE` pair:
`REASONCODE` is always the pre-existing justification, `CODE` is always
the event this row itself represents.

**Common procedures in this dataset** skew heavily toward the same
preventive/screening theme seen building across tables: "Depression
screening" (1,805 — the single most common), "Assessment of health and
social care needs" (1,061), "Renal dialysis" (826), "Medication
reconciliation" (797), "Assessment of substance use" (715), plus dental
referrals/consultations/education. This lines up directly with the
PHQ-9/GAD-7/PRAPARE screening instruments seen as *observations* — those
questionnaires are logged here as the *procedure* of administering the
screening, while the actual answers/scores live in `observations.csv`.
Same clinical event, captured from two different angles across two tables.

**Sample row:**
```
START: 2016-09-12T11:35:06Z | STOP: 2016-09-12T11:50:06Z
PATIENT: ba419d35-0dfe-8af7-347c-eebf02485a56
ENCOUNTER: ba419d35-0dfe-8af7-4981-4140c6293455
SYSTEM: SNOMED-CT | CODE: 430193006 | DESCRIPTION: Medication reconciliation (procedure)
BASE_COST: 310.22 | REASONCODE: (blank)
```

## immunizations.csv

**What it represents:** one row per vaccine dose administered to a
patient. Simpler than the tables above — no `STOP`, no `REASONCODE`
(immunizations are routine/preventive, not diagnosis-driven), no `SYSTEM`
column either. Only 1,672 rows in this POC.

**Real-world activity represented:** immunization/vaccination
administration records, the kind of thing that feeds a patient's official
immunization record or a state vaccine registry.

**Columns:**

| Column | Meaning |
|---|---|
| `DATE` | ISO 8601 timestamp of administration. |
| `PATIENT` | FK → `patients.Id`. |
| `ENCOUNTER` | FK → `encounters.Id` — the visit during which it was given. |
| `CODE`, `DESCRIPTION` | Identifies the specific vaccine, coded via **CVX** (see glossary) — a third coding system distinct from SNOMED CT and LOINC. |
| `BASE_COST` | Cost of the dose. |

**Common vaccines** in this dataset: Influenza (878 — by far the most
common, an annual recurring shot), COVID-19 mRNA (90+42), Td/Tdap/DTaP
(tetanus family), HPV, Pneumococcal (PCV13), IPV (polio), Meningococcal,
Hepatitis A/B, Hib, varicella, MMR, rotavirus, zoster — essentially the
standard US childhood + adult recommended immunization schedule.

**Sample row:**
```
DATE: 2016-09-12T11:35:06Z
PATIENT: ba419d35-0dfe-8af7-347c-eebf02485a56
ENCOUNTER: ba419d35-0dfe-8af7-4981-4140c6293455
CODE: 140 | DESCRIPTION: Influenza, split virus, trivalent, PF | BASE_COST: 136.00
```

## allergies.csv

**What it represents:** one row per specific allergy or intolerance a
patient has, plus up to two documented reactions to it. Distinct from
`conditions.csv` in that it's specifically the allergy/intolerance domain,
with its own structure for reaction/severity tracking that
`conditions.csv` doesn't have. Small table — only 160 rows, and only 29 of
the 112 patients have any allergy at all (realistic — most people don't).

**Real-world activity represented:** the allergy list an EHR prominently
displays — the kind of data that drives safety alerts (e.g. "don't
prescribe penicillin, patient is allergic").

**Columns:**

| Column | Meaning |
|---|---|
| `START`, `STOP` | Date noted / resolved. `STOP` is blank for all 160 rows in this POC — like chronic conditions, allergies are treated as lifelong once identified. |
| `PATIENT` | FK → `patients.Id`. |
| `ENCOUNTER` | FK → `encounters.Id` — visit where it was documented. |
| `CODE`, `SYSTEM`, `DESCRIPTION` | The allergen itself. Most codes are SNOMED CT format (e.g. `111088007` = Latex), but the 10 `medication`-category rows use **RxNorm** codes instead (`1191` = Aspirin, `7984` = Penicillin V, `10831` = Sulfamethoxazole/Trimethoprim, `29046` = Lisinopril) — Synthea's rule is RxNorm for medication allergies, SNOMED CT otherwise. The literal `SYSTEM` column reflects neither — see the `SYSTEM` quirk below. |
| `TYPE` | `allergy` or `intolerance` — a real, important clinical distinction: an *allergy* is immune-system mediated (can be life-threatening, e.g. anaphylaxis), an *intolerance* is a non-immune adverse reaction (e.g. lactose intolerance) — different mechanism, different clinical urgency. |
| `CATEGORY` | `environment`, `food`, or `medication` — the source of the allergen. Synthea's full domain also allows `drug` (distinct from `medication`), not seen in this POC. |
| `REACTION1`/`DESCRIPTION1`/`SEVERITY1` | The first documented reaction to this allergen: a SNOMED CT finding/disorder code + description, plus severity (`MILD`/`MODERATE`/`SEVERE`). |
| `REACTION2`/`DESCRIPTION2`/`SEVERITY2` | A second reaction, same structure — present in only 45 of 160 rows. Most allergies have zero or one reaction recorded, not two. |

**`SYSTEM` quirk:** always literally the string `Unknown` across all 160
rows, despite `CODE` clearly being SNOMED CT format (same code style as
`conditions.CODE`/`procedures.CODE`). In tables where `SYSTEM` is
populated correctly (`conditions.csv`, `procedures.csv`), it reads
`SNOMED-CT`. Logged in
[../data-quality/synthea-clean-input.md](../data-quality/synthea-clean-input.md)
as an existing Synthea export quirk, not something to read real meaning
into.

**Sample row** (patient with a latex allergy, two reactions):
```
PATIENT: 4f083ce3-f12b-bb4b-7353-e17f0cd55b0a
CODE: 111088007 | SYSTEM: Unknown | DESCRIPTION: Latex (substance)
TYPE: allergy | CATEGORY: environment
REACTION1: Dyspnea (finding) | SEVERITY1: MODERATE
REACTION2: Wheal (finding) | SEVERITY2: MILD
```

**Structural note:** unlike `conditions.csv`/`observations.csv` which are
purely long/tall (one fact per row), this table is **wide** — it fixed the
max reactions at 2 by giving them numbered column pairs
(`REACTION1`/`REACTION2`) rather than a separate one-row-per-reaction
child table. This table has a hard ceiling (can't represent a 3rd
reaction) that the others don't — also logged in the data quality notes.

## medications.csv

**What it represents:** one row per medication prescription/course a
patient was given — not each individual pill, but each distinct
prescription episode (with a dispense count for refills). 5,351 rows.

**Real-world activity represented:** prescription and pharmacy dispensing
records — what was prescribed, how many times it was filled, and what it
cost.

**Columns:**

| Column | Meaning |
|---|---|
| `START`, `STOP` | When the prescription began/ended. 251 of 5,351 rows have a blank `STOP` — an ongoing/current medication. |
| `PATIENT` | FK → `patients.Id`. |
| `PAYER` | FK → `payers.Id`. First table since `encounters.csv` to carry this — a prescription, like a visit, has its own billing/coverage story. |
| `ENCOUNTER` | FK → `encounters.Id` — the visit where it was prescribed. |
| `CODE`, `DESCRIPTION` | Drug identifier + full name/strength/form (e.g. `856987` = "Acetaminophen 300 MG / Hydrocodone Bitartrate 5 MG Oral Tablet"). No `SYSTEM` column, but the code format is **RxNorm** — see glossary. |
| `BASE_COST` | Cost per dispense/fill. |
| `PAYER_COVERAGE` | How much the payer covered for this prescription. |
| `DISPENSES` | Number of times this prescription was filled/refilled. |
| `TOTALCOST` | `BASE_COST × DISPENSES` (verified: `19.29 × 12 = 231.48` in the sample row below). |
| `REASONCODE`, `REASONDESCRIPTION` | SNOMED CT diagnosis that justified the prescription — same directional pattern as `procedures.REASONCODE` (diagnosis → justifies → action). Blank for only 1,066 of 5,351 rows (~20%) — a much higher fill rate than `procedures.REASONCODE` (~53% blank), since medications are almost always prescribed *for* something specific. |

**Sample row:**
```
START: 2016-06-28T11:35:06Z | STOP: 2017-06-23T11:54:14Z
PATIENT: ba419d35-0dfe-8af7-347c-eebf02485a56
PAYER: 734afbd6-4794-363b-9bc0-6a3981533ed5
CODE: 1000126 | DESCRIPTION: 1 ML medroxyprogesterone acetate 150 MG/ML Injection
BASE_COST: 19.29 | PAYER_COVERAGE: 15.43 | DISPENSES: 12 | TOTALCOST: 231.48
REASONCODE: (blank)
```

## careplans.csv

**What it represents:** one row per structured, longer-term treatment plan
established for a patient — a formal, named plan of care rather than a
single procedure or medication. Where `procedures.csv` captures a discrete
action, `careplans.csv` captures an ongoing *program* (e.g. "Fracture
care," "Diabetes self management plan") that typically spans multiple
future visits. 356 rows.

**Real-world activity represented:** the care-plan documentation an EHR
maintains for managing a patient's ongoing treatment trajectory — the kind
of structured plan a case manager or care coordinator would track.

**Columns:**

| Column | Meaning |
|---|---|
| `Id` | UUID primary key — this table has one, unlike `conditions.csv`. |
| `START`, `STOP` | Plan duration. 161 of 356 rows have a blank `STOP` — an active, ongoing plan. |
| `PATIENT` | FK → `patients.Id`. |
| `ENCOUNTER` | FK → `encounters.Id` — the visit where the plan was established. |
| `CODE`, `DESCRIPTION` | SNOMED CT code identifying the plan type — note the mix of qualifiers: `(record artifact)` for plan documents themselves (e.g. "Care plan," "Diabetes self management plan"), `(regime/therapy)` for treatment programs (e.g. "Wound care," "Fracture care"), and `(procedure)` for plans framed as an active intervention (e.g. "Respiratory therapy," "Self-care interventions"). |
| `REASONCODE`, `REASONDESCRIPTION` | The diagnosis that justified the plan — same directional pattern as `procedures.REASONCODE`/`medications.REASONCODE`. Blank for 182 of 356 rows (~51%) — plans like "Diabetes self management" or "Routine antenatal care" are ongoing programs rather than reactions to one acute diagnosis, so they often skip this. |

**Common care plans:** "Respiratory therapy" (61), "Diabetes self
management plan" (36), "Routine antenatal care" (34), "Self-care
interventions" (29), "Wound care" (27), "Physiotherapy care plan" (21) — a
mix of chronic-disease management programs and post-acute recovery plans.

**Sample row** (a reason-linked plan):
```
Id: ba419d35-0dfe-8af7-126e-84c665672319
START: 2021-09-12 | STOP: 2021-12-24
ENCOUNTER: ba419d35-0dfe-8af7-9696-e4cddc4f1c0d
CODE: 385691007 | DESCRIPTION: Fracture care (regime/therapy)
REASONCODE: 65966004 | REASONDESCRIPTION: Fracture of forearm (disorder)
```

## devices.csv

**What it represents:** one row per medical device associated with a
patient — ranging from durable equipment a patient uses long-term
(wheelchair, CPAP machine, blood glucose meter) to equipment used
momentarily during a single procedure (a dental x-ray machine, an
operating room itself). Broader than "device" in the everyday sense —
Synthea logs anything with a trackable device identifier here, including
rooms/imaging equipment used during an encounter. 674 rows.

**Real-world activity represented:** medical device tracking, most
directly tied to a real FDA regulatory requirement (see `UDI` below) that
hospitals and manufacturers track specific devices used in patient care.

**Columns:**

| Column | Meaning |
|---|---|
| `START`, `STOP` | When the device usage began/ended. For one-time-use equipment (dental x-ray, operating room), `START` and `STOP` are often identical — a momentary event. 234 of 674 rows have a blank `STOP` — durable devices (wheelchairs, CPAP units, glucose meters) a patient is still using. |
| `PATIENT` | FK → `patients.Id`. |
| `ENCOUNTER` | FK → `encounters.Id`. |
| `CODE`, `DESCRIPTION` | SNOMED CT code, mostly tagged `(physical object)` for actual devices, or `(environment)` for "Operating room." |
| `UDI` | **Unique Device Identifier** — a real, FDA-mandated barcode standard (in effect since 2013) for tracking medical devices. The format here is GS1 barcode syntax, e.g. `(01)81486702245262(11)160905(17)410920(10)3343689389795064(21)36240480647274`, where `(01)` = the device identifier (GTIN), `(11)` = manufacture date, `(17)` = expiration date, `(10)` = lot/batch number, `(21)` = serial number. This is a real, well-defined encoding, not an arbitrary string — **a realistic malformed-identifier corruption of this column breaks one of these bracketed segments specifically, rather than randomizing characters**, since that's what a real-world UDI parsing failure would actually look like. |

**Common devices:** "Dental x-ray system" (340) and "Operating room" (128)
dominate — both are equipment-usage-during-a-procedure entries rather than
patient-worn devices — followed by "Appliance for sleep apnea" (41),
"Blood glucose meter" (36), "Home nebulizer" (30), "Manual wheelchair"
(22), dentures, CPAP units.

**Sample row:**
```
START: 2016-09-26T13:36:18Z | STOP: 2016-09-26T13:36:18Z (same instant — momentary use)
PATIENT: ba419d35-0dfe-8af7-347c-eebf02485a56
CODE: 706298007 | DESCRIPTION: Dental x-ray system (physical object)
UDI: (01)81486702245262(11)160905(17)410920(10)3343689389795064(21)36240480647274
```

## supplies.csv

**What it represents:** one row per consumable medical supply used during
a visit — items that get used up rather than durable equipment that gets
tracked/reused. The direct counterpart to `devices.csv`: **devices** are
durable, individually-trackable equipment (hence the `UDI` serial-level
tracking); **supplies** are consumable materials tracked only by quantity,
with no individual identity per unit. 2,680 rows.

**Real-world activity represented:** supply consumption/inventory
logging — the materials a clinic uses up during patient care, the kind of
data that feeds inventory restocking.

**Columns:**

| Column | Meaning |
|---|---|
| `DATE` | Date the supply was used. |
| `PATIENT` | FK → `patients.Id`. |
| `ENCOUNTER` | FK → `encounters.Id`. |
| `CODE`, `DESCRIPTION` | SNOMED CT code for the specific supply item (mostly tagged `(physical object)`, some `(dose form)` for consumable substances like gel). |
| `QUANTITY` | How many units were used — the key structural difference from `devices.csv`, which has no quantity column at all (each device row is one specific tracked unit). Values cluster at `1` (2,081 rows) but range up to `100` (129 rows) for small bulk items. |

**No `Id` column** — same pattern as `conditions.csv`, but with a weaker
natural key: `DATE` + `PATIENT` + `ENCOUNTER` + `CODE` gets close, yet 10
rows repeat it exactly — a "Blood glucose testing strips" (qty 50) row
doubled within an encounter, across 10 different encounters (logged in the
data-quality notes). So unlike `conditions`, this composite isn't a
reliable unique identifier.

**Common supplies:** dental-visit bundles — "Dental floss," "Dental
equipment," "Conventional release periodontal gel" all tied at 610 each
(clearly always dispensed together as a set) — plus diabetes-management
supplies ("Blood glucose testing strips" at quantity 50, "Blood lancet"),
and CPAP/BPAP-related consumables (tubing, masks, air filters) matching
the CPAP devices seen in `devices.csv`.

**Sample row:**
```
DATE: 2016-09-26
PATIENT: ba419d35-0dfe-8af7-347c-eebf02485a56
ENCOUNTER: ba419d35-0dfe-8af7-7457-cd0223f74a1c
CODE: 469020004 | DESCRIPTION: Dental floss (physical object) | QUANTITY: 1
```

## imaging_studies.csv

**What it represents:** one row per diagnostic imaging study performed
(x-ray, ultrasound, ophthalmic imaging) — the record of the *study
itself*, not the image file contents. 658 rows.

**Real-world activity represented:** radiology/imaging order and study
metadata, the kind of record a PACS (Picture Archiving and Communication
System) or radiology information system would hold — separate from the
actual image data, which this table only references by identifier.

**Columns:**

| Column | Meaning |
|---|---|
| `Id` | UUID, but **not a unique row key** — 526 distinct values across 658 rows. A single imaging study produces multiple rows (one per series/instance) that share the same `Id`. Synthea's data dictionary documents this explicitly. It can't be used as a primary key. |
| `DATE` | When the study was performed. |
| `PATIENT` | FK → `patients.Id`. |
| `ENCOUNTER` | FK → `encounters.Id`. |
| `SERIES_UID`, `INSTANCE_UID` | **DICOM UIDs** — see glossary. A different identifier scheme entirely from Synthea's UUIDs, despite the similar name. |
| `BODYSITE_CODE`, `BODYSITE_DESCRIPTION` | SNOMED CT body-structure code for what was imaged. |
| `MODALITY_CODE`, `MODALITY_DESCRIPTION` | The imaging technique, using real DICOM modality codes: `DX` (Digital Radiography), `CR` (Computed Radiography), `US` (Ultrasound), `OP` (Ophthalmic Photography), `OPT` (Ophthalmic Tomography). |
| `SOP_CODE`, `SOP_DESCRIPTION` | The DICOM **SOP Class** (Service-Object Pair) — identifies the specific type of DICOM image object being stored, e.g. `1.2.840.10008.5.1.4.1.1.1.1` = "Digital X-Ray Image Storage." A real, registered DICOM UID, not Synthea-invented. One inconsistency: that same code appears with two different `SOP_DESCRIPTION` strings in this dataset (a plain form and an en-dash "– for Presentation" variant) — see the data-quality notes. |
| `PROCEDURE_CODE` | **Not a UUID FK.** A SNOMED CT code that matches a `CODE` value in `procedures.csv` for the same `ENCOUNTER`. Confirmed directly: encounter `ba419d35-0dfe-8af7-7457-cd0223f74a1c` has both an imaging row with `PROCEDURE_CODE = 241046008` and a `procedures.csv` row with `CODE = 241046008` ("Dental plain X-ray bitewing"). The link back to "what procedure caused this imaging study" is a **code-based join** (`ENCOUNTER` + `CODE` match), not a direct `Id` reference — a different join mechanism from anything else in this cluster. |

**Sample row:**
```
Id: ba419d35-0dfe-8af7-2907-531c13c85c1a
DATE: 2016-09-26T13:36:18Z
BODYSITE_DESCRIPTION: Structure of region of internal part of mouth (body structure)
MODALITY_CODE: DX (Digital Radiography)
SOP_DESCRIPTION: Digital Intra-Oral X-Ray Image Storage - For Presentation
PROCEDURE_CODE: 241046008 → matches procedures.csv CODE for the same ENCOUNTER
```

## Relationships within this cluster

- `encounters.csv` is the hub: `conditions`, `observations`, `procedures`,
  `immunizations`, `allergies`, `medications`, `careplans`, `devices`,
  `supplies`, and `imaging_studies` all carry an `ENCOUNTER` FK back to it
  (with the one legitimate exception of `observations`' QALY/DALY/QOLS
  rows, which have no encounter at all).
- All of them also carry a direct `PATIENT` FK, so most queries in this
  cluster can join through either `patients` or `encounters` depending on
  whether the question is "everything about this patient" or "everything
  that happened at this visit."
- `PAYER` only appears on `encounters` and `medications` — the two things
  in this cluster that are billed with their own distinct payer coverage
  story. Everything else (conditions, procedures, etc.) is billed as part
  of the encounter's overall cost, not separately.
- Several `REASONCODE`/`REASONDESCRIPTION` pairs (`encounters`,
  `procedures`, `medications`, `careplans`) point to a SNOMED CT diagnosis
  code — always in the same direction, diagnosis → justifies → action —
  but there's no FK enforcing that the reason code actually matches a real
  row in `conditions.csv`; it's just a code that happens to describe the
  same thing. This is a "soft" cross-table relationship — matching codes,
  not matching IDs — the same pattern `imaging_studies.PROCEDURE_CODE` uses
  to link back to `procedures.csv`, and there is no FK here to break in the
  usual way.
- Most of this cluster has no `Id` column at all — **8 of the 11 tables**:
  `conditions`, `observations`, `procedures`, `immunizations`,
  `allergies`, `medications`, `devices`, `supplies`. Only `encounters`,
  `careplans`, and `imaging_studies` have one, and `imaging_studies.Id` is
  itself non-unique (see that table's section). The keyless tables fall
  back on `PATIENT`/`ENCOUNTER`/`CODE`/date-based composites — which
  uniquely identify a row for `conditions`, `procedures`, `immunizations`,
  `allergies`, and `devices`, but *not* for `observations`, `medications`,
  or `supplies` (see `overview.md`'s UUID section). (For reference: all
  four core-entities tables do have an `Id`; in financial-billing,
  `payer_transitions` does not.)
- Multiple distinct coding vocabularies coexist across this cluster, each
  for a different purpose: **SNOMED CT** (procedures/diagnoses/findings —
  `encounters`, `conditions`, `procedures`, `careplans`, `devices`,
  `supplies`, imaging bodysite, and most of `allergies`), **LOINC**
  (measurements — `observations`), **CVX** (vaccines — `immunizations`),
  **RxNorm** (medications — `medications`, plus the `medication`-category
  rows of `allergies`), and **DICOM** UIDs specific to `imaging_studies`.
  The one cross-vocabulary table is `allergies`: SNOMED CT for most rows,
  RxNorm for medication allergies.

# Financial billing

The revenue-cycle layer that shadows the clinical events: `claims`,
`claims_transactions`, `payer_transitions`.

## claims.csv

**What it represents:** one row per billing claim — a broader, more
complete billing record than `encounters.csv`'s cost columns. This is the
actual claim as it would be submitted to and adjudicated by insurance,
following the real-world **billing waterfall**: bill the primary insurer,
then the secondary insurer for whatever's left, then the patient for the
remainder. A wide table: 31 columns, 11,794 rows (claims_transactions.csv
is wider still, at 33).

**Real-world activity represented:** medical claims processing/revenue
cycle management — this maps closely to a real CMS-1500 (professional) or
UB-04 (institutional) claim form.

**Identity & parties:**

| Column | Meaning |
|---|---|
| `Id` | UUID primary key. |
| `PATIENTID` | FK → `patients.Id`. |
| `PROVIDERID` | FK → `providers.Id` — who performed the service. |
| `PRIMARYPATIENTINSURANCEID`, `SECONDARYPATIENTINSURANCEID` | FK → `payers.Id`, each. `SECONDARYPATIENTINSURANCEID` is blank for 9,095 of 11,794 rows (~77%) — most patients don't have secondary coverage, which is realistic. |
| `DEPARTMENTID`, `PATIENTDEPARTMENTID` | Internal numeric department codes — not a FK to any table; Synthea's own billing-department numbering, derived from the encounter type. Values `1`–`20` in this POC; Synthea's full range also includes `0`, `7`, and a `99` fallback. The two columns are always equal here. |
| `REFERRINGPROVIDERID` | FK → `providers.Id` for a referring physician. **Blank for all 11,794 rows** — a hardcoded unimplemented field in the v4.0.0 CSV exporter, not a population artifact. See note below. |
| `SUPERVISINGPROVIDERID` | FK → `providers.Id`. Always identical to `PROVIDERID` here (0 of 11,794 rows differ) — the v4.0.0 exporter writes both from the same value, so they can't diverge despite the name suggesting they could. |

**Clinical linkage:**

| Column | Meaning |
|---|---|
| `DIAGNOSIS1`–`DIAGNOSIS8` | Up to 8 SNOMED CT diagnosis codes justifying the claim — mirrors real claim forms' multiple diagnosis-pointer fields (real CMS-1500 forms go up to 12; Synthea caps at 8). `DIAGNOSIS2` alone is blank for 8,482 of 11,794 rows (~72%) — most claims only cite one diagnosis. |
| `APPOINTMENTID` | FK → `encounters.Id`, despite the different name — confirmed directly against sample data. |
| `CURRENTILLNESSDATE`, `SERVICEDATE` | When the underlying condition began vs. when the billed service was actually rendered — relevant to claim adjudication (e.g. pre-existing condition timing). |

**Billing waterfall** (three parallel column sets, one per payer role — primary / secondary / patient):

| Column set | Meaning |
|---|---|
| `STATUS1`/`STATUS2`/`STATUSP` | Claim status with the primary insurer / secondary insurer / patient. Only two non-blank values observed: `BILLED`, `CLOSED`. `STATUS1` and `STATUSP` are never blank; `STATUS2` is blank on exactly the 2,699 rows that **have** a populated `SECONDARYPATIENTINSURANCEID` and set on the 9,095 that don't — the same inversion called out under `HEALTHCARECLAIMTYPEID2` below. |
| `OUTSTANDING1`/`OUTSTANDING2`/`OUTSTANDINGP` | Dollar amount still owed by each party. |
| `LASTBILLEDDATE1`/`LASTBILLEDDATE2`/`LASTBILLEDDATEP` | Last date billed to each party. |
| `HEALTHCARECLAIMTYPEID1`/`HEALTHCARECLAIMTYPEID2` | Claim type code — `1` = professional, `2` = institutional (per Synthea source). Watch the direction on `...ID2`: it's `0` on exactly the 2,699 rows that **have** a populated `SECONDARYPATIENTINSURANCEID`, and `1`/`2` on the 9,095 rows where that's blank. So `0` here marks the *presence* of a secondary payer, not its absence. |

**`REFERRINGPROVIDERID` note:** blank for all 11,794 rows — and it would
be blank in **any** Synthea v4.0.0 run. The v4.0.0 CSV exporter writes
this column unconditionally empty (a `// TODO` placeholder with no logic
behind it), so population size, specialty mix, and referral modules make
no difference. Logged in
[../data-quality/synthea-clean-input.md](../data-quality/synthea-clean-input.md)
as an unimplemented-field quirk.

**Sample row** (patient's first ER visit, fully closed, no secondary insurance):
```
Id: ba419d35-0dfe-8af7-c8fb-83f2952ac3be
PATIENTID: ba419d35-0dfe-8af7-347c-eebf02485a56
PROVIDERID: f350eb85-a748-3cec-9d39-b28260e621ed
PRIMARYPATIENTINSURANCEID: 0133f751-9229-3cfd-815f-b6d4979bdd6a | SECONDARYPATIENTINSURANCEID: (blank)
DIAGNOSIS1: 82423001 | DIAGNOSIS2: 82423001
APPOINTMENTID: ba419d35-0dfe-8af7-2d0c-110156324066  (matches an encounters.csv Id)
STATUS1/STATUS2/STATUSP: CLOSED / CLOSED / CLOSED
OUTSTANDING1/2/P: 0 / 0 / 0
```

## claims_transactions.csv

**What it represents:** one row per financial transaction against a
specific line item of a claim — following the claim's money through its
full lifecycle. Multiple transaction rows accumulate against the same
`CLAIMID` over time as the claim moves through billing. The largest table
in this dataset: 33 columns, 98,160 rows.

**Real-world activity represented:** the actual accounting ledger behind a
claim — this is what a billing department's system generates as a claim
gets charged, paid, and shuffled between payer and patient responsibility
(the waterfall from `claims.csv`, now shown as it actually executes,
transaction by transaction).

Every column below was checked directly against the data rather than
inferred from its name. The two places where the obvious reading of a
column name is wrong are flagged inline.

| Column | Verified meaning |
|---|---|
| `ID` | UUID primary key. Verified unique across all 98,160 rows (0 duplicates). |
| `CLAIMID` | FK → `claims.Id`. |
| `CHARGEID` | A globally unique sequential integer per transaction row — **not** a line-item grouping key shared across a charge's lifecycle, despite the name. Other rows can reference a specific one via `TRANSFEROUTID`. |
| `PATIENTID` | FK → `patients.Id`. Verified identical across every transaction row belonging to the same claim, and matches the parent claim's `PATIENTID` exactly. |
| `TYPE` | `CHARGE` / `PAYMENT` / `TRANSFERIN` / `TRANSFEROUT` in this POC. Synthea's source defines a 5th value, `ADJUSTMENT`, which never fires here (the `ADJUSTMENTS` dollar column is `0.00` on every row). |
| `AMOUNT` | Populated on `CHARGE` and `TRANSFERIN` rows; blank on `PAYMENT` and `TRANSFEROUT` — verified across one sample of each type. |
| `METHOD` | Populated only on `PAYMENT` rows here (`CASH`/`CC`/`CHECK`/`COPAY`/`ECHECK`); blank on the other types. Synthea's source also populates `METHOD` on `ADJUSTMENT` rows with a 6th value, `SYSTEM` — neither appears in this POC. |
| `FROMDATE`, `TODATE` | Service date range for the line item. **Not** claim-wide: each transaction carries its own line item's dates, and they vary within a claim — 18% of claims have more than one distinct `FROMDATE` across their transactions, 24% more than one `TODATE`. |
| `PLACEOFSERVICE` | FK → `organizations.Id` — verified by direct lookup. |
| `PROCEDURECODE` | Reuses the underlying clinical event's own code — **not** a distinct CPT/HCPCS billing code, and not always SNOMED CT: of 453 distinct values, just over half trace to `procedures.CODE` (SNOMED CT), ~30% to `medications.CODE` (RxNorm), ~5% to `immunizations.CODE` (CVX), the rest to `encounters.CODE`. Matches Synthea's wiki wording ("SNOMED-CT or other code, e.g. CVX"). |
| `MODIFIER1`, `MODIFIER2` | Always blank — 0 non-blank values across the entire 98,160-row table. Real CPT modifier fields, structurally present, never populated in this dataset. Logged as a data quality note below. |
| `DIAGNOSISREF1`–`DIAGNOSISREF4` | Positional pointers into the parent claim's `DIAGNOSIS1`–`DIAGNOSIS8` — verified: `DIAGNOSISREF1=1`/`DIAGNOSISREF2=2` on a sample claim correctly mapped to that claim's `DIAGNOSIS1`/`DIAGNOSIS2`. `DIAGNOSISREF3` non-blank for 9,610 rows (~10%), `DIAGNOSISREF4` for only 2,252 (~2%). |
| `UNITS` | Always `1` across the entire table — no bulk-quantity billing occurs here (unlike `supplies.QUANTITY`). |
| `DEPARTMENTID` | Matches the parent claim's `DEPARTMENTID` exactly — verified. |
| `NOTES` | Free-text description mirroring the underlying clinical event's description. |
| `UNITAMOUNT` | Populated (matching `AMOUNT`) only on `CHARGE` rows; `0.00` on the other three types — verified. |
| `TRANSFEROUTID` | Populated only on `TRANSFERIN` rows (13,410 — exactly matching the `TRANSFEROUT` row count, a clean 1:1). Value = the `CHARGEID` of the specific `TRANSFEROUT` row that spawned it — verified directly against a sample claim. |
| `TRANSFERTYPE` | Populated only on `CHARGE` (values `1` or `p`) and `TRANSFERIN` (values `2` or `p`) rows; blank on `PAYMENT`/`TRANSFEROUT`. Indicates which party this charge/transfer currently belongs to: `1` = primary payer, `2` = secondary payer, `p` = patient. Ties directly to `claims.STATUS1`/`STATUS2`/`STATUSP`. |
| `PAYMENTS`, `ADJUSTMENTS`, `TRANSFERS`, `OUTSTANDING` | Dollar mechanics per transaction, populated according to `TYPE`. |
| `APPOINTMENTID` | FK → `encounters.Id` — matches the parent claim exactly, verified. |
| `LINENOTE` | Always blank — 0 non-blank values across the entire table. Same situation as `MODIFIER1`/`MODIFIER2`. |
| `PATIENTINSURANCEID` | **Not a `payers.Id`** — a FK → `payer_transitions.MEMBERID` (a specific patient enrollment-period record, not the insurance company). 1,213 distinct values here, 0 overlap with `payers.Id`. The FK is *mostly* intact: 17 of the 1,213 have no matching `MEMBERID` in `payer_transitions.csv` (orphaned references). Contrast `claims.PRIMARYPATIENTINSURANCEID`/`SECONDARYPATIENTINSURANCEID`, which are direct `payers.Id` FKs (10 distinct values) — the two "insurance ID" columns across `claims.csv` and `claims_transactions.csv` point to different tables entirely. |
| `FEESCHEDULEID` | Always `1` across the entire table — a hardcoded `// TODO` constant in the exporter, not a real fee-schedule selection (same class as `MODIFIER1`/`MODIFIER2`). |
| `PROVIDERID`, `SUPERVISINGPROVIDERID` | FK → `providers.Id` — match the parent claim exactly, verified. |

**Sample — one claim's full 4-transaction lifecycle** (simple ER visit, `CLAIMID = ba419d35-0dfe-8af7-c8fb-83f2952ac3be`):
```
CHARGEID=0  TYPE=CHARGE       AMOUNT=99.00  TRANSFERTYPE=1   TRANSFEROUTID=(blank)
CHARGEID=1  TYPE=TRANSFEROUT  TRANSFERS=99.00  OUTSTANDING=99.00
CHARGEID=2  TYPE=TRANSFERIN   TRANSFERS=99.00  OUTSTANDING=99.00  TRANSFEROUTID=1
CHARGEID=3  TYPE=PAYMENT      METHOD=CASH  PAYMENTS=99.00
```

## payer_transitions.csv

**What it represents:** the patient's insurance coverage history — which
payer covered them during each period of their life, including who
legally owns the policy. This is the real-world "eligibility history" a
payer or clearinghouse maintains to answer "was this patient covered on
date X" during claims adjudication — it's what
`claims_transactions.PATIENTINSURANCEID` (`MEMBERID`) actually FKs into.
3,837 rows.

Every column below was checked directly against real data before writing
this up.

| Column | Verified meaning |
|---|---|
| `PATIENT` | FK → `patients.Id`. |
| `MEMBERID` | **Not unique per row** — 2,476 distinct non-blank values across 3,837 rows, plus 643 blank rows (all `NO_INSURANCE`). The FK target for `claims_transactions.PATIENTINSURANCEID`. Only *loosely* an enrollment-stint identifier; see the note below the table. |
| `START_DATE`, `END_DATE` | Coverage period boundaries. **`END_DATE` is never blank — 0 of 3,837 rows** — a real structural difference from every other date-range table in this dataset (`conditions.STOP`, `medications.STOP`, `careplans.STOP` all use a blank to mean "still ongoing"). Here, coverage is instead segmented into fixed periods (mostly ~1-year renewal cycles) continuing all the way through the patient's simulated lifetime, even for currently-active coverage. "Ongoing" is represented completely differently in this table than everywhere else. |
| `PAYER` | FK → `payers.Id`. |
| `SECONDARY_PAYER` | FK → `payers.Id`, populated for only 291 of 3,837 rows (~7.6%). Not the same rate as `claims.SECONDARYPATIENTINSURANCEID` (~23%) — secondary coverage shows up about 3× more often at the claim level than in the coverage-history table. |
| `PLAN_OWNERSHIP` | `Self`, `Guardian`, `Spouse`, or blank. **Blank correlates exactly with `PAYER = NO_INSURANCE`** — verified directly, every blank-ownership row has the `NO_INSURANCE` sentinel payer. No policy to "own" if uninsured. |
| `OWNER_NAME` | Name of whoever holds the policy — the patient's own name when `Self`, a different name (the parent) when `Guardian`. Blank on exactly the 643 `NO_INSURANCE` rows (the same rows where `PLAN_OWNERSHIP` is blank), populated everywhere else — no policy, no owner. |

**`MEMBERID` as an enrollment identifier.** It behaves like a stable
enrollment-period key only for Guardian-owned (minor) coverage, where
consecutive yearly-renewal rows reliably share one value. For adult `Self` /
`Spouse` coverage, Synthea mints a fresh `MEMBERID` at nearly every renewal
even when payer and ownership are unchanged — e.g. patient `ba419d35-…347c`
has four straight years of `Dual Eligible` / `Self` (2021–2025) with no
coverage change and four different `MEMBERID`s. Across the table, ~55% of
consecutive same-patient periods with identical payer / secondary / ownership
still get a new `MEMBERID`. The reverse never happens: one `MEMBERID` never
spans more than one payer or ownership.

**Downstream note for Project Hadur:** collapsing consecutive rows into one
continuous coverage-period record is a natural silver-layer transform, but
the grouping key must be (patient, payer, secondary, ownership, contiguous
dates), *not* `MEMBERID` alone, which over-segments adult coverage. Out of
scope for this repo either way — bronze hands off Synthea's raw shape as-is.

**Sample — one patient's real coverage history** (patient `ba419d35-…347c`, childhood → adulthood):
```
MEMBERID …c422…  7 yearly rows  2000–2007  Aetna          Guardian  Latia151 Upton904 (the parent)
MEMBERID …0142…  1 row          2007–2008  Cigna Health   Guardian  Latia151 Upton904
MEMBERID …cd86…  5 yearly rows  2008–2013  Aetna (again)  Guardian  Latia151 Upton904
MEMBERID …5139…  3 yearly rows  2013–2016  Anthem         Guardian  Latia151 Upton904
MEMBERID …acee…  1 row          2016–2017  Cigna Health   Self      Corie618 Jast432 (the patient)
```
The one-year `Cigna Health` stint in 2007–2008 sits between two
`Aetna`/`Guardian` blocks, and the second `Aetna` block gets a fresh
`MEMBERID` (`…cd86…`) rather than reusing `…c422…`. Coverage changed in
between here, so that's expected — but per the `MEMBERID` note above, adult
`Self` coverage churns the ID even without a change.

## Relationships within this cluster

- `claims_transactions.CLAIMID` → `claims.Id` — many-to-one; transaction
  rows accumulate against one claim as it moves through billing.
- `claims_transactions.PATIENTINSURANCEID` → `payer_transitions.MEMBERID` —
  a specific enrollment period, **not** `payers.Id`. This is the one
  non-obvious join in the cluster (see the `PATIENTINSURANCEID` row in the
  `claims_transactions` table and the `MEMBERID` note above).
- `claims.PRIMARYPATIENTINSURANCEID` / `SECONDARYPATIENTINSURANCEID` and
  `payer_transitions.PAYER` / `SECONDARY_PAYER` are all direct `payers.Id`
  FKs.
- `claims_transactions.DIAGNOSISREF1`–`DIAGNOSISREF4` are positional
  pointers into the parent claim's `DIAGNOSIS1`–`DIAGNOSIS8`, not codes in
  their own right.

Links out to the rest of the dataset:

- `claims.APPOINTMENTID` and `claims_transactions.APPOINTMENTID` →
  `encounters.Id` — the join back to the clinical side; every financial row
  traces to one encounter.
- `PATIENTID` → `patients.Id`, and `PROVIDERID` / `SUPERVISINGPROVIDERID` →
  `providers.Id`, on both `claims` and `claims_transactions`;
  `payer_transitions.PATIENT` → `patients.Id`.
- `claims_transactions.PLACEOFSERVICE` → `organizations.Id`.

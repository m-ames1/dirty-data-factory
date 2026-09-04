"""The fixed v1 error-injection catalogue: which tables, columns, and FK
relationships are eligible for which injector, and how to identify a row.

This is data, not config, because it encodes facts about the Synthea schema
(key columns, baseline null patterns, join structure) rather than knobs a run
should tune. Config only turns injectors on/off and sets rates; it never
redefines what's eligible.
"""

from dataclasses import dataclass, field

# Tables with a dedicated, (mostly) unique key column.
# imaging_studies.Id is deliberately excluded: it's not unique by design
# (one study spans multiple series/instance rows), so it's not a safe
# cardinality-break target and isn't treated as a keyed table here.
KEYED_TABLES = {
    "patients": "Id",
    "organizations": "Id",
    "providers": "Id",
    "payers": "Id",
    "encounters": "Id",
    "careplans": "Id",
    "claims": "Id",
    "claims_transactions": "ID",
}

# Keyless clinical event logs and payer_transitions: identified in the
# manifest by their 0-based line index in the source file, since natural
# composite keys repeat on some of these tables (observations, medications,
# supplies) and a line index is always available and always unique.
KEYLESS_TABLES = [
    "conditions",
    "procedures",
    "immunizations",
    "allergies",
    "devices",
    "observations",
    "medications",
    "supplies",
    "imaging_studies",
    "payer_transitions",
]

ALL_TABLES = [*KEYED_TABLES, *KEYLESS_TABLES]


@dataclass(frozen=True)
class FkEdge:
    child_table: str
    child_column: str
    parent_table: str
    # Values that legitimately point nowhere real and must never be treated
    # as orphans / drift / collision targets (e.g. the NO_INSURANCE sentinel).
    skip_values: frozenset[str] = field(default_factory=frozenset)


# Hard UUID FKs eligible for orphan_fk / key_format_drift. Not exhaustive
# against the full join map in the design notes — a representative slice
# across the hub tables, enough to exercise join-breaking meaningfully.
# parent table's key column is looked up from KEYED_TABLES.
FK_EDGES: list[FkEdge] = [
    FkEdge("encounters", "PATIENT", "patients"),
    FkEdge("encounters", "ORGANIZATION", "organizations"),
    FkEdge("encounters", "PROVIDER", "providers"),
    FkEdge("encounters", "PAYER", "payers", skip_values=frozenset({"NO_INSURANCE"})),
    FkEdge("claims", "PATIENTID", "patients"),
    FkEdge("claims", "PROVIDERID", "providers"),
    FkEdge("claims_transactions", "CLAIMID", "claims"),
    FkEdge("claims_transactions", "PATIENTID", "patients"),
    FkEdge("conditions", "PATIENT", "patients"),
    FkEdge("conditions", "ENCOUNTER", "encounters"),
    FkEdge("procedures", "PATIENT", "patients"),
    FkEdge("medications", "PATIENT", "patients"),
    FkEdge("providers", "ORGANIZATION", "organizations"),
]

# Cardinality-break targets: keyed tables whose key is genuinely unique in
# the clean data (i.e. all of KEYED_TABLES, since imaging_studies is
# already excluded from that dict).
CARDINALITY_BREAK_TARGETS = list(KEYED_TABLES)

# missing_values: (table, column) pairs that are normally populated.
# Deliberately excludes structural keys and columns already documented as
# legitimately-often-blank in docs/data-quality/synthea-clean-input.md
# (e.g. encounters.REASONCODE, claims.SECONDARYPATIENTINSURANCEID) so the
# injector never inflates a baseline quirk instead of adding a real one.
MISSING_VALUE_TARGETS: dict[str, list[str]] = {
    "patients": ["MARITAL", "RACE", "ETHNICITY", "ADDRESS", "CITY", "STATE", "ZIP", "INCOME"],
    "encounters": ["DESCRIPTION", "TOTAL_CLAIM_COST"],
    "claims": ["STATUS1", "CURRENTILLNESSDATE", "SERVICEDATE"],
    "conditions": ["DESCRIPTION"],
    "procedures": ["DESCRIPTION", "BASE_COST"],
    "medications": ["DESCRIPTION", "TOTALCOST"],
    "observations": ["VALUE", "UNITS"],
    "immunizations": ["DESCRIPTION"],
    "allergies": ["DESCRIPTION", "REACTION1", "DESCRIPTION1"],
    "devices": ["DESCRIPTION", "UDI"],
    "supplies": ["QUANTITY"],
    "careplans": ["DESCRIPTION"],
    "payers": ["PHONE"],
    "payer_transitions": ["OWNER_NAME"],
}

# typos: free-text columns worth corrupting (names, addresses, descriptions).
TYPO_TARGETS: dict[str, list[str]] = {
    "patients": ["FIRST", "LAST", "ADDRESS", "CITY", "BIRTHPLACE"],
    "organizations": ["NAME", "ADDRESS", "CITY"],
    "providers": ["NAME", "ADDRESS", "CITY"],
    "payers": ["NAME", "ADDRESS", "CITY"],
    "encounters": ["DESCRIPTION"],
    "conditions": ["DESCRIPTION"],
    "procedures": ["DESCRIPTION"],
    "medications": ["DESCRIPTION"],
    "immunizations": ["DESCRIPTION"],
    "devices": ["DESCRIPTION"],
    "careplans": ["DESCRIPTION"],
    "allergies": ["DESCRIPTION"],
}

# formatting: date columns get a format-variant rewrite (ISO/US/EU), numeric
# columns get a display-format rewrite (thousands separators, trailing
# zeros) — same value, different surface representation.
DATE_FORMAT_TARGETS: dict[str, list[str]] = {
    "patients": ["BIRTHDATE"],
    "careplans": ["START", "STOP"],
    "conditions": ["START", "STOP"],
    "allergies": ["START", "STOP"],
    "medications": ["START", "STOP"],
    "supplies": ["DATE"],
    "immunizations": ["DATE"],
    "imaging_studies": ["DATE"],
    "claims": ["SERVICEDATE", "CURRENTILLNESSDATE"],
}

NUMBER_FORMAT_TARGETS: dict[str, list[str]] = {
    "patients": ["INCOME"],
    "encounters": ["BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST"],
    "procedures": ["BASE_COST"],
    "medications": ["TOTALCOST"],
    "claims_transactions": ["AMOUNT", "PAYMENTS"],
}

# type_mismatch: numeric columns eligible to receive a stray non-numeric
# string value.
TYPE_MISMATCH_TARGETS: dict[str, list[str]] = {
    "patients": ["INCOME"],
    "encounters": ["TOTAL_CLAIM_COST"],
    "procedures": ["BASE_COST"],
    "medications": ["TOTALCOST"],
    "claims_transactions": ["AMOUNT"],
    "supplies": ["QUANTITY"],
}

# date_issues: same date columns as DATE_FORMAT_TARGETS are eligible for
# impossible-date corruption (kept as a separate dict in case the sets
# should diverge later).
DATE_ISSUE_TARGETS: dict[str, list[str]] = {
    "patients": ["BIRTHDATE"],
    "encounters": ["START"],
    "claims": ["SERVICEDATE"],
}

# duplicates: tables where a whole-row duplicate is a realistic dirty-data
# scenario (a source system re-sending the same record). Small reference
# tables (organizations, providers, payers) are excluded as low-value.
DUPLICATE_TARGET_TABLES = [
    "patients",
    "encounters",
    "claims",
    "claims_transactions",
    "conditions",
    "procedures",
    "medications",
    "observations",
]

# key_format_drift: (child_table, child_column) -> parent_table pairs whose
# child-side value gets its surface format mangled (case/hyphenation) while
# keeping the same logical identity, so an exact-string join breaks.
KEY_FORMAT_DRIFT_TARGETS: list[FkEdge] = [
    FkEdge("encounters", "PATIENT", "patients"),
    FkEdge("claims", "PATIENTID", "patients"),
]

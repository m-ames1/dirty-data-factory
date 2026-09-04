"""A tiny, hand-built, internally-consistent 18-table dataset for tests.

Real Synthea headers, a handful of rows each, FK values that actually
resolve to each other (so any orphan the tests observe was injected, not
already present in the fixture). Columns irrelevant to a given table's row
are left blank.
"""

from pathlib import Path

import pytest

from dirty_data_factory.csv_io import Table, load_all_tables, write_table

HEADERS: dict[str, list[str]] = {
    "patients": [
        "Id",
        "BIRTHDATE",
        "DEATHDATE",
        "SSN",
        "DRIVERS",
        "PASSPORT",
        "PREFIX",
        "FIRST",
        "MIDDLE",
        "LAST",
        "SUFFIX",
        "MAIDEN",
        "MARITAL",
        "RACE",
        "ETHNICITY",
        "GENDER",
        "BIRTHPLACE",
        "ADDRESS",
        "CITY",
        "STATE",
        "COUNTY",
        "FIPS",
        "ZIP",
        "LAT",
        "LON",
        "HEALTHCARE_EXPENSES",
        "HEALTHCARE_COVERAGE",
        "INCOME",
    ],
    "organizations": [
        "Id",
        "NAME",
        "ADDRESS",
        "CITY",
        "STATE",
        "ZIP",
        "LAT",
        "LON",
        "PHONE",
        "REVENUE",
        "UTILIZATION",
    ],
    "providers": [
        "Id",
        "ORGANIZATION",
        "NAME",
        "GENDER",
        "SPECIALITY",
        "ADDRESS",
        "CITY",
        "STATE",
        "ZIP",
        "LAT",
        "LON",
        "ENCOUNTERS",
        "PROCEDURES",
    ],
    "payers": [
        "Id",
        "NAME",
        "OWNERSHIP",
        "ADDRESS",
        "CITY",
        "STATE_HEADQUARTERED",
        "ZIP",
        "PHONE",
        "AMOUNT_COVERED",
        "AMOUNT_UNCOVERED",
        "REVENUE",
        "COVERED_ENCOUNTERS",
        "UNCOVERED_ENCOUNTERS",
        "COVERED_MEDICATIONS",
        "UNCOVERED_MEDICATIONS",
        "COVERED_PROCEDURES",
        "UNCOVERED_PROCEDURES",
        "COVERED_IMMUNIZATIONS",
        "UNCOVERED_IMMUNIZATIONS",
        "UNIQUE_CUSTOMERS",
        "QOLS_AVG",
        "MEMBER_MONTHS",
    ],
    "encounters": [
        "Id",
        "START",
        "STOP",
        "PATIENT",
        "ORGANIZATION",
        "PROVIDER",
        "PAYER",
        "ENCOUNTERCLASS",
        "CODE",
        "DESCRIPTION",
        "BASE_ENCOUNTER_COST",
        "TOTAL_CLAIM_COST",
        "PAYER_COVERAGE",
        "REASONCODE",
        "REASONDESCRIPTION",
    ],
    "careplans": [
        "Id",
        "START",
        "STOP",
        "PATIENT",
        "ENCOUNTER",
        "CODE",
        "DESCRIPTION",
        "REASONCODE",
        "REASONDESCRIPTION",
    ],
    "claims": [
        "Id",
        "PATIENTID",
        "PROVIDERID",
        "PRIMARYPATIENTINSURANCEID",
        "SECONDARYPATIENTINSURANCEID",
        "DEPARTMENTID",
        "PATIENTDEPARTMENTID",
        "DIAGNOSIS1",
        "DIAGNOSIS2",
        "DIAGNOSIS3",
        "DIAGNOSIS4",
        "DIAGNOSIS5",
        "DIAGNOSIS6",
        "DIAGNOSIS7",
        "DIAGNOSIS8",
        "REFERRINGPROVIDERID",
        "APPOINTMENTID",
        "CURRENTILLNESSDATE",
        "SERVICEDATE",
        "SUPERVISINGPROVIDERID",
        "STATUS1",
        "STATUS2",
        "STATUSP",
        "OUTSTANDING1",
        "OUTSTANDING2",
        "OUTSTANDINGP",
        "LASTBILLEDDATE1",
        "LASTBILLEDDATE2",
        "LASTBILLEDDATEP",
        "HEALTHCARECLAIMTYPEID1",
        "HEALTHCARECLAIMTYPEID2",
    ],
    "claims_transactions": [
        "ID",
        "CLAIMID",
        "CHARGEID",
        "PATIENTID",
        "TYPE",
        "AMOUNT",
        "METHOD",
        "FROMDATE",
        "TODATE",
        "PLACEOFSERVICE",
        "PROCEDURECODE",
        "MODIFIER1",
        "MODIFIER2",
        "DIAGNOSISREF1",
        "DIAGNOSISREF2",
        "DIAGNOSISREF3",
        "DIAGNOSISREF4",
        "UNITS",
        "DEPARTMENTID",
        "NOTES",
        "UNITAMOUNT",
        "TRANSFEROUTID",
        "TRANSFERTYPE",
        "PAYMENTS",
        "ADJUSTMENTS",
        "TRANSFERS",
        "OUTSTANDING",
        "APPOINTMENTID",
        "LINENOTE",
        "PATIENTINSURANCEID",
        "FEESCHEDULEID",
        "PROVIDERID",
        "SUPERVISINGPROVIDERID",
    ],
    "imaging_studies": [
        "Id",
        "DATE",
        "PATIENT",
        "ENCOUNTER",
        "SERIES_UID",
        "BODYSITE_CODE",
        "BODYSITE_DESCRIPTION",
        "MODALITY_CODE",
        "MODALITY_DESCRIPTION",
        "INSTANCE_UID",
        "SOP_CODE",
        "SOP_DESCRIPTION",
        "PROCEDURE_CODE",
    ],
    "conditions": ["START", "STOP", "PATIENT", "ENCOUNTER", "SYSTEM", "CODE", "DESCRIPTION"],
    "procedures": [
        "START",
        "STOP",
        "PATIENT",
        "ENCOUNTER",
        "SYSTEM",
        "CODE",
        "DESCRIPTION",
        "BASE_COST",
        "REASONCODE",
        "REASONDESCRIPTION",
    ],
    "immunizations": ["DATE", "PATIENT", "ENCOUNTER", "CODE", "DESCRIPTION", "BASE_COST"],
    "allergies": [
        "START",
        "STOP",
        "PATIENT",
        "ENCOUNTER",
        "CODE",
        "SYSTEM",
        "DESCRIPTION",
        "TYPE",
        "CATEGORY",
        "REACTION1",
        "DESCRIPTION1",
        "SEVERITY1",
        "REACTION2",
        "DESCRIPTION2",
        "SEVERITY2",
    ],
    "devices": ["START", "STOP", "PATIENT", "ENCOUNTER", "CODE", "DESCRIPTION", "UDI"],
    "observations": [
        "DATE",
        "PATIENT",
        "ENCOUNTER",
        "CATEGORY",
        "CODE",
        "DESCRIPTION",
        "VALUE",
        "UNITS",
        "TYPE",
    ],
    "medications": [
        "START",
        "STOP",
        "PATIENT",
        "PAYER",
        "ENCOUNTER",
        "CODE",
        "DESCRIPTION",
        "BASE_COST",
        "PAYER_COVERAGE",
        "DISPENSES",
        "TOTALCOST",
        "REASONCODE",
        "REASONDESCRIPTION",
    ],
    "supplies": ["DATE", "PATIENT", "ENCOUNTER", "CODE", "DESCRIPTION", "QUANTITY"],
    "payer_transitions": [
        "PATIENT",
        "MEMBERID",
        "START_DATE",
        "END_DATE",
        "PAYER",
        "SECONDARY_PAYER",
        "PLAN_OWNERSHIP",
        "OWNER_NAME",
    ],
}


def _row(table: str, **values: str) -> dict[str, str]:
    return {column: values.get(column, "") for column in HEADERS[table]}


def build_tiny_tables() -> dict[str, Table]:
    rows: dict[str, list[dict[str, str]]] = {name: [] for name in HEADERS}

    rows["payers"].append(_row("payers", Id="NO_INSURANCE", NAME="NO_INSURANCE"))
    rows["payers"].append(_row("payers", Id="payer-1", NAME="Acme Health Plan", PHONE="555-0100"))

    rows["organizations"].append(
        _row(
            "organizations",
            Id="org-1",
            NAME="Springfield Clinic",
            ADDRESS="1 Main St",
            CITY="Springfield",
        )
    )

    rows["providers"].append(
        _row(
            "providers",
            Id="prov-1",
            ORGANIZATION="org-1",
            NAME="Dr. Alice Smith",
            ADDRESS="1 Main St",
            CITY="Springfield",
        )
    )

    for i in (1, 2, 3):
        rows["patients"].append(
            _row(
                "patients",
                Id=f"pat-{i}",
                BIRTHDATE="1980-01-15",
                FIRST=f"First{i}",
                LAST=f"Last{i}",
                MARITAL="M",
                RACE="white",
                ETHNICITY="nonhispanic",
                ADDRESS=f"{i} Elm St",
                CITY="Springfield",
                STATE="IL",
                ZIP="62701",
                INCOME="50000",
            )
        )

    for i in (1, 2, 3):
        rows["encounters"].append(
            _row(
                "encounters",
                Id=f"enc-{i}",
                START="2020-03-10T09:00:00Z",
                STOP="2020-03-10T10:00:00Z",
                PATIENT=f"pat-{i}",
                ORGANIZATION="org-1",
                PROVIDER="prov-1",
                PAYER="payer-1",
                ENCOUNTERCLASS="ambulatory",
                DESCRIPTION="General checkup",
                BASE_ENCOUNTER_COST="100.00",
                TOTAL_CLAIM_COST="100.00",
            )
        )

    rows["careplans"].append(
        _row(
            "careplans",
            Id="care-1",
            START="2020-03-10",
            PATIENT="pat-1",
            ENCOUNTER="enc-1",
            DESCRIPTION="Diabetes self management plan",
        )
    )

    rows["claims"].append(
        _row(
            "claims",
            Id="claim-1",
            PATIENTID="pat-1",
            PROVIDERID="prov-1",
            PRIMARYPATIENTINSURANCEID="payer-1",
            APPOINTMENTID="enc-1",
            CURRENTILLNESSDATE="2020-03-10T09:00:00Z",
            SERVICEDATE="2020-03-10T09:00:00Z",
            STATUS1="BILLED",
        )
    )

    rows["claims_transactions"].append(
        _row(
            "claims_transactions",
            ID="1",
            CLAIMID="claim-1",
            CHARGEID="1",
            PATIENTID="pat-1",
            TYPE="CHARGE",
            AMOUNT="100.00",
            APPOINTMENTID="enc-1",
            PROVIDERID="prov-1",
        )
    )

    rows["imaging_studies"].append(
        _row("imaging_studies", Id="img-1", DATE="2020-03-10", PATIENT="pat-1", ENCOUNTER="enc-1")
    )
    rows["conditions"].append(
        _row(
            "conditions",
            START="2020-03-10",
            PATIENT="pat-1",
            ENCOUNTER="enc-1",
            DESCRIPTION="Diabetes",
        )
    )
    rows["procedures"].append(
        _row(
            "procedures",
            START="2020-03-10",
            PATIENT="pat-1",
            ENCOUNTER="enc-1",
            DESCRIPTION="Blood draw",
            BASE_COST="20.00",
        )
    )
    rows["immunizations"].append(
        _row(
            "immunizations",
            DATE="2020-03-10",
            PATIENT="pat-1",
            ENCOUNTER="enc-1",
            DESCRIPTION="Flu shot",
            BASE_COST="15.00",
        )
    )
    rows["allergies"].append(
        _row(
            "allergies",
            START="2020-03-10",
            PATIENT="pat-1",
            ENCOUNTER="enc-1",
            DESCRIPTION="Penicillin allergy",
            REACTION1="Rash",
        )
    )
    rows["devices"].append(
        _row(
            "devices",
            START="2020-03-10",
            PATIENT="pat-1",
            ENCOUNTER="enc-1",
            DESCRIPTION="Hearing aid",
            UDI="00012345",
        )
    )
    rows["observations"].append(
        _row(
            "observations",
            DATE="2020-03-10",
            PATIENT="pat-1",
            ENCOUNTER="enc-1",
            DESCRIPTION="Body weight",
            VALUE="70",
            UNITS="kg",
        )
    )
    rows["medications"].append(
        _row(
            "medications",
            START="2020-03-10",
            PATIENT="pat-1",
            PAYER="payer-1",
            ENCOUNTER="enc-1",
            DESCRIPTION="Metformin",
            BASE_COST="5.00",
            TOTALCOST="5.00",
        )
    )
    rows["supplies"].append(
        _row(
            "supplies",
            DATE="2020-03-10",
            PATIENT="pat-1",
            ENCOUNTER="enc-1",
            DESCRIPTION="Bandage",
            QUANTITY="1",
        )
    )
    rows["payer_transitions"].append(
        _row(
            "payer_transitions",
            PATIENT="pat-1",
            MEMBERID="member-1",
            START_DATE="2020-01-01",
            END_DATE="2020-12-31",
            PAYER="payer-1",
            OWNER_NAME="First1 Last1",
        )
    )

    return {
        name: Table(name=name, fieldnames=HEADERS[name], rows=table_rows)
        for name, table_rows in rows.items()
    }


@pytest.fixture
def tiny_input_dir(tmp_path: Path) -> Path:
    input_dir = tmp_path / "clean_input" / "csv"
    for table in build_tiny_tables().values():
        write_table(table, input_dir / f"{table.name}.csv")
    return input_dir


@pytest.fixture
def tiny_tables(tiny_input_dir: Path) -> dict[str, Table]:
    return load_all_tables(tiny_input_dir)

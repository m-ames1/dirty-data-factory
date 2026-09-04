import random

from dirty_data_factory.config import InjectorConfig
from dirty_data_factory.csv_io import Table
from dirty_data_factory.injectors import row_level
from dirty_data_factory.manifest import ManifestWriter

FULL = InjectorConfig(enabled=True, rate=1.0)
NEVER = InjectorConfig(enabled=True, rate=0.0)


def _manifest(tmp_path):
    return ManifestWriter(tmp_path / "manifest.jsonl")


def test_missing_values_nulls_populated_cells(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    row_level.apply_missing_values(tiny_tables, FULL, random.Random(1), manifest)
    assert tiny_tables["patients"].rows[0]["MARITAL"] == ""
    counts = manifest.close()
    assert counts[("missing_values", "patients")] > 0


def test_missing_values_at_zero_rate_changes_nothing(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    before = tiny_tables["patients"].rows[0]["MARITAL"]
    row_level.apply_missing_values(tiny_tables, NEVER, random.Random(1), manifest)
    assert tiny_tables["patients"].rows[0]["MARITAL"] == before
    assert manifest.close() == {}


def test_typos_change_text_without_dropping_it(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    before = tiny_tables["patients"].rows[0]["FIRST"]
    row_level.apply_typos(tiny_tables, FULL, random.Random(1), manifest)
    after = tiny_tables["patients"].rows[0]["FIRST"]
    assert after != before
    assert (
        len(after) >= len(before) - 1
    )  # transpose/substitute/case keep length; whitespace adds one


def test_duplicates_appends_a_copy(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    before_count = len(tiny_tables["patients"].rows)
    row_level.apply_duplicates(tiny_tables, FULL, random.Random(1), manifest)
    assert len(tiny_tables["patients"].rows) == before_count * 2
    # the duplicate keeps the same key, since it's a literal copy of the row
    ids = [row["Id"] for row in tiny_tables["patients"].rows]
    assert ids.count("pat-1") == 2


def test_formatting_rewrites_date_and_number_without_changing_meaning(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    row_level.apply_formatting(tiny_tables, FULL, random.Random(1), manifest)
    birthdate = tiny_tables["patients"].rows[0]["BIRTHDATE"]
    assert birthdate != "1980-01-15"
    assert birthdate in ("01/15/1980", "15/01/1980", "1980.01.15")


def test_type_mismatch_replaces_numeric_with_stray_string(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    row_level.apply_type_mismatch(tiny_tables, FULL, random.Random(1), manifest)
    value = tiny_tables["patients"].rows[0]["INCOME"]
    assert value in row_level._STRAY_STRINGS


def test_date_issues_produces_an_invalid_calendar_date(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    row_level.apply_date_issues(tiny_tables, FULL, random.Random(1), manifest)
    birthdate = tiny_tables["patients"].rows[0]["BIRTHDATE"]
    assert birthdate != "1980-01-15"


def test_rate_is_honoured_within_tolerance():
    table = Table(
        name="patients",
        fieldnames=["Id", "MARITAL"],
        rows=[{"Id": str(i), "MARITAL": "M"} for i in range(5000)],
    )
    tables = {"patients": table}
    manifest_records = []

    class FakeManifest:
        def record_edit(self, **kwargs):
            manifest_records.append(kwargs)

    cfg = InjectorConfig(enabled=True, rate=0.1)
    row_level.apply_missing_values(tables, cfg, random.Random(7), FakeManifest())
    observed_rate = len(manifest_records) / 5000
    assert abs(observed_rate - 0.1) < 0.02

import random

from dirty_data_factory.config import InjectorConfig
from dirty_data_factory.injectors import join_breaking
from dirty_data_factory.manifest import ManifestWriter

FULL = InjectorConfig(enabled=True, rate=1.0)


def _manifest(tmp_path):
    return ManifestWriter(tmp_path / "manifest.jsonl")


def test_orphan_fk_repoints_to_a_nonexistent_parent(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    patient_ids = {row["Id"] for row in tiny_tables["patients"].rows}
    join_breaking.apply_orphan_fk(tiny_tables, FULL, random.Random(1), manifest)
    for row in tiny_tables["encounters"].rows:
        assert row["PATIENT"] not in patient_ids


def test_orphan_fk_never_touches_the_sentinel(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    tiny_tables["encounters"].rows[0]["PAYER"] = "NO_INSURANCE"
    join_breaking.apply_orphan_fk(tiny_tables, FULL, random.Random(1), manifest)
    assert tiny_tables["encounters"].rows[0]["PAYER"] == "NO_INSURANCE"


def test_key_format_drift_mangles_surface_format_only(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    before = tiny_tables["encounters"].rows[0]["PATIENT"]
    join_breaking.apply_key_format_drift(tiny_tables, FULL, random.Random(1), manifest)
    after = tiny_tables["encounters"].rows[0]["PATIENT"]
    assert after != before
    assert after.lower().replace("-", "").strip("{}") == before.lower().replace("-", "")


def test_cardinality_break_creates_a_duplicate_key(tiny_tables, tmp_path):
    manifest = _manifest(tmp_path)
    join_breaking.apply_cardinality_break(tiny_tables, FULL, random.Random(1), manifest)
    ids = [row["Id"] for row in tiny_tables["patients"].rows]
    assert len(set(ids)) < len(ids)

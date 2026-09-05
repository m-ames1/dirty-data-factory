import json
from pathlib import Path

from dirty_data_factory.config import Config, InjectorConfig
from dirty_data_factory.pipeline import JOIN_BREAKING_ORDER, ROW_LEVEL_ORDER, run


def _make_config(input_dir: Path, output_dir: Path, *, seed: int = 1, rate: float = 0.3) -> Config:
    row_level = {name: InjectorConfig(enabled=True, rate=rate) for name in ROW_LEVEL_ORDER}
    join_breaking = {name: InjectorConfig(enabled=True, rate=rate) for name in JOIN_BREAKING_ORDER}
    return Config(
        seed=seed,
        input_dir=input_dir,
        output_dir=output_dir,
        withhold_manifest=False,
        row_level=row_level,
        join_breaking=join_breaking,
    )


def _read_csvs(output_dir: Path) -> dict[str, str]:
    return {p.name: p.read_text() for p in sorted((output_dir / "csv").glob("*.csv"))}


def test_same_seed_produces_identical_output_and_manifest(tiny_input_dir, tmp_path):
    run(_make_config(tiny_input_dir, tmp_path / "run1"))
    run(_make_config(tiny_input_dir, tmp_path / "run2"))

    assert _read_csvs(tmp_path / "run1") == _read_csvs(tmp_path / "run2")
    manifest1 = (tmp_path / "run1" / "manifest.jsonl").read_text()
    manifest2 = (tmp_path / "run2" / "manifest.jsonl").read_text()
    assert manifest1 == manifest2


def test_different_seeds_diverge(tiny_input_dir, tmp_path):
    run(_make_config(tiny_input_dir, tmp_path / "run1", seed=1))
    run(_make_config(tiny_input_dir, tmp_path / "run2", seed=2))
    assert _read_csvs(tmp_path / "run1") != _read_csvs(tmp_path / "run2")


def test_manifest_accounts_for_every_changed_cell(tiny_input_dir, tmp_path):
    from dirty_data_factory.csv_io import load_all_tables

    output_dir = tmp_path / "out"
    result = run(_make_config(tiny_input_dir, output_dir))

    clean = load_all_tables(tiny_input_dir)
    dirty = load_all_tables(output_dir / "csv")

    edits = [
        json.loads(line)
        for line in result.manifest_path.read_text().splitlines()
        if json.loads(line)["action"] == "edit_cell"
    ]
    edited = {(e["table"], e["row_id"], e["column"]) for e in edits}

    # every clean row that still has a matching row_id in dirty should be
    # byte-identical except at manifest-recorded (table, row_id, column) cells.
    for table_name, clean_table in clean.items():
        dirty_rows_by_id = {}
        from dirty_data_factory.manifest import row_id_for

        for i, row in enumerate(dirty[table_name].rows):
            dirty_rows_by_id.setdefault(row_id_for(table_name, row, i), row)

        for i, clean_row in enumerate(clean_table.rows):
            row_id = row_id_for(table_name, clean_row, i)
            dirty_row = dirty_rows_by_id.get(row_id)
            if dirty_row is None:
                continue
            for column, clean_value in clean_row.items():
                if (table_name, row_id, column) in edited:
                    continue
                assert dirty_row[column] == clean_value, (table_name, row_id, column)


def test_untouched_column_is_never_modified(tiny_input_dir, tmp_path):
    from dirty_data_factory.csv_io import load_all_tables

    output_dir = tmp_path / "out"
    run(_make_config(tiny_input_dir, output_dir, rate=1.0))
    dirty = load_all_tables(output_dir / "csv")
    # ENCOUNTERCLASS is not targeted by any row-level or join-breaking
    # injector in the catalogue, so it must survive even a rate=1.0 run.
    assert all(row["ENCOUNTERCLASS"] == "ambulatory" for row in dirty["encounters"].rows)


def test_disabled_injector_produces_no_changes(tiny_input_dir, tmp_path):
    config = _make_config(tiny_input_dir, tmp_path / "out", rate=1.0)
    config.row_level["typos"] = InjectorConfig(enabled=False, rate=1.0)
    result = run(config)
    assert not any(injector == "typos" for injector, _table in result.change_counts)

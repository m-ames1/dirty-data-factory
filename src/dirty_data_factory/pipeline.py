"""Orchestrates a full injection run: load -> row-level injectors ->
join-breaking injectors -> write CSVs + manifest.

Injectors run in a fixed order so a later injector's view of the data
always includes every earlier injector's edits (e.g. a join-breaker can
land on a row a row-level injector already touched). A run always
regenerates from `clean_input/` — it never reads an existing
`dirty_output/` — so it stays idempotent given the same seed and config.

The output is written under the same batch label as its source
(`dirty_output/<BATCH_DATE>/`, mirroring `clean_input/<BATCH_DATE>/`) so a
dirty batch stays traceable to the exact clean batch it was derived from,
and regenerating a later clean batch doesn't clobber an earlier dirty one.
"""

from dataclasses import dataclass
from pathlib import Path

from dirty_data_factory.config import Config
from dirty_data_factory.csv_io import Table, load_all_tables, resolve_clean_input, write_all_tables
from dirty_data_factory.injectors.join_breaking import INJECTORS as JOIN_BREAKING_INJECTORS
from dirty_data_factory.injectors.row_level import INJECTORS as ROW_LEVEL_INJECTORS
from dirty_data_factory.manifest import ManifestWriter, write_summary
from dirty_data_factory.seeding import derive_rng

# Fixed application order within each tier.
ROW_LEVEL_ORDER = (
    "missing_values",
    "typos",
    "duplicates",
    "formatting",
    "type_mismatch",
    "date_issues",
)
JOIN_BREAKING_ORDER = ("orphan_fk", "key_format_drift", "cardinality_break")


@dataclass
class RunResult:
    tables: dict[str, Table]
    manifest_path: Path
    summary_path: Path
    change_counts: dict


def run(config: Config) -> RunResult:
    csv_dir, batch_label = resolve_clean_input(config.input_dir)
    tables = load_all_tables(csv_dir)

    output_dir = config.output_dir / batch_label if batch_label else config.output_dir

    manifest_path = (
        output_dir / ".manifest_withheld" / "manifest.jsonl"
        if config.withhold_manifest
        else output_dir / "manifest.jsonl"
    )
    manifest = ManifestWriter(manifest_path)

    for name in ROW_LEVEL_ORDER:
        cfg = config.row_level[name]
        if not cfg.enabled:
            continue
        rng = derive_rng(config.seed, name)
        ROW_LEVEL_INJECTORS[name](tables, cfg, rng, manifest)

    for name in JOIN_BREAKING_ORDER:
        cfg = config.join_breaking[name]
        if not cfg.enabled:
            continue
        rng = derive_rng(config.seed, name)
        JOIN_BREAKING_INJECTORS[name](tables, cfg, rng, manifest)

    change_counts = manifest.close()

    write_all_tables(tables, output_dir)

    summary_path = output_dir / "manifest_summary.json"
    write_summary(change_counts, summary_path)

    return RunResult(
        tables=tables,
        manifest_path=manifest_path,
        summary_path=summary_path,
        change_counts=change_counts,
    )

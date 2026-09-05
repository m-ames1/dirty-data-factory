"""Join-breaking injectors: orphan FKs, key-format drift, cardinality
breaks. These target the relationships between CSVs rather than individual
cell values, exercising what a downstream ingestion/join step would need to
handle.
"""

import random
import uuid

from dirty_data_factory.catalogue import (
    CARDINALITY_BREAK_TARGETS,
    FK_EDGES,
    KEY_FORMAT_DRIFT_TARGETS,
    KEYED_TABLES,
)
from dirty_data_factory.config import InjectorConfig
from dirty_data_factory.csv_io import Table
from dirty_data_factory.manifest import ManifestWriter, row_id_for

TIER = "join"


def _fresh_orphan_id(rng: random.Random, existing: set[str]) -> str:
    while True:
        candidate = str(uuid.UUID(int=rng.getrandbits(128), version=4))
        if candidate not in existing:
            return candidate


def apply_orphan_fk(
    tables: dict[str, Table], cfg: InjectorConfig, rng: random.Random, manifest: ManifestWriter
) -> None:
    for edge in FK_EDGES:
        child = tables.get(edge.child_table)
        parent = tables.get(edge.parent_table)
        if child is None or parent is None or edge.child_column not in child.fieldnames:
            continue
        parent_key_column = KEYED_TABLES[edge.parent_table]
        existing_keys = {row[parent_key_column] for row in parent.rows}
        rate = cfg.rate_for(edge.child_table, edge.child_column)
        for line_index, row in enumerate(child.rows):
            value = row.get(edge.child_column, "")
            if value == "" or value in edge.skip_values:
                continue
            if rng.random() >= rate:
                continue
            new_value = _fresh_orphan_id(rng, existing_keys)
            row[edge.child_column] = new_value
            manifest.record_edit(
                injector="orphan_fk",
                tier=TIER,
                table=edge.child_table,
                row_id=row_id_for(edge.child_table, row, line_index),
                column=edge.child_column,
                original=value,
                new=new_value,
            )


def _drift_format(value: str, rng: random.Random) -> str:
    variant = rng.choice(("upper", "strip_hyphens", "braces"))
    if variant == "upper":
        return value.upper()
    if variant == "strip_hyphens":
        return value.replace("-", "")
    return "{" + value + "}"


def apply_key_format_drift(
    tables: dict[str, Table], cfg: InjectorConfig, rng: random.Random, manifest: ManifestWriter
) -> None:
    for edge in KEY_FORMAT_DRIFT_TARGETS:
        child = tables.get(edge.child_table)
        if child is None or edge.child_column not in child.fieldnames:
            continue
        rate = cfg.rate_for(edge.child_table, edge.child_column)
        for line_index, row in enumerate(child.rows):
            value = row.get(edge.child_column, "")
            if value == "" or value in edge.skip_values:
                continue
            if rng.random() >= rate:
                continue
            new_value = _drift_format(value, rng)
            if new_value == value:
                continue
            row[edge.child_column] = new_value
            manifest.record_edit(
                injector="key_format_drift",
                tier=TIER,
                table=edge.child_table,
                row_id=row_id_for(edge.child_table, row, line_index),
                column=edge.child_column,
                original=value,
                new=new_value,
            )


def apply_cardinality_break(
    tables: dict[str, Table], cfg: InjectorConfig, rng: random.Random, manifest: ManifestWriter
) -> None:
    for table_name in CARDINALITY_BREAK_TARGETS:
        table = tables.get(table_name)
        if table is None:
            continue
        key_column = KEYED_TABLES[table_name]
        rate = cfg.rate_for(table_name, key_column)
        all_keys = [row[key_column] for row in table.rows]
        for line_index, row in enumerate(table.rows):
            if rng.random() >= rate:
                continue
            original = row[key_column]
            candidates = [k for k in all_keys if k != original]
            if not candidates:
                continue
            collide_with = rng.choice(candidates)
            row[key_column] = collide_with
            manifest.record_edit(
                injector="cardinality_break",
                tier=TIER,
                table=table_name,
                row_id=line_index,
                column=key_column,
                original=original,
                new=collide_with,
            )


INJECTORS = {
    "orphan_fk": apply_orphan_fk,
    "key_format_drift": apply_key_format_drift,
    "cardinality_break": apply_cardinality_break,
}

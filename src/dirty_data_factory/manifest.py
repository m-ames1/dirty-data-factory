"""JSONL manifest of every injected change, plus a per-injector/table summary."""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dirty_data_factory.catalogue import KEYED_TABLES


def row_id_for(table_name: str, row: dict[str, str], line_index: int) -> str | int:
    """The identifier recorded in the manifest for a given row.

    Keyed tables use their key column's value. Keyless tables (and
    imaging_studies, whose Id is not unique) use the row's 0-based line
    index in the source file, which is always present and always unique.
    """
    key_column = KEYED_TABLES.get(table_name)
    if key_column is not None:
        return row[key_column]
    return line_index


@dataclass
class ManifestWriter:
    path: Path
    _file: Any = None
    _counts: Counter = None

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8")
        self._counts = Counter()

    def record_edit(
        self,
        *,
        injector: str,
        tier: str,
        table: str,
        row_id: str | int,
        column: str,
        original: str | None,
        new: str | None,
    ) -> None:
        self._write(
            {
                "injector": injector,
                "tier": tier,
                "action": "edit_cell",
                "table": table,
                "row_id": row_id,
                "column": column,
                "original": original,
                "new": new,
            }
        )

    def record_duplicate_row(
        self,
        *,
        injector: str,
        tier: str,
        table: str,
        source_row_id: str | int,
        new_row_id: str | int,
    ) -> None:
        self._write(
            {
                "injector": injector,
                "tier": tier,
                "action": "duplicate_row",
                "table": table,
                "source_row_id": source_row_id,
                "new_row_id": new_row_id,
            }
        )

    def _write(self, record: dict) -> None:
        self._file.write(json.dumps(record, sort_keys=True) + "\n")
        self._counts[(record["injector"], record["table"])] += 1

    def close(self) -> dict:
        self._file.close()
        return dict(self._counts)


def write_summary(counts: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_injector: Counter = Counter()
    by_table: Counter = Counter()
    detail = []
    for (injector, table), count in sorted(counts.items()):
        by_injector[injector] += count
        by_table[table] += count
        detail.append({"injector": injector, "table": table, "count": count})

    summary = {
        "total_changes": sum(counts.values()),
        "by_injector": dict(sorted(by_injector.items())),
        "by_table": dict(sorted(by_table.items())),
        "detail": detail,
    }
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

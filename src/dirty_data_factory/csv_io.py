"""stdlib-csv read/write for the pipeline's in-memory table representation.

Using stdlib csv rather than pandas/polars is deliberate: it gives full
control over quoting and value formatting and never silently reformats a
cell the pipeline didn't touch. Untouched cells are preserved value-for-value
(not necessarily byte-identical at the file level — e.g. csv.QUOTE_MINIMAL
may quote a field slightly differently than Synthea's own writer did), which
is enough: this repo doesn't treat byte-for-byte reproducibility as a goal.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from dirty_data_factory.catalogue import ALL_TABLES


@dataclass
class Table:
    name: str
    fieldnames: list[str]
    rows: list[dict[str, str]]


def read_table(name: str, path: Path) -> Table:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return Table(name=name, fieldnames=fieldnames, rows=rows)


def write_table(table: Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=table.fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(table.rows)


def resolve_clean_input(input_dir: Path) -> tuple[Path, str | None]:
    """Accepts either a directory of CSVs directly (test fixtures, explicit
    --input overrides) or a `clean_input`-style root containing one dated
    batch subfolder per run (e.g. `2026-09-01/csv/`) — the real layout
    `synthea/run.sh` produces. Picks the most recent batch by folder name,
    since ISO dates sort lexicographically.

    Returns `(csv_dir, batch_label)`. `batch_label` is the batch folder's
    name (e.g. `"2026-09-01"`) when one was resolved, or `None` when
    `input_dir` was already a flat CSV directory with no batch concept —
    the caller uses this to decide whether the output should be batch-dated
    too.
    """
    if (input_dir / "patients.csv").exists():
        return input_dir, None
    batch_dirs = sorted(p for p in input_dir.iterdir() if p.is_dir() and (p / "csv").is_dir())
    if not batch_dirs:
        raise FileNotFoundError(f"no batch CSV data found under {input_dir}")
    latest = batch_dirs[-1]
    return latest / "csv", latest.name


def load_all_tables(csv_dir: Path) -> dict[str, Table]:
    tables = {}
    for name in ALL_TABLES:
        path = csv_dir / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"expected input file not found: {path}")
        tables[name] = read_table(name, path)
    return tables


def write_all_tables(tables: dict[str, Table], output_dir: Path) -> None:
    csv_dir = output_dir / "csv"
    for table in tables.values():
        write_table(table, csv_dir / f"{table.name}.csv")

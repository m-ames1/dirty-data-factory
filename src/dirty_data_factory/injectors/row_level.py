"""Row-level injectors: missing values, typos, duplicates, formatting,
type mismatches, date issues. Each mutates `tables` in place and records
every change it makes to `manifest`.
"""

import random
import re

from dirty_data_factory.catalogue import (
    DATE_FORMAT_TARGETS,
    DATE_ISSUE_TARGETS,
    DUPLICATE_TARGET_TABLES,
    KEYED_TABLES,
    MISSING_VALUE_TARGETS,
    NUMBER_FORMAT_TARGETS,
    TYPE_MISMATCH_TARGETS,
    TYPO_TARGETS,
)
from dirty_data_factory.config import InjectorConfig
from dirty_data_factory.csv_io import Table
from dirty_data_factory.manifest import ManifestWriter, row_id_for

TIER = "row"

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(.*)$")

_TYPO_ALPHABET = "abcdefghijklmnopqrstuvwxyz"

_STRAY_STRINGS = ("N/A", "unknown", "--", "null", "TBD")


def _edit_targets(
    tables: dict[str, Table],
    targets: dict[str, list[str]],
    cfg: InjectorConfig,
    rng: random.Random,
    manifest: ManifestWriter,
    injector: str,
    transform,
) -> None:
    """Shared driver: for each configured (table, column), roll the rate
    against every currently-populated cell and apply `transform` on a hit.
    `transform(value, rng) -> str | None` returns the new value, or None to
    skip this particular cell (e.g. a value that doesn't match the expected
    shape).
    """
    for table_name, columns in targets.items():
        table = tables.get(table_name)
        if table is None:
            continue
        for column in columns:
            if column not in table.fieldnames:
                continue
            rate = cfg.rate_for(table_name, column)
            for line_index, row in enumerate(table.rows):
                original = row.get(column, "")
                if original == "":
                    continue
                if rng.random() >= rate:
                    continue
                new_value = transform(original, rng)
                if new_value is None or new_value == original:
                    continue
                row[column] = new_value
                manifest.record_edit(
                    injector=injector,
                    tier=TIER,
                    table=table_name,
                    row_id=row_id_for(table_name, row, line_index),
                    column=column,
                    original=original,
                    new=new_value,
                )


def apply_missing_values(
    tables: dict[str, Table], cfg: InjectorConfig, rng: random.Random, manifest: ManifestWriter
) -> None:
    _edit_targets(
        tables, MISSING_VALUE_TARGETS, cfg, rng, manifest, "missing_values", lambda v, r: ""
    )


def _corrupt_typo(value: str, rng: random.Random) -> str | None:
    if len(value) < 2:
        return None
    chars = list(value)
    kind = rng.choice(("transpose", "substitute", "case", "whitespace"))
    if kind == "transpose":
        i = rng.randrange(len(chars) - 1)
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
    elif kind == "substitute":
        i = rng.randrange(len(chars))
        chars[i] = rng.choice(_TYPO_ALPHABET)
    elif kind == "case":
        i = rng.randrange(len(chars))
        chars[i] = chars[i].swapcase()
    else:  # whitespace
        i = rng.randrange(len(chars) + 1)
        chars.insert(i, " ")
    return "".join(chars)


def apply_typos(
    tables: dict[str, Table], cfg: InjectorConfig, rng: random.Random, manifest: ManifestWriter
) -> None:
    _edit_targets(tables, TYPO_TARGETS, cfg, rng, manifest, "typos", _corrupt_typo)


def _reformat_date(value: str, rng: random.Random) -> str | None:
    match = _ISO_DATE.match(value)
    if not match:
        return None
    year, month, day, suffix = match.groups()
    variant = rng.choice(("us", "eu", "dot"))
    if variant == "us":
        return f"{month}/{day}/{year}{suffix}"
    if variant == "eu":
        return f"{day}/{month}/{year}{suffix}"
    return f"{year}.{month}.{day}{suffix}"


def _reformat_number(value: str, rng: random.Random) -> str | None:
    try:
        number = float(value)
    except ValueError:
        return None
    variant = rng.choice(("comma", "no_decimal", "extra_zero"))
    if variant == "comma":
        return f"{number:,.2f}"
    if variant == "no_decimal":
        return str(int(round(number)))
    return f"{number:.4f}"


def apply_formatting(
    tables: dict[str, Table], cfg: InjectorConfig, rng: random.Random, manifest: ManifestWriter
) -> None:
    _edit_targets(tables, DATE_FORMAT_TARGETS, cfg, rng, manifest, "formatting", _reformat_date)
    _edit_targets(tables, NUMBER_FORMAT_TARGETS, cfg, rng, manifest, "formatting", _reformat_number)


def _mismatch_type(value: str, rng: random.Random) -> str | None:
    try:
        float(value)
    except ValueError:
        return None
    return rng.choice(_STRAY_STRINGS)


def apply_type_mismatch(
    tables: dict[str, Table], cfg: InjectorConfig, rng: random.Random, manifest: ManifestWriter
) -> None:
    _edit_targets(
        tables, TYPE_MISMATCH_TARGETS, cfg, rng, manifest, "type_mismatch", _mismatch_type
    )


def _break_date(value: str, rng: random.Random) -> str | None:
    match = _ISO_DATE.match(value)
    if not match:
        return None
    year, month, day, suffix = match.groups()
    mutation = rng.choice(("bad_day", "bad_month", "two_digit_year"))
    if mutation == "bad_day":
        return f"{year}-{month}-31{suffix}"
    if mutation == "bad_month":
        return f"{year}-13-{day}{suffix}"
    return f"{year[2:]}-{month}-{day}{suffix}"


def apply_date_issues(
    tables: dict[str, Table], cfg: InjectorConfig, rng: random.Random, manifest: ManifestWriter
) -> None:
    _edit_targets(tables, DATE_ISSUE_TARGETS, cfg, rng, manifest, "date_issues", _break_date)


def apply_duplicates(
    tables: dict[str, Table], cfg: InjectorConfig, rng: random.Random, manifest: ManifestWriter
) -> None:
    for table_name in DUPLICATE_TARGET_TABLES:
        table = tables.get(table_name)
        if table is None:
            continue
        rate = cfg.rate_for(table_name)
        key_column = KEYED_TABLES.get(table_name)
        # Snapshot the original rows so duplicates don't get duplicated again.
        for line_index, row in enumerate(list(table.rows)):
            if rng.random() >= rate:
                continue
            source_row_id = row_id_for(table_name, row, line_index)
            new_row = dict(row)
            table.rows.append(new_row)
            new_row_id = (
                row[key_column]
                if key_column
                else row_id_for(table_name, new_row, len(table.rows) - 1)
            )
            manifest.record_duplicate_row(
                injector="duplicates",
                tier=TIER,
                table=table_name,
                source_row_id=source_row_id,
                new_row_id=new_row_id,
            )


INJECTORS = {
    "missing_values": apply_missing_values,
    "typos": apply_typos,
    "duplicates": apply_duplicates,
    "formatting": apply_formatting,
    "type_mismatch": apply_type_mismatch,
    "date_issues": apply_date_issues,
}

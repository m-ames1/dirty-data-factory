"""Loads and validates injection_config.toml."""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROW_LEVEL_INJECTORS = (
    "missing_values",
    "typos",
    "duplicates",
    "formatting",
    "type_mismatch",
    "date_issues",
)
JOIN_BREAKING_INJECTORS = (
    "orphan_fk",
    "key_format_drift",
    "cardinality_break",
)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class InjectorConfig:
    enabled: bool
    rate: float
    # "table.column" -> rate, overriding the injector's default rate for
    # that one target.
    overrides: dict[str, float] = field(default_factory=dict)

    def rate_for(self, table: str, column: str | None = None) -> float:
        key = f"{table}.{column}" if column else table
        return self.overrides.get(key, self.rate)


@dataclass(frozen=True)
class Config:
    seed: int
    input_dir: Path
    output_dir: Path
    withhold_manifest: bool
    row_level: dict[str, InjectorConfig]
    join_breaking: dict[str, InjectorConfig]


def _validate_rate(rate: object, where: str) -> float:
    if not isinstance(rate, int | float) or isinstance(rate, bool):
        raise ConfigError(f"{where}: rate must be a number, got {rate!r}")
    if not 0.0 <= rate <= 1.0:
        raise ConfigError(f"{where}: rate must be between 0 and 1, got {rate}")
    return float(rate)


def _load_injector_section(
    raw: dict, names: tuple[str, ...], section: str
) -> dict[str, InjectorConfig]:
    section_raw = raw.get(section, {})
    default_rate = _validate_rate(section_raw.get("default_rate", 0.02), f"{section}.default_rate")
    result: dict[str, InjectorConfig] = {}
    for name in names:
        entry = section_raw.get(name, {})
        if not isinstance(entry, dict):
            raise ConfigError(f"{section}.{name} must be a table")
        enabled = bool(entry.get("enabled", True))
        rate = _validate_rate(entry.get("rate", default_rate), f"{section}.{name}.rate")
        overrides_raw = entry.get("overrides", {})
        if not isinstance(overrides_raw, dict):
            raise ConfigError(f"{section}.{name}.overrides must be a table")
        overrides = {
            key: _validate_rate(value, f"{section}.{name}.overrides.{key}")
            for key, value in overrides_raw.items()
        }
        result[name] = InjectorConfig(enabled=enabled, rate=rate, overrides=overrides)

    unknown = set(section_raw) - {"default_rate", *names}
    if unknown:
        raise ConfigError(f"{section}: unknown injector(s) {sorted(unknown)}")
    return result


def load_config(path: Path, *, repo_root: Path) -> Config:
    with path.open("rb") as f:
        raw = tomllib.load(f)

    run_raw = raw.get("run", {})
    if "seed" not in run_raw:
        raise ConfigError("run.seed is required")
    seed = run_raw["seed"]
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ConfigError(f"run.seed must be an integer, got {seed!r}")

    input_dir = repo_root / run_raw.get("input_dir", "data/poc/clean_input")
    output_dir = repo_root / run_raw.get("output_dir", "data/poc/dirty_output")
    withhold_manifest = bool(run_raw.get("withhold_manifest", False))

    row_level = _load_injector_section(raw, ROW_LEVEL_INJECTORS, "row_level")
    join_breaking = _load_injector_section(raw, JOIN_BREAKING_INJECTORS, "join_breaking")

    return Config(
        seed=seed,
        input_dir=input_dir,
        output_dir=output_dir,
        withhold_manifest=withhold_manifest,
        row_level=row_level,
        join_breaking=join_breaking,
    )

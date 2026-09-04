from pathlib import Path

import pytest

from dirty_data_factory.config import ConfigError, load_config


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "injection_config.toml"
    path.write_text(text)
    return path


def test_loads_minimal_config(tmp_path):
    config = load_config(_write(tmp_path, "[run]\nseed = 1\n"), repo_root=tmp_path)
    assert config.seed == 1
    assert config.row_level["missing_values"].enabled is True
    assert config.join_breaking["orphan_fk"].enabled is True


def test_missing_seed_raises(tmp_path):
    with pytest.raises(ConfigError, match="seed"):
        load_config(_write(tmp_path, "[run]\n"), repo_root=tmp_path)


def test_rate_out_of_range_raises(tmp_path):
    text = "[run]\nseed = 1\n[row_level.typos]\nrate = 1.5\n"
    with pytest.raises(ConfigError, match="rate"):
        load_config(_write(tmp_path, text), repo_root=tmp_path)


def test_unknown_injector_raises(tmp_path):
    text = "[run]\nseed = 1\n[row_level.not_a_real_injector]\nrate = 0.1\n"
    with pytest.raises(ConfigError, match="unknown"):
        load_config(_write(tmp_path, text), repo_root=tmp_path)


def test_per_target_override_applies(tmp_path):
    text = (
        "[run]\nseed = 1\n"
        "[row_level.missing_values]\nrate = 0.1\n"
        '[row_level.missing_values.overrides]\n"patients.MARITAL" = 0.9\n'
    )
    config = load_config(_write(tmp_path, text), repo_root=tmp_path)
    cfg = config.row_level["missing_values"]
    assert cfg.rate_for("patients", "MARITAL") == 0.9
    assert cfg.rate_for("patients", "RACE") == 0.1

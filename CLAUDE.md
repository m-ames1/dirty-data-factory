# Dirty Data Factory

Generates synthetic dirty healthcare data: clean data from Synthea, run through a
Python error-injection pipeline, producing the bronze-layer input for a separate
downstream project, Project Hadur (its Airflow POC in particular — see `data/*/poc/`).

## Pipeline

1. **Synthea** (Java, Docker) — generates clean synthetic patient data. Pinned to
   tag `v4.0.0` and JDK 17 in `synthea/Dockerfile`. Never install/run Synthea
   outside Docker — the whole point is that the build+run environment is fixed.
2. **Python error injection** (`src/dirty_data_factory/`) — takes clean data and
   deliberately introduces data quality issues. Not yet designed/implemented.

Both stages must be deterministic and seeded so the pipeline is fully reproducible
end to end. Never hand-edit generated output in `data/` — if the data needs to
change, change the generation parameters/code and regenerate.

## Commands

```
./synthea/run.sh              # regenerate data/clean/poc/ via Dockerized Synthea
uv sync                       # install Python deps
uv run pytest                 # run tests
uv run ruff check .           # lint
uv run ruff format .          # format
```

## Repo structure

- `synthea/` — Dockerfile + run script for the pinned Synthea build.
- `src/dirty_data_factory/` — Python error-injection package.
- `tests/` — Python tests (pytest).
- `pyproject.toml` / `uv.lock` — Python project manifest and lockfile (`uv`).
- `data/clean/poc/` — Synthea output, committed (small POC dataset).
- `data/dirty/poc/` — error-injected output, committed (small POC dataset).
- `.github/workflows/ci.yml` — lints and tests the Python package on every push/PR.
- `.github/workflows/synthea.yml` — regenerates `data/clean/poc/` and fails if it
  doesn't match what's committed, to catch non-determinism.

`data/clean/` and `data/dirty/` are committed directly for POC-sized datasets,
alongside the seeds/scripts/config that regenerate them identically. If a dataset
stops being POC-sized, that's a signal to introduce Git LFS or DVC rather than
keep committing raw files — don't do this preemptively.

## Conventions

- All data generation must be seeded and version-pinned. If you add a source of
  randomness anywhere in the pipeline (Synthea args, Python error injection), it
  must take an explicit seed — no unseeded randomness.
- Changing the pinned Synthea version (`SYNTHEA_REF` in `synthea/Dockerfile`) or
  any generation parameter in `synthea/run.sh` invalidates previously-generated
  data — regenerate and note the change in the README, don't silently drift.
- This is synthetic data only — never add real patient data (PHI) to this repo,
  even for testing.
- Python: `uv` for deps, `ruff` for lint/format, `pytest` for tests. Keep the
  error-injection logic itself in `src/dirty_data_factory/`, not in ad hoc scripts.

# Dirty Data Factory

Generates synthetic "dirty" healthcare data: realistic data quality issues injected
into clean, synthetically-generated patient records. The output is the bronze-layer
raw dataset consumed by [Project Hadur](#relationship-to-project-hadur).

## Pipeline

```
Synthea (Java, Dockerized, pinned version)
    -> clean synthetic healthcare data  (data/clean_input/)
    -> Python error-injection pipeline  (src/dirty_data_factory/)
    -> dirty healthcare data            (data/dirty_output/)  <- bronze input for Project Hadur
```

Both stages are deterministic and seeded: the Synthea stage is pinned to an
exact version and seed via Docker, and the Python stage will be seeded the same way
once it exists. Anyone cloning this repo should be able to regenerate ~98%
byte-identical output at the Synthea stage (see "Generating the clean data" below
for why it isn't exact).

The first dataset in this repo (`*/poc/`) is a small dataset for Project Hadur's
Airflow proof-of-concept — not the full-scale dataset.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) — runs the pinned Synthea build, no
  local Java install needed.
- [uv](https://docs.astral-sh.org/uv/) — Python dependency management for the
  error-injection code.

## Generating the clean data (Synthea)

```
./synthea/run.sh
```

This builds a Docker image pinned to Synthea `v4.0.0` and JDK 17, then runs it
with fixed seeds/population/state (see `synthea/run.sh` for the exact
parameters) into `data/clean_input/poc/`. Re-running it reproduces ~98%
byte-identical output — Synthea has at least one internal randomness source
not covered by its documented seed flags, so a small percentage of patient
records may differ by a day in BIRTHDATE between runs. This is a known
Synthea limitation, not something this repo's scripts control.

## Generating the dirty data (Python)

```
uv sync
uv run pytest
uv run ruff check .
```

The error-injection pipeline itself (`src/dirty_data_factory/`) is still being
designed — this section will be filled in once it exists.

## Repo structure

```
synthea/            Dockerfile + run script for the pinned Synthea build
src/dirty_data_factory/   Python error-injection code
tests/               Python tests
data/clean_input/    Synthea output (committed for the POC dataset)
data/dirty_output/   Error-injected output (committed for the POC dataset)
```

Both `data/clean_input/` and `data/dirty_output/` are committed directly for the POC dataset
(they're small), alongside the scripts/seeds needed to regenerate them from
scratch. If datasets grow beyond POC size in later phases, revisit with Git LFS
or DVC instead of raw commits.

## Relationship to Project Hadur

This repo only produces data — it doesn't consume it. Project Hadur is a separate project
whose Airflow POC ingests the dirty dataset produced here as its bronze-layer raw input.

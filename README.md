# Dirty Data Factory

Generates synthetic "dirty" healthcare data: realistic data quality issues injected
into clean, synthetically-generated patient records. The output is the bronze-layer
raw dataset consumed by [Project Hadur](#relationship-to-project-hadur).

## Pipeline

```
Synthea (Java, Dockerized, pinned version)
    -> clean synthetic healthcare data  (data/clean/)
    -> Python error-injection pipeline  (src/dirty_data_factory/)
    -> dirty healthcare data            (data/dirty/)  <- bronze input for Project Hadur
```

Both stages are deterministic and reproducible: the Synthea stage is pinned to an
exact version and seed via Docker, and the Python stage will be seeded the same way
once it exists. Anyone cloning this repo should be able to regenerate byte-identical
output at either stage.

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

This builds a Docker image pinned to Synthea `v4.0.0` and JDK 17, then runs it with
a fixed seed/population/state (see `synthea/run.sh` for the exact parameters) into
`data/clean/poc/`. Re-running it reproduces the same output, because both the
Synthea version and the generation parameters are pinned in that script.

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
data/clean/          Synthea output (committed for the POC dataset)
data/dirty/          Error-injected output (committed for the POC dataset)
```

Both `data/clean/` and `data/dirty/` are committed directly for the POC dataset
(they're small), alongside the scripts/seeds needed to regenerate them from
scratch. If datasets grow beyond POC size in later phases, revisit with Git LFS
or DVC instead of raw commits.

## Relationship to Project Hadur

This repo only produces data — it doesn't consume it. Project Hadur is a separate project
whose Airflow POC ingests the dirty dataset produced here as its bronze-layer raw input.

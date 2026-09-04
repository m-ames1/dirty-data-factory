# Dirty Data Factory

Generates synthetic "dirty" healthcare data: realistic data quality issues injected
into clean, synthetically-generated patient records. The output is the bronze-layer
raw dataset consumed by [Project Hadur](#relationship-to-project-hadur).

## Pipeline

```
Synthea (Java, Dockerized, pinned version)
    -> clean synthetic healthcare data  (data/poc/clean_input/)
    -> Python error-injection pipeline  (src/dirty_data_factory/)
    -> dirty healthcare data            (data/poc/dirty_output/)  <- bronze input for Project Hadur
```

Both stages are seeded and version-pinned for intentional, controlled
generation — the Synthea stage via Docker, and the Python stage the same way
once it exists. This is about controlling *what the data looks like*, not
about reproducing a specific prior run byte-for-byte: every regeneration is
its own new batch (see "Generating the clean data" below).

The first dataset in this repo (`data/poc/`) is a small dataset for Project Hadur's
Airflow proof-of-concept — not the full-scale dataset.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) — runs the pinned Synthea build, no
  local Java install needed.
- [uv](https://docs.astral-sh.org/uv/) — Python dependency management for the
  error-injection code.
- [jq](https://jqlang.org/) — used by `synthea/run.sh` to add the batch date to
  Synthea's metadata JSON after each run.

## Generating the clean data (Synthea)

```
./synthea/run.sh
```

This builds a Docker image pinned to Synthea `v4.0.0` and JDK 17, then runs it
with fixed seeds/population/state (see `synthea/run.sh` for the exact
parameters) into `data/poc/clean_input/<BATCH_DATE>/`. Re-running it is not
expected to reproduce a previous run's exact output — Synthea's generation is
sensitive to wall-clock time and has internal randomness not fully covered by
its seed flags. That's fine: every run is its own new batch, not a replay of
an old one, and there's no check anywhere expecting byte-for-byte matches.

Synthea also writes a per-run metadata JSON manifest to `data/poc/clean_input/<BATCH_DATE>/metadata/`
(runID, seed, patient/provider counts, etc.) — this is Synthea's own CSV exporter
behavior, not something this repo adds. `synthea/run.sh` adds one more field to it,
`batchDate`, which identifies which business batch this data belongs to. This is
distinct from the manifest's own `runStartTime` — `runStartTime` is when Synthea
actually executed; `batchDate` is a business date that doesn't have to match (the
POC dataset's `batchDate` is `2026-09-01`, treating it as one historical batch,
regardless of when it was actually generated). The CSVs themselves aren't touched —
turning `batchDate` into a `batch_id` column on ingested rows is Project Hadur's
bronze-layer ingestion responsibility, not this repo's (see "Relationship to
Project Hadur" below).

`BATCH_DATE` defaults to today (`./synthea/run.sh`), giving each day's run its own
folder. If a folder for today already exists, the script won't overwrite it — it
prompts (interactively) or exits with an error (non-interactively, e.g. CI) telling
you to pick a different date. To target a specific batch date instead — including
re-running the *same* date deliberately, which overwrites that batch's folder, the
normal way to iterate on a not-yet-finalized batch — pass it explicitly:
`BATCH_DATE=2026-10-01 ./synthea/run.sh`.

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
data/poc/clean_input/    Synthea output, one dated subfolder per batch (e.g. 2026-09-01/csv/, 2026-09-01/metadata/)
data/poc/dirty_output/   Error-injected output (committed for the POC dataset)
```

Both `data/poc/clean_input/` and `data/poc/dirty_output/` are committed directly for
the POC dataset (they're small enough to fit GitHub's size limits), alongside
the scripts/seeds needed to regenerate them from scratch. Full-scale datasets
will not be pushed to Git — they're regenerated locally instead. Revisit with
Git LFS or DVC only if that local-regeneration workflow stops being enough.

## Relationship to Project Hadur

This repo only produces data — it doesn't consume it. Project Hadur is a separate project
whose Airflow POC ingests the dirty dataset produced here as its bronze-layer raw input.

# Dirty Data Factory

Generates synthetic dirty healthcare data: clean data from Synthea, run through a
Python error-injection pipeline, producing the bronze-layer input for a separate
downstream project, Project Hadur (its Airflow POC in particular — see `data/poc/`).

## Pipeline

1. **Synthea** (Java, Docker) — generates clean synthetic patient data. Pinned to
   tag `v4.0.0` and JDK 17 in `synthea/Dockerfile`. Never install/run Synthea
   outside Docker — the whole point is that the build+run environment is fixed.
   Synthea's CSV exporter also writes a per-run metadata JSON manifest (not
   something this repo adds); `synthea/run.sh` adds a `batchDate` field to it
   (a business batch date, independent of the manifest's own `runStartTime`).
   Turning that into a `batch_id` column on rows is Project Hadur's
   ingestion-time responsibility, not this repo's — the CSVs stay untouched.
2. **Python error injection** (`src/dirty_data_factory/`) — takes clean data and
   deliberately introduces data quality issues. Not yet designed/implemented.

Both stages must be seeded and version-pinned for intentional, controlled
generation (see Conventions) — not for exact reproducibility across runs.
There is no check anywhere that expects two runs to match byte-for-byte.
Never hand-edit generated output in `data/` — if the data needs to change,
change the generation parameters/code and regenerate.

## Commands

```
./synthea/run.sh              # regenerate data/poc/clean_input/ via Dockerized Synthea
uv sync                       # install Python deps
uv run pytest                 # run tests
uv run ruff check .           # lint
uv run ruff format .          # format (CI runs the --check form; this fixes what it flags)
```

## Repo structure

- `synthea/` — Dockerfile + run script for the pinned Synthea build.
- `src/dirty_data_factory/` — Python error-injection package.
- `tests/` — Python tests (pytest).
- `pyproject.toml` / `uv.lock` — Python project manifest and lockfile (`uv`).
- `data/poc/clean_input/` — Synthea output, committed (small POC dataset); one dated
  subfolder per batch, e.g. `2026-09-01/csv/`, `2026-09-01/metadata/`.
- `data/poc/dirty_output/` — error-injected output, committed (small POC dataset); same
  per-batch dated subfolder as its source, e.g. `2026-09-01/csv/`, plus that batch's
  `manifest.jsonl` (every injected change) and `manifest_summary.json`.
- `.github/workflows/ci.yml` — lints and tests the Python package on every push/PR.
- `.github/pull_request_template.md` — checklist prefilled into the body of every new PR.

`data/poc/clean_input/` and `data/poc/dirty_output/` are committed directly for POC-sized
datasets, alongside the seeds/scripts/config that regenerate them identically —
as long as they fit within GitHub's file/repo size limits. Full-scale datasets
will not be pushed to Git at all; they're regenerated locally via the same
seeds/scripts instead. If that becomes a recurring need, that's the signal to
introduce Git LFS or DVC — don't do this preemptively.

## Conventions

- All data generation must be seeded and version-pinned. If you add a source of
  randomness anywhere in the pipeline (Synthea args, Python error injection), it
  must take an explicit seed — no unseeded randomness.
- Changing the pinned Synthea version (`SYNTHEA_REF` in `synthea/Dockerfile`) or
  any generation parameter in `synthea/run.sh` invalidates previously-generated
  data — regenerate and note the change in the README, don't silently drift.
- This is synthetic data only — never add real patient data (PHI) to this repo,
  even for testing.
- Synthea must export CSV only, never FHIR — FHIR JSON is deeply nested and
  roughly 100x larger for no analytical benefit here; CSV's flat/tabular shape
  is what the Python error-injection stage and Project Hadur's ingestion
  actually need. Enforced via `--exporter.csv.export=true`/`--exporter.fhir.export=false`
  (and the hospital/practitioner FHIR variants) in `synthea/run.sh`.
- Synthea's generation isn't exactly reproducible run-to-run, even with the
  same seed — it's sensitive to wall-clock time (reference/end date defaults
  to "today") and has at least one internal RNG source not covered by its
  documented seed flags. This is expected, not a bug: reproducing a specific
  prior run isn't a goal — there is no CI check (or anything else) that
  expects it.
- Python: `uv` for deps, `ruff` for lint/format, `pytest` for tests. Keep the
  error-injection logic itself in `src/dirty_data_factory/`, not in ad hoc scripts.

## Before committing

Always scan the staged diff for personal or sensitive content before every
`git commit` — no exceptions. Pay special attention to notes added to tracked
files like `CLAUDE.md`, not just `.env`/credentials. Flag findings before
committing, not after. In an automated commit flow, stop and have the user review.

#!/usr/bin/env bash
# Regenerates the POC "clean" dataset via Dockerized Synthea.
#
# These parameters (seed, clinician seed, population, state) define the POC
# dataset. Change them here if you need a different dataset.
#
# Reproducibility: -s/-cs pin Synthea's two documented seeds, and
# --generate.thread_pool_size=1 forces single-threaded generation to avoid
# non-deterministic write ordering. Even so, re-running with identical
# parameters produces output that's only ~98% byte-identical, not exact —
# Synthea has at least one internal RNG source not covered by either seed,
# which can shift a small percentage of patients' BIRTHDATE by a day and
# cascade into tiny floating-point differences in payer cost aggregates.
# This is a known Synthea limitation, not a bug in this script.
set -euo pipefail

SEED=42
CLINICIAN_SEED=42
POPULATION=100
STATE="New York"

SYNTHEA_REF="v4.0.0"
IMAGE_TAG="dirty-data-factory-synthea:${SYNTHEA_REF}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/data/poc/clean_input"

docker build --build-arg "SYNTHEA_REF=${SYNTHEA_REF}" -t "${IMAGE_TAG}" "${SCRIPT_DIR}"

mkdir -p "${OUTPUT_DIR}"

docker run --rm \
  -v "${OUTPUT_DIR}:/synthea/output" \
  "${IMAGE_TAG}" \
  -s "${SEED}" -cs "${CLINICIAN_SEED}" -p "${POPULATION}" "${STATE}" \
  --exporter.csv.export=true \
  --exporter.fhir.export=false \
  --exporter.hospital.fhir.export=false \
  --exporter.practitioner.fhir.export=false \
  --exporter.csv.excluded_files=patient_expenses.csv \
  --generate.thread_pool_size=1

echo "Clean POC data written to ${OUTPUT_DIR}"

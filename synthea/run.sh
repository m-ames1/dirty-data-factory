#!/usr/bin/env bash
# Regenerates the POC "clean" dataset via Dockerized Synthea.
#
# These parameters (seed, clinician seed, population, state) define the POC
# dataset. Change them here if you need a different dataset. BATCH_DATE is
# separate — see the comment further down — it identifies which batch a run
# belongs to, not what the data looks like, and is meant to change per run.
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
CLEAN_INPUT_DIR="${REPO_ROOT}/data/poc/clean_input"

# BATCH_DATE identifies which batch this run belongs to — independent of the
# generation params above, and expected to change on every real run (unlike
# SEED/POPULATION/STATE, which define the dataset itself). Defaults to today;
# pass it explicitly (BATCH_DATE=YYYY-MM-DD ./synthea/run.sh) to target a
# specific/historical batch instead — an explicit value always wins, even if
# that batch's folder already exists (re-running the same batch date is how
# you iterate on a not-yet-finalized batch).
if [ -z "${BATCH_DATE:-}" ]; then
  BATCH_DATE="$(date -u +%Y-%m-%d)"
  if [ -d "${CLEAN_INPUT_DIR}/${BATCH_DATE}" ]; then
    echo "A batch folder already exists for today (${CLEAN_INPUT_DIR}/${BATCH_DATE})." >&2
    if [ -t 0 ]; then
      NEW_DATE=""
      while [ -z "${NEW_DATE}" ] || [ -d "${CLEAN_INPUT_DIR}/${NEW_DATE}" ]; do
        read -r -p "Enter a different batch date (YYYY-MM-DD) with no existing folder: " NEW_DATE
      done
      BATCH_DATE="${NEW_DATE}"
    else
      echo "Not running interactively — pass BATCH_DATE=YYYY-MM-DD explicitly instead." >&2
      exit 1
    fi
  fi
fi

OUTPUT_DIR="${CLEAN_INPUT_DIR}/${BATCH_DATE}"

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

METADATA_FILE="$(ls -t "${OUTPUT_DIR}/metadata"/*.json | head -n1)"
jq --arg batch_date "${BATCH_DATE}" '. + {batchDate: $batch_date}' \
  "${METADATA_FILE}" > "${METADATA_FILE}.tmp" && mv "${METADATA_FILE}.tmp" "${METADATA_FILE}"

echo "Clean POC data written to ${OUTPUT_DIR}"

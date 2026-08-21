#!/usr/bin/env bash
# Regenerates the POC "clean" dataset via Dockerized Synthea.
#
# These parameters (seed, population, state) define the POC dataset.
# Change them here if you need a different dataset — running this script
# again with the same values reproduces byte-identical output.
set -euo pipefail

SEED=42
POPULATION=100
STATE="New York"

SYNTHEA_REF="v4.0.0"
IMAGE_TAG="dirty-data-factory-synthea:${SYNTHEA_REF}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${REPO_ROOT}/data/clean/poc"

docker build --build-arg "SYNTHEA_REF=${SYNTHEA_REF}" -t "${IMAGE_TAG}" "${SCRIPT_DIR}"

mkdir -p "${OUTPUT_DIR}"

docker run --rm \
  -v "${OUTPUT_DIR}:/synthea/output" \
  "${IMAGE_TAG}" \
  -s "${SEED}" -p "${POPULATION}" "${STATE}"

echo "Clean POC data written to ${OUTPUT_DIR}"

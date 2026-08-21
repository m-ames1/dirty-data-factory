# Builds and runs a pinned version of Synthea (https://github.com/synthetichealth/synthea)
# so that "clean" synthetic healthcare data is ~98% byte-identical (see
# synthea/run.sh for why it isn't exact) for anyone who builds this image,
# regardless of what JDK (if any) they have installed locally.
#
# Build:
#   docker build -t dirty-data-factory-synthea:v4.0.0 synthea/
#
# Run (generates patients into ./output inside the container — mount a host
# directory there to capture the result, see synthea/run.sh):
#   docker run --rm -v "$(pwd)/data/poc/clean_input:/synthea/output" \
#     dirty-data-factory-synthea:v4.0.0 -s 42 -p 100 Massachusetts

FROM eclipse-temurin:17-jdk-jammy

# Pinned to the v4.0.0 tag. Synthea's own docs state that "populations
# generated with the same seed and the same version of Synthea should be
# identical" — bump this only deliberately, and note the change in the README.
ARG SYNTHEA_REF=v4.0.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /synthea

RUN git clone --branch "${SYNTHEA_REF}" --depth 1 \
    https://github.com/synthetichealth/synthea.git . \
    && ./gradlew build -x test --no-daemon

ENTRYPOINT ["./run_synthea"]

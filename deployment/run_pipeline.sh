#!/bin/sh
set -eu

export RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"

echo "Starting Graph-to-Blob ingestion"
echo "RUN_ID=${RUN_ID}"

if [ "${UPLOAD_RESULTS_TO_BLOB:-}" != "true" ]; then
    echo "UPLOAD_RESULTS_TO_BLOB must be set to true" >&2
    exit 1
fi

cd /app/graphapi/src
python -m main

echo "Graph-to-Blob ingestion completed successfully"
echo "RUN_ID=${RUN_ID}"

# Step 2: register new bronze runs as cases and classify them.
# Off unless the job sets CLASSIFIER_ENABLED=true (it needs Cosmos, OpenAI and Document
# Intelligence settings, and about 2 GiB of memory for the customer registry).
# CLASSIFIER_PAUSED=true keeps registering cases but stops the model calls.
if [ "${CLASSIFIER_ENABLED:-false}" = "true" ]; then
    echo "Starting classifier"
    cd /app/AI_email_classifier
    python -m main
    echo "Classifier completed successfully"
else
    echo "Classifier step skipped (CLASSIFIER_ENABLED is not true)"
fi

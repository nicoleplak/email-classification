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
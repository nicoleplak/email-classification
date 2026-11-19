#!/bin/bash
# Azure settings for the job and the review app, kept in the repo so they can be re-applied and reviewed.
# The pipeline only swaps images; run this after the first deploy and whenever a setting here changes.
#
#   AZURE_OPENAI_API_KEY=... DOC_INTEL_API_KEY=... bash deployment/configure_azure.sh job
#   REVIEW_ACCESS_CODE=... bash deployment/configure_azure.sh app
#
# Secrets are read from the environment and stored as Container Apps secrets; they are never printed or
# written to a file. Re-running "app" without REVIEW_SESSION_SECRET signs every reviewer out once.
set -euo pipefail
export MSYS_NO_PATHCONV=1

SUB="${SUB:-doValue - Prod Envs}"
RG=LLM
JOB=caj-job-emclf-llm-gr
APP=ca-emclf-llm-gr
UAMI=id-email-classification-uat
COSMOS="https://cosmos-db-data-llm-dev.documents.azure.com:443/"
COSMOS_DB=EmailClassification
OPENAI="https://openai-data-llm.openai.azure.com/"
OPENAI_DEPLOYMENT=gpt-4.1-gs
OPENAI_VERSION=2024-12-01-preview
DOCINTEL="https://doc-intel-data-llm.cognitiveservices.azure.com/"

azq() { az "$@" --subscription "$SUB" --only-show-errors -o none; }

configure_job() {
  : "${AZURE_OPENAI_API_KEY:?set AZURE_OPENAI_API_KEY}" "${DOC_INTEL_API_KEY:?set DOC_INTEL_API_KEY}"
  # Ingest runs before this moment are an old backlog; imported runs (import-*) always register.
  local from="${REGISTER_RUNS_FROM:-$(date -u +%Y%m%dT%H%M%SZ)}"
  azq containerapp job secret set -n "$JOB" -g "$RG" \
    --secrets "azure-openai-api-key=$AZURE_OPENAI_API_KEY" "doc-intel-api-key=$DOC_INTEL_API_KEY"
  # 2 CPU / 4 GiB: the registry (~900k rows) is held in memory while classifying.
  azq containerapp job update -n "$JOB" -g "$RG" --cpu 2.0 --memory 4.0Gi --replica-timeout 3600 --parallelism 1 \
    --set-env-vars \
      CLASSIFIER_ENABLED=true CLASSIFIER_PAUSED=false CASE_STORE=cosmos \
      "COSMOS_ENDPOINT=$COSMOS" "COSMOS_DATABASE=$COSMOS_DB" \
      REGISTRY_SOURCE=csv REQUEST_HISTORY=true AUTO_ACCEPT_THRESHOLD=0.95 CLASSIFY_MAX_PER_RUN=50 \
      "REGISTER_RUNS_FROM=$from" \
      "AZURE_OPENAI_ENDPOINT=$OPENAI" "AZURE_OPENAI_DEPLOYMENT=$OPENAI_DEPLOYMENT" \
      "AZURE_OPENAI_API_VERSION=$OPENAI_VERSION" AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key \
      "DOC_INTEL_ENDPOINT=$DOCINTEL" DOC_INTEL_API_KEY=secretref:doc-intel-api-key
  bash "$(dirname "$0")/fetch_mode.sh" manual
  echo "Job configured. Classifier on; runs only when started by hand. REGISTER_RUNS_FROM=$from"
}

configure_app() {
  : "${REVIEW_ACCESS_CODE:?set REVIEW_ACCESS_CODE (12+ characters, handed to reviewers)}"
  [ "${#REVIEW_ACCESS_CODE}" -ge 12 ] || { echo "REVIEW_ACCESS_CODE must be 12+ characters" >&2; exit 2; }
  local session="${REVIEW_SESSION_SECRET:-$(python -c 'import secrets; print(secrets.token_hex(32))')}"
  local uami_id uami_client
  uami_id=$(az identity show -n "$UAMI" -g "$RG" --subscription "$SUB" --query id -o tsv)
  uami_client=$(az identity show -n "$UAMI" -g "$RG" --subscription "$SUB" --query clientId -o tsv)
  azq containerapp identity assign -n "$APP" -g "$RG" --user-assigned "$uami_id"
  azq containerapp secret set -n "$APP" -g "$RG" \
    --secrets "review-access-code=$REVIEW_ACCESS_CODE" "review-session-secret=$session"
  # Replaces the whole environment: the review app holds no mailbox secret and no AI keys.
  azq containerapp update -n "$APP" -g "$RG" --command python --args /app/review_app/server.py \
    --min-replicas 1 --max-replicas 1 \
    --replace-env-vars \
      REVIEW_AUTH=demo REVIEW_ACCESS_CODE=secretref:review-access-code \
      REVIEW_SESSION_SECRET=secretref:review-session-secret HOST=0.0.0.0 PORT=8000 \
      CASE_STORE=cosmos "COSMOS_ENDPOINT=$COSMOS" "COSMOS_DATABASE=$COSMOS_DB" \
      RESULT_STORAGE_ACCOUNT=datallmdev RESULT_CONTAINER=email-classification "AZURE_CLIENT_ID=$uami_client"
  azq containerapp ingress enable -n "$APP" -g "$RG" --type external --target-port 8000 --transport auto
  for secret in graph-client-secret azure-openai-api-key doc-intel-api-key; do
    azq containerapp secret remove -n "$APP" -g "$RG" --secret-names "$secret" 2>/dev/null || true
  done
  echo "Review app: https://$(az containerapp show -n "$APP" -g "$RG" --subscription "$SUB" \
    --query properties.configuration.ingress.fqdn -o tsv)"
}

case "${1:-}" in
  job) configure_job ;;
  app) configure_app ;;
  *) echo "usage: configure_azure.sh job | app" >&2; exit 2 ;;
esac

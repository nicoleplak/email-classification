#!/bin/bash
# Switch the ingest + classify job between manual and scheduled runs.
#
#   bash deployment/fetch_mode.sh manual                         # runs only when started by hand
#   bash deployment/fetch_mode.sh schedule "0 6,10,14 * * 1-5"   # cron, in UTC (08/12/16 Athens in winter)
#
# Manual run: Azure portal > caj-job-emclf-llm-gr > Run now, or
#   az containerapp job start -n caj-job-emclf-llm-gr -g LLM --subscription "doValue - Prod Envs"
#
# Why a script and not an environment variable: in Container Apps the trigger (manual or schedule) is a
# setting of the job itself. A variable inside the container cannot tell a scheduled start from a
# "Run now", so it could only skip both.
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows would rewrite /subscriptions/... into a file path

MODE="${1:?usage: fetch_mode.sh manual | schedule \"<cron in UTC>\"}"
JOB="${JOB:-caj-job-emclf-llm-gr}"
RG="${RG:-LLM}"
SUB="${SUB:-doValue - Prod Envs}"

case "$MODE" in
  manual)
    BODY='{"properties":{"configuration":{"triggerType":"Manual","scheduleTriggerConfig":null,
           "manualTriggerConfig":{"parallelism":1,"replicaCompletionCount":1}}}}' ;;
  schedule)
    CRON="${2:?give the cron expression, e.g. \"0 */4 * * *\"}"
    BODY="{\"properties\":{\"configuration\":{\"triggerType\":\"Schedule\",\"manualTriggerConfig\":null,
           \"scheduleTriggerConfig\":{\"cronExpression\":\"$CRON\",\"parallelism\":1,\"replicaCompletionCount\":1}}}}" ;;
  *) echo "MODE must be manual or schedule" >&2; exit 2 ;;
esac

ID=$(az containerapp job show -n "$JOB" -g "$RG" --subscription "$SUB" --query id -o tsv)
az rest --method patch --url "https://management.azure.com${ID}?api-version=2024-03-01" --body "$BODY" -o none
az containerapp job show -n "$JOB" -g "$RG" --subscription "$SUB" \
  --query "{job:name, trigger:properties.configuration.triggerType, cron:properties.configuration.scheduleTriggerConfig.cronExpression}" -o table

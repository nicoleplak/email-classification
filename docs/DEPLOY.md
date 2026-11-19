# Deploying the email classifier

One image (`email-classification:<build>`), two Azure resources, both in resource group `LLM`
(subscription *doValue - Prod Envs*):

| Resource | What it runs | Start command |
|---|---|---|
| Job `caj-job-emclf-llm-gr` | ingest from the mailbox, then the classifier | image default (`deployment/run_pipeline.sh`) |
| Container App `ca-emclf-llm-gr` | review app (page + API), exactly 1 replica | `python /app/review_app/server.py` |

Cases, reviews, audit, locks and users live in Cosmos `cosmos-db-data-llm-dev`, database `EmailClassification`.
Emails, attachments and classifier output live in storage `datallmdev`, container `email-classification`
(bronze / messages / attachments / silver; gold is for Qualco batches later).

## Branches

`feature/*` → `dev` (when the feature is done; delete the feature branch) → `main` (only to deploy).
The pipeline `pipelines/azure-pipelines.publish-deploy.yml` is started by hand from `main`.

## First deploy

1. Merge `dev` into `main`, push, run the **publish-deploy** pipeline. It builds the image and points both
   the app and the job at it. Nothing changes in behaviour yet: the app still runs its old command and the
   classifier is off by default (`CLASSIFIER_ENABLED=false`).
2. Review app settings (identity, secrets, command, ingress):
   `REVIEW_ACCESS_CODE=<12+ chars> bash deployment/configure_azure.sh app`
   Hand the access code to reviewers in person or through Teams, never by email.
3. Job settings (classifier on, 2 CPU / 4 GiB, manual trigger):
   `AZURE_OPENAI_API_KEY=... DOC_INTEL_API_KEY=... bash deployment/configure_azure.sh job`
4. Fetch and classify once: portal → `caj-job-emclf-llm-gr` → **Run now**.

## Fetching email: manual now, scheduled later

Kick-off is **manual only**. Start a run from the portal (**Run now**) or:

    az containerapp job start -n caj-job-emclf-llm-gr -g LLM --subscription "doValue - Prod Envs"

To switch to the agreed schedule (cron is in UTC; Athens is UTC+2 in winter, UTC+3 in summer):

    bash deployment/fetch_mode.sh schedule "0 6,10,14 * * 1-5"    # 08:00, 12:00, 16:00 Athens, weekdays (winter)
    bash deployment/fetch_mode.sh manual                           # back to manual

This is a job setting rather than an environment variable: Container Apps decides when a job starts, and the
container cannot tell a scheduled start from **Run now**.

## Settings

Job (`caj-job-emclf-llm-gr`, set by `configure_azure.sh job`; the ingest's own settings are untouched):

| Variable | Value | Meaning |
|---|---|---|
| `CLASSIFIER_ENABLED` | `true` | run the classifier after ingest |
| `CLASSIFIER_PAUSED` | `false` | `true`: still register new emails as cases, skip the model calls |
| `CASE_STORE`, `COSMOS_ENDPOINT`, `COSMOS_DATABASE` | `cosmos`, dev account, `EmailClassification` | where cases live (managed identity, no key) |
| `REGISTRY_SOURCE` | `csv` | newest `in/qualco_output_*.csv` (Synapse is unreachable; see FR-77/FR-130) |
| `REQUEST_HISTORY` | `true` | one scan of the newest `in/request_output_*.csv` per run (emails, past requests) |
| `AUTO_ACCEPT_THRESHOLD` | `0.95` | at or above, with nothing else wrong: AUTO; otherwise REVIEW |
| `CLASSIFY_MAX_PER_RUN` | `50` | cap per run; the rest wait for the next run |
| `REGISTER_RUNS_FROM` | deploy time (UTC) | older ingest runs are skipped; `import-*` runs always register |
| `AZURE_OPENAI_*`, `DOC_INTEL_*` | keys as secrets | model and OCR |

Review app (`ca-emclf-llm-gr`, set by `configure_azure.sh app`):

| Variable | Meaning |
|---|---|
| `REVIEW_AUTH=demo` | name + email + shared access code; each browser is its own user |
| `REVIEW_ACCESS_CODE` (secret) | the shared code |
| `REVIEW_SESSION_SECRET` (secret) | signs the browser cookie; changing it signs everyone out |
| `CASE_STORE`, `COSMOS_*`, `RESULT_STORAGE_ACCOUNT`, `RESULT_CONTAINER`, `AZURE_CLIENT_ID` | data access with the managed identity `id-email-classification-uat` |

The review app holds no mailbox secret and no AI keys.

## Importing emails by hand

Outlook `.msg` files (for example `test_data/`) go in with a local tool:

    pip install -r requirements/requirements-tools.txt
    python tools/import_msg.py test_data/

Then run the job (or `python -m main` locally) to classify them.

## Running locally

    # classifier against dev Azure: needs the variables above in your shell
    cd AI_email_classifier && python -m main
    # review app on http://127.0.0.1:8765 (no access code, local only)
    REVIEW_AUTH=dev python review_app/server.py
    # checks
    pytest && node tests/browser/review_ui_test.cjs http://127.0.0.1:8765

Locally, `AZURE_CLI_SUBSCRIPTION="doValue - Prod Envs"` makes the Cosmos client use your az login.

## Open items

- IT: *Storage Blob Data Contributor* for the developer's login on container `email-classification`
  (local work uses the account key until then).
- Entra sign-in: once a redirect URI exists, add `REVIEW_AUTH=entra`; users are matched to their demo
  records by email.
- `requirements/runtime/requirements-container.lock`: `azure-cosmos` was added by hand with its published
  hashes; regenerate with `pipelines/utilities/azure-pipelines.lock-generation.yml` when convenient.

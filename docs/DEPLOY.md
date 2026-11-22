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
3. Job settings (classifier on, 2 CPU / 4 GiB; the 4-hour schedule is kept):
   `AZURE_OPENAI_API_KEY=... DOC_INTEL_API_KEY=... bash deployment/configure_azure.sh job`
4. Fetch and classify once: portal → `caj-job-emclf-llm-gr` → **Run now**.

## Fetching email

The job runs **automatically every 4 hours** (`0 */4 * * *`, UTC) and can also be started at any time:
portal → `caj-job-emclf-llm-gr` → **Run now**, or

    az containerapp job start -n caj-job-emclf-llm-gr -g LLM --subscription "doValue - Prod Envs"

**Every run fetches only mail that arrived since the last successful run.** The ingest keeps a Graph delta
checkpoint (`state/` in blob) and moves it forward only after a run fully succeeds; it never re-reads the
mailbox history. The very first run with no checkpoint fetches the last day (`DELTA_BOOTSTRAP_DAYS`, default 1).
The classifier also ignores ingest runs from before `REGISTER_RUNS_FROM` (set at deploy time).

To switch between automatic and manual (also updates the clock icon in the review app):

    bash deployment/fetch_mode.sh manual
    bash deployment/fetch_mode.sh schedule "0 */4 * * *"          # cron in UTC

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
| `AUTO_ACCEPT_THRESHOLD` | `0.90` | certainty 90% or more, with nothing else wrong: AUTO; below 90%: REVIEW |
| `CLASSIFY_MAX_PER_RUN` | `0` | `0` = no count cap: every waiting email is classified (the time budget below is what ends a run) |
| `CLASSIFY_TIME_BUDGET_SECONDS` | `2700` | no new email is started after 45 min, so the run ends cleanly inside the 1-hour job timeout (~28 s each, about 90 per run); the rest wait for the next run. While it runs, the review app shows progress in the top bar and each email shows as "Classifying…" |
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

## Metrics view

The review app's **Metrics** tab (top bar) shows, for the last 7 / 30 / 90 days or everything, in Greek time:

- **Per day:** emails received and how each was routed: automatic, needed review, error, or not classified yet.
  Also how many have been reviewed and how many are still waiting for review.
- **Routing:** why emails needed review, certainty bands with how often reviewers kept the category (use this
  to tune `AUTO_ACCEPT_THRESHOLD`), the review outcome per route, and per category.
- **Actions:** what the action rules proposed, how many reviewers kept, removed or added, and the Qualco
  request codes used most.

Served by `GET /api/metrics?days=7|30|90|all`, computed in `review_app/metrics.py` from the case store
(read at most every 30 s). It needs nothing new in Azure.

## Importing emails by hand

Outlook `.msg` files (for example `test_data/`) go in with a local tool:

    pip install -r requirements/requirements-tools.txt
    python tools/import_msg.py test_data/

Then run the job (or `python -m main` locally) to classify them.

## Running locally

### Without Azure (invented emails)

`LOCAL_BLOB_DIR` makes every blob read and write (classifier, review app, Graph ingest, `tools/import_msg.py`)
use a local folder with the same layout instead of the storage account. Together with the local case store
(`CASE_STORE=local`, the default, in `LOCAL_STORE_DIR`), nothing needs Azure, keys or a login.

    python tools/local_demo.py                 # invented emails + registry in local_data/ (git-ignored)
    LOCAL_BLOB_DIR=local_data/blob LOCAL_STORE_DIR=local_data/case_store REVIEW_AUTH=dev \
        python review_app/server.py            # http://127.0.0.1:8765

PowerShell:

    python tools\local_demo.py
    $env:LOCAL_BLOB_DIR="local_data\blob"; $env:LOCAL_STORE_DIR="local_data\case_store"; $env:REVIEW_AUTH="dev"
    python review_app\server.py

`local_demo.py` classifies the emails with a stand-in model (no network calls) through the real
`run_classifier` and `understand` code, so every queue and card has something in it; two emails are left
waiting. `--unclassified` leaves all of them waiting instead, for the real classifier. Run it again to add
more; delete `local_data/` to start over. Everything in it is invented.

The real classifier on the same folder (only the model keys are needed; the registry is the invented one):

    cd AI_email_classifier
    LOCAL_BLOB_DIR=../local_data/blob LOCAL_STORE_DIR=../local_data/case_store UPLOAD_RESULTS_TO_BLOB=true \
        AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_API_KEY=... AZURE_OPENAI_DEPLOYMENT=... AZURE_OPENAI_API_VERSION=... \
        DOC_INTEL_ENDPOINT=... DOC_INTEL_API_KEY=... python -m main

Real `.msg` files can go into the folder too: `LOCAL_BLOB_DIR=local_data/blob python tools/import_msg.py <folder>`.
They are client data then: keep them on your machine.

### Against dev Azure

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

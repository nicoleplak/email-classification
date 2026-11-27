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

| `REVIEW_CACHE_MB` | memory for attachments and their OCR text (default 512, deployed 768); least recently used go first |
| `REVIEW_RUNS_KEPT` | ingest run files kept in memory (default 60, about 10 days at one run every 4 hours) |

Size: 1 CPU / 2 GiB, exactly one replica (the caches and the review locks live in that one process).

**Opening attachments fast** (300 emails a day, most with attachments): an email's run file is read from storage
once and kept, without the earlier thread messages its body already quotes; each run has its own lock, so one
slow download never blocks the rest. Opening an email reads its attachments into memory in the background, and
the browser starts downloading them too, so clicking an attachment tab shows it at once. Attachments are sent
with `Cache-Control: private, max-age=86400, immutable`: going back to one does not download it again. At start
the app reads the run files of the emails waiting for review, and while one email is open the next one in the
list is prepared. A file still loading shows a spinner with its name and size.

The review app holds no mailbox secret and no AI keys.

## Decision rules (prompts and actions)

The business rules (rules_for_prompt.xlsx, Nov 2026) live in `AI_email_classifier/inputs/`:
`action_rules.json` (per category: Qualco requests with open / `_Cust` codes, forwards, Outlook folders,
activities, Portal, reply template, how the account is chosen), `qualco_requests.json` (code names),
`reply_templates.json` (automatic replies) and `categories.json` (keywords and Priority for the model).
`core/action_rules.py` applies them; `docs/decision_rules.html` shows them for business review and is
regenerated with `python tools/rules_report.py` after any change, together with the editable draw.io version
`docs/decision_rules.drawio` (`python tools/rules_drawio.py`); a test fails when either is out of date.

| Variable | Meaning |
|---|---|
| `ACCOUNT_STATUS_COLUMN` | registry column with the Qualco case state per account. Unset (today): every request uses the open-case code, without `_Cust` |
| `EXTRA_CATEGORY_THRESHOLD` | certainty (share of classifier samples) from which a second or third category is added automatically, with its actions (default `0.80`; at most two) |
| `ACCOUNT_CLOSED_VALUES` | values of that column meaning "closed" (default `CLOSED,C,Κλειστός,ΚΛΕΙΣΤΟΣ`); a closed account gets the `_Cust` code |

Identification is by tax ID or account number only; a name or email match is shown to the reviewer but
never makes a case automatic.

## Senders: internal emails and Retail Support

- **Internal** (`internal_domains` in `AI_email_classifier/inputs/sender_flags.json`, `dovaluegreece.gr`): the
  classifier gives category 38 (`internal_category`) by the sender's address, with no model call, no
  attachment reading and no customer lookup, and handles it automatically (Outlook folder
  doValueGreece-noreply). A run with only internal emails does not even load the registry.
- **Retail Support** (`AI_email_classifier/inputs/retail_support_emails.txt`, one address per line): classified
  as usual and flagged **Προώθηση Retail Support**; the review app's «Αποστολέας» filter finds them.
- Changes to either file apply to the next email classified or shown; deploy the image for Azure.

The mailbox ingest keeps doValue's own senders (`EXCLUDE_DOMAINS` default `eurobank`). In a conversation that
also has a customer's email in the same run, the customer's email opens the case (`INTERNAL_DOMAINS`, default
`dovaluegreece`). It also saves CC addresses (`ccRecipients`); emails fetched before have none.

## Categories by rule

`AI_email_classifier/inputs/forced_categories.json` (`core/forced.py`), applied whatever the model answers:

- **Board:** a board member's name or title (`board.names`, `board.titles`) in the subject, the email text, an
  attachment or the To/Cc makes the email «Διοίκηση», the main request; the model's category stays as a further
  request with its actions.
- **Documents:** an attachment whose document type is listed (`documents`, today «Εξουσιοδότηση /
  πληρεξούσιο» → Εξουσιοδοτήσεις) adds that category and its request (45, or 124 for a closed case), unless the
  attachment was judged irrelevant.

The case page marks these categories «Κανόνας» instead of a certainty.

## Banks, SPV and ERB

`AI_email_classifier/inputs/spvmapping.json` is the SPV mapping. Its `spvs` rows have the columns **SPVNAME**
and **SPVCODE** (the registry's `PRTFL_NM` and `PRTFL_CD`), **BANK** (the bank the loans came from) and
**ALIASES** (other spellings, separated by `|`). The same rows can be kept as a table in
`inputs/spvmapping.csv` (`SPVNAME;SPVCODE;BANK;ALIASES`, e.g. saved from Excel as CSV UTF-8); rows of both files
are used. Its `banks` section lists how each bank may be written (Greek and Latin; case endings and accents are
ignored). `core/banks.py` looks in the subject, the email text and the attachments (not earlier messages of the
thread), plus the lender each attachment's analysis names:

- **SPV:** the text writes an SPV's name, code or alias, or names its bank → that SPV. It is matched to the
  customer's accounts by SPVCODE = `PRTFL_CD` or SPVNAME = `PRTFL_NM`, and narrows the accounts before the account
  rule applies. Without a mapping row, only an SPV whose registry name is written in the text matches. When the SPV
  still is not known for an "SPV" category, one request is opened per SPV instead of asking for the account.
- **ERB:** Eurobank named anywhere marks the email `ERB` (`markers` on the case): a pill in the list, the
  «Σήμανση» filter and a column in the Excel export. It changes no action or route.

Attachments get a document type from a fixed list (`DOCUMENT_TYPES` in `core/attachment_processor.py`), a lender
and a one or two sentence summary in Greek, shown on the case page («Συνημμένα»). The reader also gives, in Greek,
why each chosen category applies (`categoryReasons`), shown side by side on the case page.

## Qualco activities

Every Qualco request is followed by its activity on the same account (sheet "Activities" of
rules_for_prompt-2.xlsx, `request_activities` in `inputs/qualco_requests.json`).

**Follow-up:** when the past-requests file (`in/request_output_*.csv`, `REQUEST_HISTORY=true`) already has a
request of the same type for the customer's account (or with no account) whose `REQUEST_STATUS` is one of
`follow_up.statuses` in `inputs/qualco_requests.json` (today «Καταχώρηση αιτήματος»), no new request is
proposed: only the request's activity, marked follow-up, and the «σε εξέλιξη» reply. A request with no activity of
its own uses `follow_up.default_activity` (2090). Same type = `REQUEST_TYPE_DSC` equals the request's name, with or
without its code in front. The code table, with open and
`_Cust` codes, activities and Portal, is in `docs/decision_rules.html` and page 6 of `docs/decision_rules.drawio`.

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

Step by step for a laptop, including real emails copied from Azure with `tools/fetch_sample.py`: `docs/LOCAL_TESTING.md`.

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

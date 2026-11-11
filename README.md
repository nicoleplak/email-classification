# Email Classification: Development and Handover README

## 1. Purpose and status

This repository develops an AI-assisted workflow for triaging customer email in a shared doValue Greece mailbox. It combines Microsoft Graph ingestion, conversation context, attachment evidence, Azure AI document extraction, Azure OpenAI classification, AFM/registry validation, deterministic business rules, and output/routing components. The original UAT mailbox router **copies** messages to category folders and leaves Inbox originals unread; whether that router is used by the current integrated classifier is not established by the supplied materials.

**Read this as the central handover document.** It consolidates the three earlier documents and the current repository tree. Earlier documents describe different development phases, not three separate systems to deploy. Items marked **verify** cannot be confirmed without the current source code, configuration or deployment inventory. An image build/push and a working local Synapse connection were reported in recent development context; a deployed, scheduled, production-ready Container App has not been established.

## 2. Repository tree (supplied current layout)

```text
Email-Classification/
├── AI_email_classifier/
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── attachment_processor.py
│   │   └── processor.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── blob_output.py
│   │   ├── loader.py
│   │   ├── saver.py
│   │   └── synapse_registry.py
│   ├── DWH_Output_Storage/
│   │   └── qualco_output_20260518.csv
│   ├── inputs/
│   │   ├── categories.json
│   │   ├── classification_prompt.txt
│   │   ├── forward_rules.json
│   │   ├── replies.json
│   │   └── retry_clf_prompt.txt
│   ├── llm/
│   │   ├── __init__.py
│   │   └── classifier.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_afm_utils.py
│   │   └── test_email_processor.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── afm_utils.py
│   │   ├── builders.py
│   │   ├── registry_utils.py
│   │   └── routing_engine.py
│   ├── main.py
│   ├── requirements.txt
│   └── run.log
├── deployment/
├── graphapi/
│   ├── src/
│   │   ├── helpers/
│   │   │   ├── attachments.py
│   │   │   ├── graph_api.py
│   │   │   └── utils.py
│   │   ├── main.py
│   │   └── router.py
│   └── requirements.txt
├── attachment_mechanism.md
├── documentation.md
├── requirements-container.txt
└── run.log
```

The two old Markdown files are historical references; this README is intended to stand alone. The supplied tree does not list a Dockerfile, `.env.example`, folder registry, or the old attachment smoke-test script. This may reflect omitted/ignored files; inspect the checkout before concluding they are absent. The two `main.py` files are distinct entry points.

## 3. Architecture and data flow

```text
Shared Outlook mailbox
  -> graphapi/src/main.py: Graph fetch, sender filter, conversation deduplication,
     thread retrieval, body cleanup, attachment download
  -> enriched email JSON (OUTPUT_EMAIL)
  -> AI_email_classifier/main.py: load input and registry,
     extract/analyze attachment evidence, classify email/thread,
     validate AFMs and apply deterministic rules
  -> classification JSON/Excel and other configured outputs
  -> optional routing/forward/reply components (verify active execution path)
```

The earlier implementation used a flat `email/` folder and a separate external classifier that added `category` to `output_email.json` before `router.py` copied mail. The attachment design split Graph ingestion and classification into applications. The current tree names the latter `AI_email_classifier` and adds Synapse and Blob adapters. **Do not assume the old router consumes the current classifier output or that a manual stage-to-stage file copy has been automated.** Recent local development reported a manual copy between stage locations; verify the current producer/consumer paths.

### Component responsibilities

- `graphapi/src/helpers/graph_api.py`: Graph authentication, paginated candidate/thread/attachment retrieval; the older documentation also describes message copying.
- `graphapi/src/helpers/utils.py`: HTML/body cleanup, filename sanitization, pagination utilities.
- `graphapi/src/helpers/attachments.py`: attachment family handling, Base64 validation, binary persistence, hashed path names, descriptors and failure statuses.
- `graphapi/src/main.py`: candidate filtering, conversation deduplication, bounded UAT selection, thread enrichment and JSON export.
- `AI_email_classifier/config/settings.py`: configuration entry point; inspect actual variable names and defaults.
- `core/attachment_processor.py`: extension/size/status checks, inline asset filtering, text extraction and attachment evidence bundle.
- `core/processor.py`: target/prior-thread orchestration, AFM candidate combination, classification and deterministic processing.
- `llm/classifier.py`: initial and retry classification with attachment context and output validation.
- `data/loader.py`, `saver.py`: data loading and saving; exact current schema and destinations need code verification.
- `data/synapse_registry.py`: registry-source integration; `data/blob_output.py`: Blob-output integration. File presence alone does not establish their runtime configuration or side effects.
- `utils/afm_utils.py`, `registry_utils.py`, `routing_engine.py`, `builders.py`: AFM/registry, routing and output helpers; exact call graph and rule precedence require code review.
- `inputs/categories.json`, `forward_rules.json`, `replies.json`, prompt files: configuration for categories, forwarding, responses and classifier/retry prompts. Their actual contents were not supplied for this review.
- `graphapi/src/router.py`: legacy folder-copy router documented in the older file; confirm whether active.

## 4. Graph ingestion and thread semantics

The original candidate selection targets unread, uncategorized Inbox mail with `isRead eq false and not categories/any()`. For controlled UAT on already-read/categorized messages, the attachment document describes a strict UTC `receivedDateTime` range instead. **Verify the active filter before any run**; do not combine the two descriptions into an assumed current default. Follow Graph pagination, exclude configured sender domains from top-level candidates in Python, keep the newest candidate per `conversationId`, then apply the UAT `MAX_EMAILS` cap. Thread context retains internal replies and is sorted chronologically after retrieval. The original Graph implementation avoids combining `$filter` and `$orderby` on its mailbox-message request because that combination returned HTTP 400.

The original enriched email object contains Graph `id`, `subject`, `from`, `toRecipients`, `receivedDateTime`, `body`, `categories`, `conversationId`, `hasAttachments`, `body_clean`, `conversation_thread`, and `reply_to_message_id` (newest thread message, fallback to target). The attachment design adds per-message `attachments`, `attachment_fetch_attempted`, `attachment_fetch_succeeded`, `attachment_fetch_partially_succeeded`, and `attachment_download_errors`. The processor should use the current target and bounded *prior* context, not later messages. Confirm actual JSON field names and stage handoff against current code.

## 5. Attachment mechanism

Supported initial extensions: `.pdf`, `.docx`, `.txt`, `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`. TXT is decoded locally; PDF, DOCX and supported images use Document Intelligence `prebuilt-layout`. Item attachments and reference attachments are not handled recursively/by linked-file retrieval in the documented mechanism.

Graph file attachments are decoded, size-checked and saved under `ATTACHMENT_DIR/<conversation_hash>/<message_hash>/<attachment_hash>_<safe_filename>`. Full Graph IDs stay in metadata; raw Base64 is removed from exported JSON. The processor accepts `local_path`, `content_bytes`, or legacy `contentBytes`, ignores probable inline signature images, bounds extracted text, and asks Azure OpenAI for document type, relevance, requested actions, category suggestions, evidence, conflicts and AFM candidates. Its compact bundle includes totals, processed/relevant/failed counts, `requires_review`, warnings, extracted AFMs, evidence text and per-file records. Attachment evidence is **untrusted supporting context** on both initial and retry classifier calls, never a bypass of mandatory rules. Material unavailable evidence may require review. Other attachments continue if one fails.

Storage/fetch statuses: `SAVED`, `DOWNLOAD_MISSING`, `INVALID_BASE64`, `STORAGE_FAILED`, `ITEM_ATTACHMENT_UNSUPPORTED`, `REFERENCE_ATTACHMENT_UNSUPPORTED`, `UNKNOWN_ATTACHMENT_TYPE`, `INVALID_ATTACHMENT_OBJECT`. Analysis statuses: `ANALYZED`, `IGNORED_INLINE`, `UNSUPPORTED_TYPE`, `REJECTED_SECURITY`, `EXTRACTION_FAILED`, `ANALYSIS_FAILED`. Expected result diagnostics include `attachment_count`, `attachment_processed_count`, `attachment_relevant_count`, `attachment_failed_count`, `attachment_requires_review`, `attachment_warnings`, and `attachment_records`.

## 6. Classification, registry and routing

The attachment-aware classifier receives current email, bounded thread and attachment evidence, validates category/confidence/reasoning/evidence/thread relation, and retains attachment context on retries. The documented deterministic layer includes registry validation, Datamart/ERB handling, N.3869 rules, account selection, forwarding and routing. Attachment-derived AFMs must undergo the same authoritative validation as body/thread AFMs before production routing. The current `categories.json`, forwarding rules, replies and routing engine should be inspected to document exact category taxonomy, complaint override, rule order, side effects and review gates; those details are not recoverable from filenames alone.

Recent development context reports replacement of a local registry CSV dependency with Synapse table `[LLM].[EMCLF_ACC_OUTPUT]` on `dwhgruatsyn.sql.azuresynapse.net`, database `dwhuat`; local connection and execution were reported working. Verify the query, authentication, column mapping, timeouts and cloud identity in `synapse_registry.py`. The CSV remains in the supplied tree but should not be assumed to be the active registry source or included in a container image containing customer data. `blob_output.py` is present, but the actual storage account/container, path, schema, overwrite and retention behavior are not documented in the supplied files.

**Legacy folder-copy behavior:** The older `router.py` resolves a category against a folder registry by removing the prefix before the first underscore and comparing case-insensitively. It excludes `UAT_ROOT`, falls back to `04_Processing_Error` for unmatched categories, and copies messages while leaving Inbox originals unread. Its folder registry described business category and operational system folders. The registry file is not visible in the supplied tree. Confirm whether this router runs, where its mapping comes from, and how duplicate copies and `requires_review` are handled before enabling it.

## 7. Configuration and dependencies

The historical documents mention the following variable names. **These are a consolidated reference, not a verified `.env` for the current code**; inspect `settings.py` and entry points before use.

```dotenv
GRAPH_API_ENDPOINT=<graph-base-url>
DOVALUEGREECE_ID=<tenant-id>
CLIENT_ID=<app-client-id>
CLIENT_SECRET=<secret>
SCOPE=<graph-scope>
USER_ID=<shared-mailbox-id-or-address>
OUTPUT_EMAIL=<absolute-path-to-enriched-json>
FOLDER_MAP_FILE=<legacy-folder-registry-if-used>
EXCLUDE_DOMAINS=<comma-separated-domain-keywords>
MAX_EMAILS=<verified-batch-cap>
FETCH_ATTACHMENTS=true
ATTACHMENT_DIR=<controlled-attachment-directory>
AZURE_OPENAI_ENDPOINT=<endpoint>
AZURE_OPENAI_API_KEY=<secret>
AZURE_OPENAI_DEPLOYMENT=<deployment>
AZURE_OPENAI_API_VERSION=<version>
DOCUMENT_INTELLIGENCE_ENDPOINT=<endpoint>
DOCUMENT_INTELLIGENCE_KEY=<secret>
DOCUMENT_INTELLIGENCE_MODEL=prebuilt-layout
ATTACHMENT_PROCESSING_ENABLED=true
ATTACHMENT_MAX_BYTES=52428800
ATTACHMENT_MAX_PROMPT_CHARACTERS=60000
ATTACHMENT_RELEVANCE_THRESHOLD=0.55
```

The three attachment numeric settings above are documented examples, not verified active values. The older Graph documentation uses `MAX_EMAILS=0` for unlimited; the attachment example uses a positive UAT cap. Do not commit `.env` or credentials. Dependencies mentioned across the documents include `requests`, `python-dotenv`, `beautifulsoup4`, `openai`, `azure-ai-documentintelligence`, `azure-core`, `pydantic`, `pandas`, and `openpyxl`; install from the actual pinned `graphapi/requirements.txt`, `AI_email_classifier/requirements.txt` and `requirements-container.txt` as appropriate. Current package versions and ODBC/container installation steps require repository verification.

## 8. Running and testing

Run only after confirming current configuration and working directories. These are documented entry points, not a verified single-command production runbook:

```sh
# From graphapi/
python src/main.py

# From AI_email_classifier/
python main.py

# From AI_email_classifier/ (if pytest is installed)
python -m pytest tests/test_afm_utils.py tests/test_email_processor.py

# From graphapi/src/, only if legacy router is confirmed active and configured
python router.py
```

A historical attachment document mentions `tests/smoke_test_attachment_processor.py` (relevant TXT, ignored logo, missing referenced attachment); that script is **not in the supplied tree**. The listed AFM and processor test filenames do not establish their coverage or pass status. For a controlled integration check, select a strict Graph date window and small UAT cap, verify attachment `SAVED`/`local_path` and no exported Base64, exercise Document Intelligence and Azure OpenAI, check evidence in initial/retry prompts, and confirm review-required cases do not auto-route. Record actual JSON/Excel/Blob output locations and a reproducible test result.

## 9. Troubleshooting and failure behavior

- **No messages:** inspect mailbox, Inbox, UTC date range, active unread/category filter and excluded domains. A Graph filter cannot begin with `and`.
- **Graph HTTP 400:** inspect filter syntax and the documented `$filter` plus `$orderby` issue.
- **Windows path error:** avoid full Graph IDs as directory names; use hashed IDs and safe filenames.
- **`hasAttachments=true`, empty `attachments`:** inspect attempted/succeeded/partial flags and download errors; distinguish disabled fetch, unsupported type and storage/API failure.
- **No extracted text:** check corrupt/password-protected documents, scan quality, format and Document Intelligence access; preserve explicit failure status.
- **Per-item failures:** historical enrichment/router loops continue after individual email failures; attachment processing continues other files. Initial auth/fetch failures abort the original ingestion, and a missing error folder aborts the legacy router. Confirm current error/retry behavior in code.
- **Unrecognized category:** the historical router uses `04_Processing_Error`; this is not automatically equivalent to the attachment `requires_review` gate.

## 10. Security, operations and production gates

Treat email and documents as untrusted data: never execute embedded links, scripts, macros or instructions. Constrain file paths to `ATTACHMENT_DIR`; omit raw Base64 from exported JSON; avoid logging secrets, access tokens, complete extracted documents and full email bodies. Useful operational fields include Graph IDs, attachment SHA-256/status, document type/relevance, AFM candidates, model/prompt version, latency, retries, review reason, final category, routing status and correlation ID. Keep customer registry files and `run.log` out of images/repositories unless explicitly approved and sanitized.

The attachment documentation lists outstanding production work: consolidated integration run; authoritative attachment-AFM validation; live Graph, Document Intelligence and Azure OpenAI tests; cloud storage adaptation; deployment pipeline; malware scanning/quarantine; performance/UAT evaluation; and routing-review policy approval. Local attachment paths need a cloud storage abstraction for distributed execution. Hosting (Functions vs Container Apps worker/job), queueing, identity/secrets, retry/poison handling, idempotency, retention, networking and telemetry need explicit decisions. Older Graph documentation also calls out token refresh and transient API backoff.

## 11. Handover verification checklist

- [ ] Confirm current Git commit, branch and contents of `deployment/`, Dockerfile and build context.
- [ ] Trace both `main.py` entry points and the exact JSON handoff; document or eliminate the manual copy.
- [ ] Capture active Graph filter, mailbox permissions, sender exclusions, cap and pagination.
- [ ] Record actual settings, pinned dependencies, ODBC driver and secret/identity configuration without exposing values.
- [ ] Document Synapse query/schema, authoritative AFM matching and approved CSV fallback (if any).
- [ ] Document actual Blob/JSON/Excel outputs, schemas, retention and idempotency.
- [ ] Read category/prompt/rule/reply inputs and document rule precedence, complaint override and human-review routing.
- [ ] Establish whether `graphapi/src/router.py` is used; locate folder mapping and confirm mailbox side effects.
- [ ] Run visible unit tests plus controlled end-to-end attachment and routing tests; record results.
- [ ] Verify container image/revision and whether an Azure Container App or Job is deployed, triggered and monitored; do not equate a pushed image with a running service.
- [ ] Approve malware scanning, data handling, retries, review gate and production release criteria.


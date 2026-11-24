# Testing on your laptop

Four levels, from no Azure at all to real emails. Each level only adds what it needs. Commands are for
PowerShell, run from the repository folder (`email-classification`).

| Level | What you test | Needs |
|---|---|---|
| 1 | Unit tests | Python only |
| 2 | Review app on invented emails | Python only |
| 3 | Classifier + review app on **real emails copied from Azure** | read access to the storage account, OpenAI + Document Intelligence keys |
| 4 | Classifier + review app on your own **.msg files** | OpenAI + Document Intelligence keys |

Everything runs against two local folders, never the shared Azure data:
`local_data\blob` stands in for the blob container (`LOCAL_BLOB_DIR`) and `local_data\case_store` for
Cosmos (`LOCAL_STORE_DIR`). `local_data\` is git-ignored. Delete it to start over.

## 0. Set up once

```powershell
python -m venv .venv                       # Python 3.13 is what the tests run on
.venv\Scripts\Activate.ps1                 # if blocked: Set-ExecutionPolicy -Scope Process Bypass
pip install -r requirements\requirements-container.txt pytest
```

Open a new PowerShell window later? Run `.venv\Scripts\Activate.ps1` again.

## 1. Unit tests (no Azure, no keys)

```powershell
$env:CI = "1"; python -m pytest; Remove-Item Env:CI
```

`CI=1` stops the code from reading your `.env`, so the tests never call Azure.

## 2. Review app on invented emails (no Azure, no keys)

```powershell
python tools\local_demo.py                 # 40 invented emails, classified, some reviewed
$env:LOCAL_BLOB_DIR = "local_data\blob"; $env:LOCAL_STORE_DIR = "local_data\case_store"; $env:REVIEW_AUTH = "dev"
python review_app\server.py                # open http://127.0.0.1:8765, sign in with any name
```

`python tools\local_demo.py --no-reviews` leaves everything to review. Optional browser test (needs Node.js):
`npm install -g @playwright/test`, `npx playwright install chromium`, then, with the server running,
`node tests\browser\review_ui_test.cjs http://127.0.0.1:8765` in a second window.

## 3. Real emails copied from Azure

You do not connect the classifier to Azure storage: you **copy a sample** to `local_data\blob` once,
read-only, and work on the copy. Nothing in the shared container changes.

**a. Access to the storage account** (`datallmdev`, container `email-classification`), one of:

```powershell
az login                                                    # needs a Storage Blob Data Reader role on the container
$env:STG_KEY = "<account key>"                              # or: the account key (until IT grants the role)
$env:AZURE_STORAGE_CONNECTION_STRING = "<connection string>"  # or: a connection string
```

**b. Copy a sample**

```powershell
python tools\fetch_sample.py --runs 1 --limit 20 --registry
```

This copies the newest ingest run (at most 20 emails), each email's original and attachments, and the newest
customer registry (`in\qualco_output_*.csv`, about 170 MB). Other options: `--run 20261120T080000Z` for a
specific run, `--runs 3`, `--limit 0` for every email, `--requests` for the past-requests file (about 570 MB).
Without `--registry`, set `$env:REGISTRY_CSV` to a registry file you already have.

**c. Keys for the model**, in a file `AI_email_classifier\.env` (git-ignored, never commit it):

```dotenv
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=...
AZURE_OPENAI_API_VERSION=...
DOC_INTEL_ENDPOINT=...
DOC_INTEL_API_KEY=...
```

**d. Classify the copy**

```powershell
cd AI_email_classifier
$env:LOCAL_BLOB_DIR = "..\local_data\blob"; $env:LOCAL_STORE_DIR = "..\local_data\case_store"
$env:UPLOAD_RESULTS_TO_BLOB = "true"; $env:CASE_STORE = "local"
python -m main
cd ..
```

Expect about 30 seconds per email. Results go to `local_data\blob\silver` and the cases to
`local_data\case_store`.

**e. Review them**

```powershell
$env:LOCAL_BLOB_DIR = "local_data\blob"; $env:LOCAL_STORE_DIR = "local_data\case_store"; $env:REVIEW_AUTH = "dev"
python review_app\server.py
```

To compare prompt or rule changes on the same emails: delete `local_data\case_store` and
`local_data\blob\silver`, change the prompt or rule, and run step d again.

## 4. Your own .msg files

```powershell
pip install -r requirements\requirements-tools.txt
$env:LOCAL_BLOB_DIR = "local_data\blob"
python tools\import_msg.py C:\path\to\msg-folder
```

Then steps 3c to 3e. The customer registry comes from `--registry` (3b), `REGISTRY_CSV`, or, after
`local_demo.py`, the invented one (real tax IDs will not be found in it).

## Why not connect straight to Azure storage?

It works (`AZURE_STORAGE_CONNECTION_STRING` set and `LOCAL_BLOB_DIR` not set), but the classifier then
**writes** its results into the shared container's `silver\`, next to production's. Use a copy (level 3)
unless you mean to.

## Client data

Levels 3 and 4 put real client emails, attachments and the customer registry on your laptop. Keep them in
`local_data\` (never in git), do not share the folder, and delete it when you are done.

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
python tools\local_demo.py --serve          # 40 invented emails, classified, some reviewed; then starts the app
```

Open http://127.0.0.1:8765 and sign in with any name. Stop with Ctrl+C. Next time, without adding emails:
`python tools\local_demo.py --serve-only`. `--no-reviews` leaves everything to review; delete `local_data\`
to start over.

Starting the app by hand instead: the settings must be in the **same** PowerShell window as the server.

```powershell
$env:LOCAL_BLOB_DIR = "local_data\blob"; $env:LOCAL_STORE_DIR = "local_data\case_store"; $env:REVIEW_AUTH = "dev"
python review_app\server.py
```

On start the server prints where it reads emails from and how many it found, for example
`Cases: C:\...\local_data\case_store (42 emails)`. With `(0 emails)` it says what to set.

Optional browser test (needs Node.js): `npm install -g @playwright/test`, `npx playwright install chromium`,
then, with the server running, `node tests\browser\review_ui_test.cjs http://127.0.0.1:8765` in a second window.

### If the app shows no emails

| What you see | Cause | Fix |
|---|---|---|
| Server prints `(0 emails)` | the settings were typed in another window, or the server runs from another folder | use `python tools\local_demo.py --serve-only` |
| Blank page or a spinner that never stops | the browser blocked the page script (versions before this fix, on Windows) | use the latest `dev`; then Ctrl+F5 in the browser |
| Server prints `copied run(s) not in the app yet` | emails were copied but not registered as cases | step 3d: `cd AI_email_classifier; python -m main` (with `CLASSIFIER_PAUSED=true` to register only) |
| Server shows a different folder than `.env`, with `(set in this window, overrides .env)` | `$env:` settings typed earlier in that window | open a new terminal, or `Remove-Item Env:LOCAL_BLOB_DIR, Env:LOCAL_STORE_DIR` |
| "Δεν υπάρχουν email εδώ" | the selected queue or filter is empty | click «Όλα», set «Ημέρα» to «Όλες οι μέρες», clear the category filter |

## 3. Real emails copied from Azure

You do not connect the classifier to Azure storage: you **copy a sample** to `local_data\blob` once,
read-only, and work on the copy. Nothing in the shared container changes.

**a. Access to the storage account** (`datallmdev`, container `email-classification`), one of (or put
`STG_KEY` / `AZURE_STORAGE_CONNECTION_STRING` in `.env`, section 3):

```powershell
az login                                                    # needs a Storage Blob Data Reader role on the container
$env:STG_KEY = "<account key>"                              # or: the account key (until IT grants the role)
$env:AZURE_STORAGE_CONNECTION_STRING = "<connection string>"  # or: a connection string
```

If the copy stops with `AuthorizationPermissionMismatch` ("not authorized to perform this operation using
this permission"): your login reaches Azure but has no data role on the container. Use the account key
(`STG_KEY` in `.env`) until IT grants **Storage Blob Data Reader** on the container.

**b. Copy a sample** into an empty `local_data` (delete the folder first if level 2 left invented emails
in it, or the classifier will send those to the model too):

```powershell
python tools\fetch_sample.py --runs 1 --limit 20 --registry
```

This copies the newest ingest run (at most 20 emails), each email's original and attachments, and the newest
customer registry (`in\qualco_output_*.csv`, about 170 MB). Other options: `--run 20261120T080000Z` for a
specific run, `--runs 3`, `--limit 0` for every email, `--requests` for the past-requests file (about 570 MB).
Without `--registry`, set `$env:REGISTRY_CSV` to a registry file you already have.

**c. Settings file**: copy `.env.example` to `.env` in the repository root (next to `README.md`), fill in
section 1 (model keys) and the two full folder paths in section 2. `.env` is git-ignored: never commit it or
send it. Every script below reads it, so steps d and e need no PowerShell settings.

```powershell
Copy-Item .env.example .env
notepad .env
```

The copied emails are files only. They appear in the review app after step d, which registers each one as
a case (and classifies it). Until then the server prints `N copied run(s) not in the app yet`.

**d. Classify the copy**

```powershell
cd AI_email_classifier
python -m main
cd ..
```

Expect about 30 seconds per email. Results go to `local_data\blob\silver` and the cases to
`local_data\case_store`. To try a few first, add `CLASSIFY_MAX_PER_RUN=5` to `.env`.

**e. Review them**

```powershell
python review_app\server.py      # prints the folders it reads and how many emails it found
```

To compare prompt or rule changes on the same emails: delete `local_data\case_store` and
`local_data\blob\silver`, change the prompt or rule, and run step d again.

## 4. Your own .msg files

```powershell
pip install -r requirements\requirements-tools.txt
$env:LOCAL_BLOB_DIR = "local_data\blob"
python tools\import_msg.py C:\path\to\msg-folder
```

Then steps 3c to 3e (with `LOCAL_BLOB_DIR` in `.env`, the import needs no `$env:` line). The customer registry comes from `--registry` (3b), `REGISTRY_CSV`, or, after
`local_demo.py`, the invented one (real tax IDs will not be found in it).

## Why not connect straight to Azure storage?

It works (`AZURE_STORAGE_CONNECTION_STRING` set and `LOCAL_BLOB_DIR` not set), but the classifier then
**writes** its results into the shared container's `silver\`, next to production's. Use a copy (level 3)
unless you mean to.

## Client data

Levels 3 and 4 put real client emails, attachments and the customer registry on your laptop. Keep them in
`local_data\` (never in git), do not share the folder, and delete it when you are done.

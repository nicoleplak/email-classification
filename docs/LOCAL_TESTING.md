# Testing on your laptop

Commands are for PowerShell, run from the repository folder (`email-classification`, next to `README.md`)
unless a step says `cd`. Four levels; each adds only what it needs:

| Level | What you test | Needs | Data folder |
|---|---|---|---|
| 1 | Unit tests | Python | none |
| 2 | Review app on invented emails | Python | `local_data\` in the repository |
| 3 | Classifier + review app on **real emails copied from Azure** | `.env` with model keys, read access to the storage account | `C:\emclf-data\` (from `.env`) |
| 4 | Classifier + review app on your own **.msg files** | `.env` with model keys | `C:\emclf-data\` (from `.env`) |

Nothing here writes to Azure. Levels 3 and 4 only read from it (the copy) and call the model.

## 0. Set up once

```powershell
python -m venv .venv                       # Python 3.13 is what the tests run on
.venv\Scripts\Activate.ps1                 # if blocked: Set-ExecutionPolicy -Scope Process Bypass
python -m pip install -r requirements\requirements-container.txt pytest
```

- Every new terminal: run `.venv\Scripts\Activate.ps1` first. The prompt then starts with `(.venv)`.
- Always type `python`, never `C:\Program Files\...\python.exe`: that one ignores the `.venv` packages.
- New version of the code (zip or `git pull`): copy it over the folder **but keep your `.env`**. The zip has
  none, so it cannot overwrite yours.

## 1. Unit tests (no Azure, no keys)

```powershell
$env:CI = "1"; python -m pytest; Remove-Item Env:CI
```

`CI=1` stops the code from reading your `.env`, so the tests never call Azure. Expect all tests to pass.

## 2. Review app on invented emails (no Azure, no keys)

```powershell
python tools\local_demo.py --serve          # 40 invented emails, classified, some reviewed; then starts the app
```

Open http://127.0.0.1:8765 and sign in with any name; stop with Ctrl+C.

- Next time, without adding emails: `python tools\local_demo.py --serve-only`.
- `--no-reviews` leaves everything to review. Delete `local_data\` to start over.
- The demo always uses `local_data\` in the repository, never the folders in your `.env`, so it never mixes
  with real emails.

Optional browser test (needs Node.js): `npm install -g @playwright/test`, `npx playwright install chromium`,
then, with the app running, `node tests\browser\review_ui_test.cjs http://127.0.0.1:8765` in a second terminal.

## 3. Real emails copied from Azure

You copy a sample once, read-only, to `C:\emclf-data` on your laptop and work on the copy.

### a. Settings file (`.env`)

```powershell
Copy-Item .env.example .env
notepad .env
```

- **Section 1, model keys** (required): from `deployment\configure_azure.sh` and the Azure portal.

  | Setting | Value |
  |---|---|
  | `AZURE_OPENAI_ENDPOINT` | `https://openai-data-llm.openai.azure.com/` |
  | `AZURE_OPENAI_DEPLOYMENT` | `gpt-4.1-gs` |
  | `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` |
  | `AZURE_OPENAI_API_KEY` | portal → `openai-data-llm` → Keys and Endpoint → KEY 1 |
  | `DOC_INTEL_ENDPOINT` | `https://doc-intel-data-llm.cognitiveservices.azure.com/` |
  | `DOC_INTEL_API_KEY` | portal → `doc-intel-data-llm` → Keys and Endpoint → KEY 1 |

- **Section 2, folders**: already `C:\emclf-data\blob` and `C:\emclf-data\case_store`. Keep them **outside
  OneDrive**: they will hold client emails and the customer registry. If Windows refuses a folder under `C:\`,
  use `C:\Users\<you>\emclf-data\...` (also outside OneDrive). Keep `REVIEW_AUTH=dev` exactly.
- **Section 3, storage access**: remove the `#` before **one** of `STG_KEY` (portal → `datallmdev` → Access
  keys → key1) or `AZURE_STORAGE_CONNECTION_STRING`. Or leave both off and use `az login` (needs the
  role *Storage Blob Data Reader* on the container, which IT has to grant).

`.env` holds keys: it is git-ignored and never in the image. Never commit it, send it, or show it in a
screenshot. If a key was ever shown, rotate it in the portal (Access keys → Rotate key) and update `.env`.

### b. Copy a sample

```powershell
python tools\fetch_sample.py --runs 1 --limit 20 --registry
```

It first prints where it copies from and to, and how it signs in, then copies:

- the newest ingest run, at most 20 emails (`--limit 0` = all; `--run 20261123T080038Z` = a given run;
  `--runs 3` = the three newest);
- each email's original and attachments;
- with `--registry`, the newest customer registry (`in\qualco_output_*.csv`, about 170 MB). The classifier
  needs it to find customers. Copy it once; without it, set `REGISTRY_CSV` in `.env` to a registry you have.
- `--requests` adds the past-requests file (about 570 MB). Optional.

The emails are now **files only**: the review app shows them after step c.

### c. Classify them

```powershell
cd AI_email_classifier
python -m main
cd ..
```

- About 30 seconds per email. To try a few first, put `CLASSIFY_MAX_PER_RUN=5` in `.env`; remove it and run
  again for the rest (emails already classified are not sent again).
- To register them without calling the model, put `CLASSIFIER_PAUSED=true` in `.env` for one run: they show
  as «Δεν έχει ταξινομηθεί».
- Emails from `@dovaluegreece.gr` get category 38 by address, without the model. Addresses listed in
  `AI_email_classifier\inputs\retail_support_emails.txt` are classified as usual and flagged
  «Προώθηση Retail Support».

### d. Review them

```powershell
python review_app\server.py
```

It prints what it reads, for example:

```
Review app (dev) on http://127.0.0.1:8765
Cases: C:\emclf-data\case_store (20 emails)  (from .env)
Files: C:\emclf-data\blob  (from .env)
```

Open http://127.0.0.1:8765. Stop with Ctrl+C.

### e. Try a prompt or rule change on the same emails

Change the prompt (`AI_email_classifier\inputs\*.txt`) or the rules (`action_rules.json`, `categories.json`,
...), delete `C:\emclf-data\case_store` and `C:\emclf-data\blob\silver`, and run steps c and d again. The
copied emails and the registry stay. After a rule change, also run `python tools\rules_report.py` and
`python tools\rules_drawio.py` so the decision page and the draw.io file match.

## 4. Your own .msg files

```powershell
python -m pip install -r requirements\requirements-tools.txt
python tools\import_msg.py C:\path\to\your\msg-folder
```

They go into `LOCAL_BLOB_DIR` from `.env`. Then steps 3c and 3d. The customer registry still comes from
`--registry` (3b) or `REGISTRY_CSV`.

## What to look at in this version

- **Categories**: priority between several requests; a complaint leads only when nothing else is asked;
  category 45 «Τεχνικό πρόβλημα με Portal»; second and third categories added from 80% certainty.
- **Actions** (step 2 of an email): the Qualco request with its account, SPV and code (open, or `_Cust` once
  the closed flag exists), followed by its **activity** (sheet Activities); Portal only for 113, 89, 119.
- **Senders**: «Εσωτερικό» emails with category 38 and no model; «Προώθηση Retail Support»; the
  «Αποστολέας» filter; every To and Cc address in the email header (emails fetched from now on).
- **Case page**: «Πελάτης» first, possible customers (name or email only) in a drop-down; every chosen category
  in its own block with why it was chosen; «Συνημμένα» with document type, bank and summary; why the email went to
  review at the top. In the list: the review reason under each email, and the «Λόγος ελέγχου» and «Σήμανση» (ERB)
  filters.
- **Banks and SPV**: a bank or SPV named in the email or an attachment picks the SPV of the request; otherwise an
  "SPV" category opens one request per SPV. Fill the SPV names per bank in `AI_email_classifier\inputs\banks.json`.
- **Statistics**: click a number to open exactly those emails; the Excel export lists the current list.
- The rules for the business: `docs\decision_rules.html` and `docs\decision_rules.drawio`.

## If something goes wrong

| What you see | Cause | Fix |
|---|---|---|
| `No module named 'azure'` (or another module) | the packages are not in `.venv` | `python -m pip install -r requirements\requirements-container.txt` with `(.venv)` active |
| `... is still the example path from .env.example` | `.env` section 2 still has `C:\path\to\...` | put your folders, e.g. `C:\emclf-data\blob` |
| `AuthorizationPermissionMismatch` during the copy | your `az login` has no data role on the container | `STG_KEY=<key1>` in `.env` until IT grants Storage Blob Data Reader |
| `The ... was not accepted` during the copy | wrong or rotated key | copy key1 again from Access keys, without spaces or quotes |
| `REVIEW_AUTH must be demo or dev` | typo in `.env` | `REVIEW_AUTH=dev` |
| Server prints `N copied run(s) not in the app yet` | the copy was not classified yet | step 3c |
| Server prints `(set in this window, overrides .env)` | `$env:` settings typed earlier in that terminal | open a new terminal, or `Remove-Item Env:LOCAL_BLOB_DIR, Env:LOCAL_STORE_DIR` |
| Server prints `(0 emails)` | nothing classified in that folder yet, or the wrong folder | for the demo: `python tools\local_demo.py --serve-only`; for real emails: step 3c |
| The app shows only demo emails | the server reads `local_data\` instead of `.env` | start it with `python review_app\server.py` in a new terminal (not `local_demo.py`) |
| Blank page or a spinner that never stops | old version of the code | use the latest version, then Ctrl+F5 in the browser |
| «Δεν υπάρχουν email εδώ» | the queue or a filter is empty | click «Όλα», «Ημέρα» = «Όλες οι μέρες», clear «Κατηγορία» and «Αποστολέας» |

## Why not connect straight to Azure storage?

It works (a connection string and no `LOCAL_BLOB_DIR`), but the classifier then **writes** its results into
the shared container, next to the deployed system's. Work on a copy unless you mean to.

## Client data

Levels 3 and 4 put real client emails, attachments and the customer registry on your laptop, in
`C:\emclf-data`. Keep that folder outside OneDrive and out of git, do not share it, and delete it when you are
done: `Remove-Item -Recurse C:\emclf-data`.

-- Email classifier → data warehouse (Synapse dedicated SQL pool, schema [LLM]).
-- The classifier job writes CSV files to storage account datallmdev, container email-classification:
--   gold/dwh/EMCLF_EMAIL/yyyy/mm/dd/EMCLF_EMAIL_<stamp>.csv              one row per email
--   gold/dwh/EMCLF_EMAIL_DATA/yyyy/mm/dd/EMCLF_EMAIL_DATA_<stamp>.csv    one row per value of its data table
--   gold/dwh/EMCLF_EMAIL_ACTION/yyyy/mm/dd/EMCLF_EMAIL_ACTION_<stamp>.csv one row per proposed / final action
--   gold/dwh/_manifests/<stamp>.json                                    the files of one export, with row counts
-- UTF-8, header row, comma separated, every field in double quotes, timestamps ISO 8601 UTC (…Z).
-- Each file holds ALL rows of the emails it contains: load it by replacing those emails (delete + insert by case_id).

-- 1. Tables (once) ------------------------------------------------------------------------------------------
CREATE TABLE [LLM].[EMCLF_EMAIL] (
    case_id             NVARCHAR(64)   NOT NULL,
    received_at         NVARCHAR(32)   NULL,
    from_address        NVARCHAR(320)  NULL,
    sender_type         NVARCHAR(32)   NULL,   -- external | internal | retail_support
    subject             NVARCHAR(1000) NULL,
    status              NVARCHAR(32)   NULL,   -- CLASSIFIED | REVIEWED
    route               NVARCHAR(16)   NULL,   -- AUTO | REVIEW | EXCEPTION
    route_reasons       NVARCHAR(4000) NULL,   -- '; ' separated
    model_category      NVARCHAR(200)  NULL,
    confidence          NVARCHAR(16)   NULL,   -- 0..1
    final_category      NVARCHAR(200)  NULL,
    other_categories    NVARCHAR(1000) NULL,
    auto_categories     NVARCHAR(1000) NULL,
    no_match            NVARCHAR(1)    NULL,
    markers             NVARCHAR(200)  NULL,   -- e.g. ERB
    customer_tax_id     NVARCHAR(16)   NULL,
    customer_name       NVARCHAR(400)  NULL,
    identified_via      NVARCHAR(32)   NULL,   -- deceased_debtor | debtor | heir
    customers_confirmed NVARCHAR(8)    NULL,
    customers_possible  NVARCHAR(8)    NULL,
    reviewed_by         NVARCHAR(200)  NULL,
    reviewed_at         NVARCHAR(32)   NULL,
    review_outcome      NVARCHAR(32)   NULL,   -- accepted | changed | none_fits
    actions_outcome     NVARCHAR(32)   NULL,
    review_comment      NVARCHAR(4000) NULL,
    classified_at       NVARCHAR(32)   NULL,
    classifier_run      NVARCHAR(64)   NULL,
    ingest_run          NVARCHAR(128)  NULL,
    updated_at          NVARCHAR(32)   NULL,
    exported_at         NVARCHAR(32)   NULL
) WITH (DISTRIBUTION = HASH(case_id), CLUSTERED COLUMNSTORE INDEX);

CREATE TABLE [LLM].[EMCLF_EMAIL_DATA] (
    case_id         NVARCHAR(64)   NOT NULL,
    row_id          NVARCHAR(32)   NOT NULL,
    type            NVARCHAR(32)   NULL,   -- afm | account | contract | payment_code | iban | adt | phone | email | case_ref | name | spv
    value           NVARCHAR(200)  NULL,
    role            NVARCHAR(32)   NULL,   -- debtor | co_debtor | deceased_debtor | heir | representative | ...
    identifies_case NVARCHAR(1)    NULL,
    checked         NVARCHAR(1)    NULL,   -- passed a check digit
    method          NVARCHAR(64)   NULL,
    source_kind     NVARCHAR(32)   NULL,   -- subject | body | thread | attachment | sender | user | ...
    source_file     NVARCHAR(400)  NULL,
    source_page     NVARCHAR(8)    NULL,
    snippet         NVARCHAR(1000) NULL,   -- empty when DWH_EXPORT_SNIPPETS=false
    status          NVARCHAR(16)   NULL,   -- found | added | edited | removed
    original_value  NVARCHAR(200)  NULL,
    changed_by      NVARCHAR(200)  NULL,
    changed_at      NVARCHAR(32)   NULL,
    exported_at     NVARCHAR(32)   NULL
) WITH (DISTRIBUTION = HASH(case_id), CLUSTERED COLUMNSTORE INDEX);

CREATE TABLE [LLM].[EMCLF_EMAIL_ACTION] (
    case_id       NVARCHAR(64)   NOT NULL,
    stage         NVARCHAR(16)   NOT NULL,   -- proposed | final
    seq           NVARCHAR(8)    NOT NULL,
    action        NVARCHAR(32)   NULL,       -- request | activity | reply | portal_referral | outlook_folder | forward | ...
    category      NVARCHAR(200)  NULL,
    code          NVARCHAR(16)   NULL,       -- Qualco request / activity code
    code_name     NVARCHAR(400)  NULL,
    account       NVARCHAR(64)   NULL,
    spv           NVARCHAR(200)  NULL,
    account_state NVARCHAR(16)   NULL,
    template      NVARCHAR(64)   NULL,
    folder        NVARCHAR(200)  NULL,
    forward_to    NVARCHAR(1000) NULL,
    for_request   NVARCHAR(16)   NULL,
    follow_up     NVARCHAR(1)    NULL,
    caveat        NVARCHAR(64)   NULL,
    exported_at   NVARCHAR(32)   NULL
) WITH (DISTRIBUTION = HASH(case_id), CLUSTERED COLUMNSTORE INDEX);

-- Staging tables with the same columns, emptied before each load.
CREATE TABLE [LLM].[EMCLF_EMAIL_STG] WITH (DISTRIBUTION = HASH(case_id), HEAP) AS SELECT * FROM [LLM].[EMCLF_EMAIL] WHERE 1 = 0;
CREATE TABLE [LLM].[EMCLF_EMAIL_DATA_STG] WITH (DISTRIBUTION = HASH(case_id), HEAP) AS SELECT * FROM [LLM].[EMCLF_EMAIL_DATA] WHERE 1 = 0;
CREATE TABLE [LLM].[EMCLF_EMAIL_ACTION_STG] WITH (DISTRIBUTION = HASH(case_id), HEAP) AS SELECT * FROM [LLM].[EMCLF_EMAIL_ACTION] WHERE 1 = 0;

-- 2. Load one export (per run; the paths come from gold/dwh/_manifests/<stamp>.json) ------------------------
-- <EMAIL_FILE>, <DATA_FILE>, <ACTION_FILE>: the three "file" values of one manifest (gold/dwh/_manifests/<stamp>.json),
-- e.g. gold/dwh/EMCLF_EMAIL/2026/11/27/EMCLF_EMAIL_20261127T101500Z.csv; the orchestrator (ADF / Synapse pipeline)
-- fills them in, one manifest at a time, oldest first. The pool's identity needs Storage Blob Data Reader on the
-- container (or use a SAS / storage key credential).
TRUNCATE TABLE [LLM].[EMCLF_EMAIL_STG];
TRUNCATE TABLE [LLM].[EMCLF_EMAIL_DATA_STG];
TRUNCATE TABLE [LLM].[EMCLF_EMAIL_ACTION_STG];

COPY INTO [LLM].[EMCLF_EMAIL_STG]
FROM 'https://datallmdev.blob.core.windows.net/email-classification/<EMAIL_FILE>'
WITH (FILE_TYPE = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0A',
      ENCODING = 'UTF8', CREDENTIAL = (IDENTITY = 'Managed Identity'));
COPY INTO [LLM].[EMCLF_EMAIL_DATA_STG]
FROM 'https://datallmdev.blob.core.windows.net/email-classification/<DATA_FILE>'
WITH (FILE_TYPE = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0A',
      ENCODING = 'UTF8', CREDENTIAL = (IDENTITY = 'Managed Identity'));
COPY INTO [LLM].[EMCLF_EMAIL_ACTION_STG]
FROM 'https://datallmdev.blob.core.windows.net/email-classification/<ACTION_FILE>'
WITH (FILE_TYPE = 'CSV', FIRSTROW = 2, FIELDQUOTE = '"', FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0A',
      ENCODING = 'UTF8', CREDENTIAL = (IDENTITY = 'Managed Identity'));

-- Replace the exported emails' rows.
DELETE FROM [LLM].[EMCLF_EMAIL] WHERE case_id IN (SELECT case_id FROM [LLM].[EMCLF_EMAIL_STG]);
DELETE FROM [LLM].[EMCLF_EMAIL_DATA] WHERE case_id IN (SELECT case_id FROM [LLM].[EMCLF_EMAIL_STG]);
DELETE FROM [LLM].[EMCLF_EMAIL_ACTION] WHERE case_id IN (SELECT case_id FROM [LLM].[EMCLF_EMAIL_STG]);
INSERT INTO [LLM].[EMCLF_EMAIL] SELECT * FROM [LLM].[EMCLF_EMAIL_STG];
INSERT INTO [LLM].[EMCLF_EMAIL_DATA] SELECT * FROM [LLM].[EMCLF_EMAIL_DATA_STG];
INSERT INTO [LLM].[EMCLF_EMAIL_ACTION] SELECT * FROM [LLM].[EMCLF_EMAIL_ACTION_STG];

-- 3. Examples ------------------------------------------------------------------------------------------------
-- Accounts reviewers had to type in, per category:
--   SELECT e.final_category, COUNT(*) FROM [LLM].[EMCLF_EMAIL_DATA] d JOIN [LLM].[EMCLF_EMAIL] e ON e.case_id = d.case_id
--   WHERE d.type = 'account' AND d.status = 'added' GROUP BY e.final_category;
-- Qualco requests filed per day:
--   SELECT LEFT(e.reviewed_at, 10) AS day, a.code, a.code_name, COUNT(*) FROM [LLM].[EMCLF_EMAIL_ACTION] a
--   JOIN [LLM].[EMCLF_EMAIL] e ON e.case_id = a.case_id WHERE a.stage = 'final' AND a.action = 'request'
--   GROUP BY LEFT(e.reviewed_at, 10), a.code, a.code_name;

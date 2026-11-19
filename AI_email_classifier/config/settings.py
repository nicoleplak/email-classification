import os
from dotenv import load_dotenv

CI_MODE = os.getenv("CI", "").strip().lower() in {"1", "true", "yes"}

if not CI_MODE:
    load_dotenv()


# -----------------------------------------------------------
# 1. LLM / API Configuration
# -----------------------------------------------------------
# These can come from environment variables or be hard‑coded for local use.
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")

doc_intel_endpoint = os.getenv("DOC_INTEL_ENDPOINT")
doc_intel_api_key = os.getenv("DOC_INTEL_API_KEY")
attachment_progress_enabled = True
# -----------------------------------------------------------
# 2. Input / Output Paths
# -----------------------------------------------------------
# Base folders — adjust as needed
BASE_INPUTS = os.path.join(os.getcwd(), "inputs")
BASE_STORAGE = os.path.join(os.getcwd(), "DWH_Output_Storage")
BASE_EMAILS = os.path.join(os.getcwd(), "Sample_Emails")
BASE_EXPORTS = os.path.join(os.getcwd(), "exports")

# Specific files
classification_prompt_path = os.path.join(BASE_INPUTS, "classification_prompt.txt")
retry_clf_prompt_path = os.path.join(BASE_INPUTS, "retry_clf_prompt.txt")
categories_path = os.path.join(BASE_INPUTS, "categories.json")
replies_path = os.path.join(BASE_INPUTS, "replies.json")
forward_rules_path = os.path.join(BASE_INPUTS, "forward_rules.json")
registry_path = os.path.join(BASE_STORAGE, "qualco_output_20260518.csv")
emails_path = os.getenv("EMAILS_PATH", os.path.join(BASE_EMAILS, "emails.json"))

# Optional export paths (if DataSaver wants them)
summary_json_path = os.path.join(BASE_EXPORTS, "summary.json")
summary_excel_path = os.path.join(BASE_EXPORTS, "summary.xlsx")


# -----------------------------------------------------------
# 3. Miscellaneous Settings
# -----------------------------------------------------------
# Example: temperature, max tokens, etc., if you want them centralized
LLM_TEMPERATURE = 0
LLM_MAX_TOKENS = 800

CLASSIFIER_MAX_LOOP_ITERATIONS = 3
CLASSIFIER_CONFIDENCE_THRESHOLD = 0.80
# Confidence = share of sampled answers (weighted by token probability) that
# agree with the returned category; 1 sample falls back to token probability.
CLASSIFIER_SAMPLES = 5
LLM_SAMPLING_TEMPERATURE = 0.7


# -----------------------------------------------------------
# 4. Utility function (optional)
# -----------------------------------------------------------
def ensure_directories():
    """Create required folders if they don't exist."""
    for folder in [BASE_INPUTS, BASE_STORAGE, BASE_EMAILS, BASE_EXPORTS]:
        os.makedirs(folder, exist_ok=True)


# Automatically ensure folders exist when settings is imported
if not CI_MODE:
    ensure_directories()

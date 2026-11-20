import json
import os
import tempfile
from pathlib import Path

from data.loader import DataLoader
from data.saver import DataSaver
from llm.classifier import EmailClassifier
from core.processor import EmailProcessor
from core.attachment_processor import AttachmentProcessor, AttachmentProcessorConfig
from config import settings

import logging

# stdout, so Container Apps sends it to Log Analytics; a file inside the container is lost after each run.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)
logger.info("Starting main.py")


def env_flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() == "true"


def load_registry():
    """Customer registry: Synapse, a local CSV (REGISTRY_CSV), or the newest in/qualco_output_*.csv in blob."""
    registry_source = os.getenv("REGISTRY_SOURCE", "csv").strip().lower()
    if registry_source == "synapse":
        from data.synapse_registry import load_registry_from_synapse

        registry_df = load_registry_from_synapse()
    elif registry_source == "csv":
        local = os.getenv("REGISTRY_CSV")
        if local:
            registry_df = DataLoader.load_registry_df(local)
        else:
            from data.blob_output import download_to, list_names

            names = [n for n in list_names("in/qualco_output_") if n.endswith(".csv")]
            if not names:
                raise FileNotFoundError("No in/qualco_output_*.csv in the blob container.")
            # Names end in YYYYMMDD, so the last one sorted is the newest export.
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "registry.csv"
                download_to(names[-1], path)
                registry_df = DataLoader.load_registry_df(str(path))
            registry_source = names[-1]
    else:
        raise ValueError(f"Unsupported REGISTRY_SOURCE: {registry_source}")

    print(f"Registry source: {registry_source}; rows loaded: {len(registry_df)}")
    return registry_df, registry_source


def newest_blob(prefix: str) -> str | None:
    """Names end in YYYYMMDD, so the last one sorted is the newest export."""
    from data.blob_output import list_names

    names = [n for n in list_names(prefix) if n.endswith(".csv")]
    return names[-1] if names else None


def understand_factory(processor, messages):
    """The per-email reader, with one streaming pass over past Qualco requests for this run's emails."""
    from core.customer_lookup import Registry, RequestHistory
    from core.understand import lookup_tokens, understand

    registry = Registry(processor.registry_df, getattr(processor, "registry_source", ""))
    history = RequestHistory.empty()
    requests_blob = newest_blob("in/request_output_") if env_flag("REQUEST_HISTORY", True) else None
    if requests_blob:
        from data.blob_output import download_to

        emails, tax_ids = set(), set()
        for message in messages:
            found_emails, found_tax = lookup_tokens(message)
            emails |= found_emails
            tax_ids |= found_tax
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "requests.csv"
                download_to(requests_blob, path)
                history = RequestHistory.scan(str(path), emails, tax_ids, requests_blob)
            print(f"Request history: {requests_blob}; {len(history.rows)} matching rows")
        except Exception as exc:  # The lookup still works from the registry alone.
            print(f"Request history unavailable ({type(exc).__name__}: {exc}); continuing without it")
    categories = [c["Categories"].strip() for c in processor.categories_data]
    client = processor.classifier.client
    model = processor.classifier.model_name

    def read(message, records, text_dir):
        return understand(client=client, model=model, message=message, records=records, text_dir=text_dir,
                          categories=categories, registry=registry, history=history)

    return read


def build_processor(save_attachment_text: bool = False) -> EmailProcessor:
    classifier_prompt = DataLoader.load_text(settings.classification_prompt_path)
    retry_clf_prompt = DataLoader.load_text(settings.retry_clf_prompt_path)
    categories_data = DataLoader.load_json(settings.categories_path)
    reply_templates = DataLoader.load_json(settings.replies_path)
    forward_rules = DataLoader.load_json(settings.forward_rules_path)
    default_reply = reply_templates.get("--default--", "Λάβαμε το αίτημά σας.")

    classifier = EmailClassifier(
        prompt_text=classifier_prompt,
        retry_prompt=retry_clf_prompt,
        api_key=settings.api_key,
        base_url=settings.endpoint,
        model_name=settings.deployment_name,
        max_loop_iterations=settings.CLASSIFIER_MAX_LOOP_ITERATIONS,
        confidence_threshold=settings.CLASSIFIER_CONFIDENCE_THRESHOLD,
    )

    attachment_processor = AttachmentProcessor(
        openai_client=classifier.client,
        model_name=settings.deployment_name,
        config=AttachmentProcessorConfig(
            enabled=getattr(settings, "ATTACHMENT_PROCESSING_ENABLED", True),
            document_intelligence_endpoint=settings.doc_intel_endpoint,
            document_intelligence_key=settings.doc_intel_api_key,
            document_intelligence_model=getattr(
                settings, "DOCUMENT_INTELLIGENCE_MODEL", "prebuilt-layout"
            ),
            max_attachment_bytes=getattr(
                settings, "ATTACHMENT_MAX_BYTES", 50 * 1024 * 1024
            ),
            max_prompt_characters=getattr(
                settings, "ATTACHMENT_MAX_PROMPT_CHARACTERS", 60_000
            ),
            show_progress=getattr(settings, "attachment_progress_enabled", True),
            # The blob flow points this at a fresh folder per email, then copies it to silver.
            save_extracted_text_debug=save_attachment_text,
        ),
    )

    registry_df, registry_source = load_registry()
    processor = EmailProcessor(
        registry_df=registry_df,
        classifier=classifier,
        categories_data=categories_data,
        reply_templates=reply_templates,
        forward_rules=forward_rules,
        default_reply=default_reply,
        attachment_processor=attachment_processor,
    )
    processor.registry_source = registry_source  # shown on every case as where customer data came from
    return processor


def run_from_blob() -> None:
    """Scheduled job: register new bronze runs as cases, then classify what is waiting."""
    from core import run_classifier
    from data import blob_output
    from data.case_store import open_store

    summary = run_classifier.run(
        open_store(),
        blob_output,
        lambda: build_processor(save_attachment_text=True),
        paused=env_flag("CLASSIFIER_PAUSED"),
        threshold=float(os.getenv("AUTO_ACCEPT_THRESHOLD", "0.90")),
        limit=int(os.getenv("CLASSIFY_MAX_PER_RUN", "0")),
        budget_seconds=float(os.getenv("CLASSIFY_TIME_BUDGET_SECONDS", "0")),
        runs_from=os.getenv("REGISTER_RUNS_FROM", "").strip(),
        understand_factory=understand_factory if env_flag("UNDERSTAND_ENABLED", True) else None,
    )
    print(json.dumps(summary, indent=2))
    logger.info("Run summary: %s", summary)


def run_local_file() -> None:
    """Local/evaluation use: classify EMAILS_PATH and write exports/summary.json + .xlsx."""
    processor = build_processor()
    emails = DataLoader.load_json(settings.emails_path)
    results = processor.process_batch(emails, export=False, use_thread_context=True)
    DataSaver.save_json(results)
    DataSaver.save_excel(results)
    print(f"\nDONE — {len(results)} records processed and exported (JSON + Excel)\n")


def main():
    logger.info("Initializing pipeline...")
    if env_flag("UPLOAD_RESULTS_TO_BLOB"):
        run_from_blob()
    else:
        run_local_file()
    logger.info("Pipeline finished successfully.")


# -----------------------------------------------------------
# Entry point
# -----------------------------------------------------------
if __name__ == "__main__":
    logger.info("Executing __main__ block")
    main()

# One image, two steps: Graph ingest, then the classifier (see deployment/run_pipeline.sh).
# ACR mirror of python:3.13-slim-bookworm (the build VM cannot reach Docker Hub or deb.debian.org).
# The image already ships ca-certificates.
FROM craiplatformsharedgrprd.azurecr.io/mirror/python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UPLOAD_RESULTS_TO_BLOB=true \
    CLASSIFIER_ENABLED=false \
    REGISTRY_SOURCE=csv

WORKDIR /app

# Customer registry via Synapse (ADWH view [LLM].[EMCLF_ACC_OUTPUT]): DISABLED.
# The FSD (FR-77, FR-130) intends a live ADWH lookup, but the Container Apps environment cannot
# reach the private Synapse endpoint, and the build VM cannot reach packages.microsoft.com or
# deb.debian.org. Until then the classifier reads the newest in/qualco_output_*.csv from blob
# (REGISTRY_SOURCE=csv). To enable: make these packages reachable (e.g. through the platform
# mirror), uncomment the block, and set REGISTRY_SOURCE=synapse on the job.
# ENV SYNAPSE_ODBC_DRIVER="ODBC Driver 17 for SQL Server"
# RUN apt-get update \
#     && apt-get install -y --no-install-recommends curl gnupg libgssapi-krb5-2 \
#     && curl -fsSL https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
#         -o /tmp/packages-microsoft-prod.deb \
#     && dpkg -i /tmp/packages-microsoft-prod.deb \
#     && rm /tmp/packages-microsoft-prod.deb \
#     && apt-get update \
#     && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
#     && rm -rf /var/lib/apt/lists/*

COPY requirements/runtime/requirements-container.lock \
    /app/requirements-container.lock

RUN python -m pip install \
        --no-cache-dir \
        --require-hashes \
        -r /app/requirements-container.lock \
    && python -m pip check

COPY graphapi/src/ /app/graphapi/src/
COPY AI_email_classifier/ /app/AI_email_classifier/
COPY deployment/run_pipeline.sh /app/deployment/run_pipeline.sh

RUN chmod +x /app/deployment/run_pipeline.sh

CMD ["/app/deployment/run_pipeline.sh"]

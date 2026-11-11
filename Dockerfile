FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UPLOAD_RESULTS_TO_BLOB=true

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/runtime/requirements-container.lock \
    /app/requirements-container.lock

RUN python -m pip install \
        --no-cache-dir \
        --require-hashes \
        -r /app/requirements-container.lock \
    && python -m pip check

COPY graphapi/src/ /app/graphapi/src/
COPY deployment/run_pipeline.sh /app/deployment/run_pipeline.sh

RUN chmod +x /app/deployment/run_pipeline.sh

CMD ["/app/deployment/run_pipeline.sh"]
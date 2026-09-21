FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages
COPY fixtures ./fixtures
COPY migrations ./migrations
COPY alembic.ini ./
RUN pip install --upgrade pip && pip install .

EXPOSE 8000
CMD ["sh", "-c", "if [ \"$SERVICE_ROLE\" = \"worker\" ]; then exec dramatiq veritydocs_api.jobs --processes 1 --threads 4; else exec uvicorn veritydocs_api.main:app --app-dir apps/api --host 0.0.0.0 --port ${PORT:-8000}; fi"]

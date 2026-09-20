from __future__ import annotations

import logging

import dramatiq

from .config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
if settings.redis_url:
    from dramatiq.brokers.redis import RedisBroker

    dramatiq.set_broker(RedisBroker(url=settings.redis_url))

if settings.ocr_engine.lower() == "tesseract":
    from .pipeline.ocr import OCRUnavailable, TesseractOCREngine

    try:
        engine = TesseractOCREngine()
        logger.info("worker_startup ocr_engine=%s version=%s", engine.name, engine.version)
    except OCRUnavailable as exc:
        logger.warning("worker_startup ocr_engine=unavailable reason=%s", exc)


@dramatiq.actor(max_retries=3, min_backoff=5_000, max_backoff=120_000)
def process_document_job(document_id: str) -> None:
    from .database import SessionLocal
    from .service import process_document

    db = SessionLocal()
    try:
        process_document(db, document_id)
    finally:
        db.close()


def enqueue_document(document_id: str) -> None:
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required to enqueue background document work")
    process_document_job.send(document_id)

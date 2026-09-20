from __future__ import annotations

import dramatiq

from .config import get_settings

settings = get_settings()
if settings.redis_url:
    from dramatiq.brokers.redis import RedisBroker

    dramatiq.set_broker(RedisBroker(url=settings.redis_url))


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

"""Background Redis worker processing asynchronous AI indexing jobs."""

import json
import logging
import time
from uuid import UUID

import redis

from app.application.use_cases.ai import IndexDocumentUseCase
from app.infrastructure.ai.embedder import DeterministicHashEmbedder
from app.infrastructure.ai.queue import RedisJobQueue
from app.infrastructure.ai.text_extractor import DefaultTextExtractor
from app.infrastructure.config import get_settings
from app.infrastructure.persistence.database import SessionLocal
from app.infrastructure.persistence.repositories import (
    SqlAlchemyAuditRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyVectorStore,
)
from app.infrastructure.storage.local_storage import LocalStorageAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("archivite.worker")


def process_job(raw_payload: str) -> None:
    """Deserialize a single job and run IndexDocumentUseCase."""
    data = json.loads(raw_payload)
    if data.get("task") != "index_document":
        logger.warning("Unknown task: %s", data.get("task"))
        return

    tenant_id = UUID(data["tenant_id"])
    document_id = UUID(data["document_id"])
    settings = get_settings()

    with SessionLocal() as db:
        use_case = IndexDocumentUseCase(
            document_repo=SqlAlchemyDocumentRepository(db),
            storage=LocalStorageAdapter(settings.storage_base_path),
            extractor=DefaultTextExtractor(),
            embedder=DeterministicHashEmbedder(),
            vector_store=SqlAlchemyVectorStore(db),
            audit_repo=SqlAlchemyAuditRepository(db),
        )
        chunks_count = use_case.execute(tenant_id=tenant_id, document_id=document_id)
        logger.info("Indexed document=%s tenant=%s chunks=%d", document_id, tenant_id, chunks_count)


def run_worker() -> None:
    """Blocking BRPOP loop consuming AI indexing jobs from Redis."""
    settings = get_settings()
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("Worker listening on %s", RedisJobQueue.QUEUE_KEY)

    while True:
        try:
            item = client.brpop(RedisJobQueue.QUEUE_KEY, timeout=5)
            if item is not None:
                _, raw_payload = item
                process_job(raw_payload)
        except Exception:
            logger.exception("Error processing AI job; continuing...")
            time.sleep(1)


if __name__ == "__main__":
    run_worker()

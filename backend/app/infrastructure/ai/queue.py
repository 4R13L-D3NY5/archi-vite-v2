"""Redis and in-memory job queue adapters for background AI indexing."""

import json
from uuid import UUID, uuid4

import redis


class RedisJobQueue:
    """JobQueuePort implementation backed by a Redis list."""

    QUEUE_KEY = "archivite:ai_jobs"

    def __init__(self, redis_url: str) -> None:
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    def enqueue_document_indexing(self, tenant_id: UUID, document_id: UUID) -> str:
        """Push an indexing job payload onto Redis and return the job ID."""
        job_id = str(uuid4())
        payload = json.dumps(
            {
                "job_id": job_id,
                "task": "index_document",
                "tenant_id": str(tenant_id),
                "document_id": str(document_id),
            }
        )
        self._client.lpush(self.QUEUE_KEY, payload)
        return job_id


class InMemoryJobQueue:
    """In-memory JobQueuePort for unit and HTTP tests."""

    def __init__(self) -> None:
        self.jobs: list[tuple[UUID, UUID, str]] = []

    def enqueue_document_indexing(self, tenant_id: UUID, document_id: UUID) -> str:
        job_id = str(uuid4())
        self.jobs.append((tenant_id, document_id, job_id))
        return job_id

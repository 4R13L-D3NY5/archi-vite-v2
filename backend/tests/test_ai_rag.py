"""Tests for AI text extraction, chunking, RAG semantic search, and tenant isolation."""

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.application.use_cases.ai import (
    IndexDocumentUseCase,
    SemanticSearchUseCase,
    chunk_text,
)
from app.domain.entities import Document, Role
from app.infrastructure.ai.embedder import DeterministicHashEmbedder
from app.infrastructure.ai.queue import InMemoryJobQueue
from app.infrastructure.ai.text_extractor import DefaultTextExtractor
from app.infrastructure.api.main import (
    app,
    get_audit_repo,
    get_document_repo,
    get_embedder,
    get_folder_repo,
    get_job_queue,
    get_storage,
    get_tenant_repo,
    get_text_extractor,
    get_user_repo,
    get_vector_store,
)
from app.infrastructure.persistence.in_memory import (
    InMemoryAuditRepository,
    InMemoryDocumentRepository,
    InMemoryFolderRepository,
    InMemoryTenantRepository,
    InMemoryUserRepository,
    InMemoryVectorStore,
)
from app.infrastructure.storage.local_storage import LocalStorageAdapter


def test_chunk_text_splits_with_overlap() -> None:
    text = "word " * 300
    chunks = chunk_text(text, max_chars=200, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_index_and_semantic_search_are_tenant_isolated(tmp_path: Path) -> None:
    doc_repo = InMemoryDocumentRepository()
    storage = LocalStorageAdapter(tmp_path)
    extractor = DefaultTextExtractor()
    embedder = DeterministicHashEmbedder()
    vector_store = InMemoryVectorStore(doc_repo)

    tenant_a = uuid4()
    tenant_b = uuid4()

    key_a = storage.put_object(f"{tenant_a}/a.txt", b"Quarterly financial invoice and tax report for 2026.", "text/plain")
    doc_a = doc_repo.save(
        Document(
            tenant_id=tenant_a,
            title="finance_2026.txt",
            mime_type="text/plain",
            storage_key=key_a,
            size_bytes=52,
        )
    )

    key_b = storage.put_object(f"{tenant_b}/b.txt", b"Secret financial merger plan for Beta Corp.", "text/plain")
    doc_b = doc_repo.save(
        Document(
            tenant_id=tenant_b,
            title="beta_secret.txt",
            mime_type="text/plain",
            storage_key=key_b,
            size_bytes=43,
        )
    )

    index_uc = IndexDocumentUseCase(doc_repo, storage, extractor, embedder, vector_store)
    assert index_uc.execute(tenant_a, doc_a.id) == 1
    assert index_uc.execute(tenant_b, doc_b.id) == 1

    search_uc = SemanticSearchUseCase(embedder, vector_store)
    res_a = search_uc.execute(tenant_a, "financial invoice report")
    assert len(res_a.results) == 1
    assert res_a.results[0].document_title == "finance_2026.txt"


def test_http_upload_enqueues_job_and_search_endpoint_works(tmp_path: Path) -> None:
    tenant_repo = InMemoryTenantRepository()
    user_repo = InMemoryUserRepository()
    folder_repo = InMemoryFolderRepository()
    doc_repo = InMemoryDocumentRepository()
    audit_repo = InMemoryAuditRepository()
    storage = LocalStorageAdapter(tmp_path)
    extractor = DefaultTextExtractor()
    embedder = DeterministicHashEmbedder()
    vector_store = InMemoryVectorStore(doc_repo)
    job_queue = InMemoryJobQueue()

    app.dependency_overrides[get_tenant_repo] = lambda: tenant_repo
    app.dependency_overrides[get_user_repo] = lambda: user_repo
    app.dependency_overrides[get_folder_repo] = lambda: folder_repo
    app.dependency_overrides[get_document_repo] = lambda: doc_repo
    app.dependency_overrides[get_audit_repo] = lambda: audit_repo
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_text_extractor] = lambda: extractor
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    app.dependency_overrides[get_job_queue] = lambda: job_queue

    client = TestClient(app)
    try:
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "tenant_name": "Delta AI",
                "tenant_slug": "delta",
                "admin_email": "admin@delta.com",
                "admin_password": "strong-password-123",
            },
        )
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        upload = client.post(
            "/api/v1/documents",
            headers=headers,
            files={"file": ("architecture.txt", b"Hexagonal architecture decouples domain from adapters.", "text/plain")},
        )
        assert upload.status_code == 201
        doc_id = upload.json()["id"]
        assert len(job_queue.jobs) == 1

        idx = client.post(f"/api/v1/documents/{doc_id}/index", headers=headers)
        assert idx.status_code == 200
        assert idx.json()["chunks_indexed"] == 1

        search = client.post(
            "/api/v1/search",
            headers=headers,
            json={"query": "hexagonal domain adapters", "limit": 3},
        )
        assert search.status_code == 200
        body = search.json()
        assert len(body["results"]) == 1
        assert body["results"][0]["document_title"] == "architecture.txt"
    finally:
        app.dependency_overrides.clear()

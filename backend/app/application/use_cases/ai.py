"""Asynchronous AI indexing and semantic search (RAG) use cases."""

from dataclasses import dataclass
from uuid import UUID

from app.application.ports import (
    AuditRepositoryPort,
    DocumentRepositoryPort,
    EmbeddingPort,
    StoragePort,
    TextExtractorPort,
    VectorStorePort,
)
from app.domain.entities import AuditLog, DocumentChunk, SearchResult
from app.domain.exceptions import EntityNotFoundError, ValidationError


def chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping character windows for embedding."""
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    if max_chars <= overlap:
        raise ValidationError("max_chars must be greater than overlap.")

    chunks: list[str] = []
    start = 0
    step = max_chars - overlap
    while start < len(cleaned):
        chunks.append(cleaned[start : start + max_chars])
        start += step
    return chunks


@dataclass(frozen=True)
class SemanticSearchResponse:
    """Ranked semantic matches plus a synthesized context summary."""

    query: str
    results: list[SearchResult]
    summary: str


class IndexDocumentUseCase:
    """Extract text, chunk, embed, and store vectors for a tenant document."""

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        storage: StoragePort,
        extractor: TextExtractorPort,
        embedder: EmbeddingPort,
        vector_store: VectorStorePort,
        audit_repo: AuditRepositoryPort | None = None,
    ) -> None:
        self._document_repo = document_repo
        self._storage = storage
        self._extractor = extractor
        self._embedder = embedder
        self._vector_store = vector_store
        self._audit_repo = audit_repo

    def execute(
        self, tenant_id: UUID, document_id: UUID, actor_user_id: UUID | None = None
    ) -> int:
        """Index a document and return the number of stored chunks."""
        doc = self._document_repo.get_by_id(tenant_id, document_id)
        if doc is None:
            raise EntityNotFoundError(
                f"Document {document_id} not found for tenant {tenant_id}."
            )

        raw_bytes = self._storage.get_object(doc.storage_key)
        text = self._extractor.extract_text(raw_bytes, doc.mime_type)
        parts = chunk_text(text)
        if not parts:
            self._vector_store.upsert_chunks(tenant_id, document_id, [])
            return 0

        vectors = self._embedder.embed_texts(parts)
        chunks = [
            DocumentChunk(
                tenant_id=tenant_id,
                document_id=document_id,
                chunk_index=idx,
                content=part,
                embedding=vec,
            )
            for idx, (part, vec) in enumerate(zip(parts, vectors, strict=True))
        ]
        self._vector_store.upsert_chunks(tenant_id, document_id, chunks)

        if self._audit_repo is not None and actor_user_id is not None:
            self._audit_repo.record(
                AuditLog(
                    tenant_id=tenant_id,
                    actor_user_id=actor_user_id,
                    action="document.indexed",
                    resource_type="document",
                    resource_id=document_id,
                )
            )
        return len(chunks)


class SemanticSearchUseCase:
    """Perform tenant-isolated semantic search over indexed document chunks."""

    def __init__(
        self, embedder: EmbeddingPort, vector_store: VectorStorePort
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store

    def execute(
        self, tenant_id: UUID, query: str, limit: int = 5
    ) -> SemanticSearchResponse:
        """Embed query and retrieve top-k matching chunks for tenant_id."""
        cleaned = query.strip()
        if not cleaned:
            raise ValidationError("Search query cannot be empty.")

        query_vec = self._embedder.embed_texts([cleaned])[0]
        results = self._vector_store.search(
            tenant_id=tenant_id, query_embedding=query_vec, limit=limit
        )
        if not results:
            summary = "No matching indexed passages found in this workspace."
        else:
            top = results[0]
            summary = (
                f"Top match in '{top.document_title}' (score {top.score:.2f}): "
                f"{top.content[:240]}"
            )
        return SemanticSearchResponse(query=cleaned, results=results, summary=summary)

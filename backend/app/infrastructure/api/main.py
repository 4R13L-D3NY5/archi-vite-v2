"""FastAPI HTTP entrypoint wired to application use cases."""

from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form
from pydantic import BaseModel

from app.application.use_cases.documents import (
    ListDocumentsUseCase,
    UploadDocumentCommand,
    UploadDocumentUseCase,
)
from app.domain.entities import Document, DocumentSource
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.infrastructure.config import get_settings
from app.infrastructure.persistence.in_memory import (
    InMemoryDocumentRepository,
    InMemoryFolderRepository,
)
from app.infrastructure.storage.local_storage import LocalStorageAdapter

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

# Temporary in-memory wiring for Phase 1 bootstrap; replaced by PostgreSQL adapters in Phase 2.
_document_repo = InMemoryDocumentRepository()
_folder_repo = InMemoryFolderRepository()
_storage = LocalStorageAdapter(settings.storage_base_path)


class DocumentResponse(BaseModel):
    """HTTP representation of a Document domain entity."""

    id: UUID
    tenant_id: UUID
    title: str
    mime_type: str
    size_bytes: int
    source: DocumentSource
    folder_id: UUID | None
    created_at: datetime

    @classmethod
    def from_domain(cls, doc: Document) -> "DocumentResponse":
        """Map a domain Document to an HTTP response model."""
        return cls(
            id=doc.id,
            tenant_id=doc.tenant_id,
            title=doc.title,
            mime_type=doc.mime_type,
            size_bytes=doc.size_bytes,
            source=doc.source,
            folder_id=doc.folder_id,
            created_at=doc.created_at,
        )


@app.get("/health")
def health_check() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": settings.app_name}


@app.post("/api/v1/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    file: UploadFile = File(...),
    folder_id: UUID | None = Form(default=None),
) -> DocumentResponse:
    """Upload a document into the caller's tenant workspace."""
    content = await file.read()
    use_case = UploadDocumentUseCase(
        document_repo=_document_repo,
        storage=_storage,
        folder_repo=_folder_repo,
    )
    try:
        document = use_case.execute(
            UploadDocumentCommand(
                tenant_id=x_tenant_id,
                title=file.filename or "untitled",
                mime_type=file.content_type or "application/octet-stream",
                content=content,
                folder_id=folder_id,
            )
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DocumentResponse.from_domain(document)


@app.get("/api/v1/documents", response_model=list[DocumentResponse])
def list_documents(
    x_tenant_id: UUID = Header(..., alias="X-Tenant-ID"),
    folder_id: UUID | None = None,
) -> list[DocumentResponse]:
    """List documents belonging to the caller's tenant."""
    use_case = ListDocumentsUseCase(document_repo=_document_repo)
    docs = use_case.execute(tenant_id=x_tenant_id, folder_id=folder_id)
    return [DocumentResponse.from_domain(doc) for doc in docs]

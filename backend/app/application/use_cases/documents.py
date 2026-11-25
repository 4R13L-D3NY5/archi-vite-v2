"""Document management use cases."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.application.ports import (
    DocumentRepositoryPort,
    FolderRepositoryPort,
    StoragePort,
)
from app.domain.entities import Document, DocumentSource
from app.domain.exceptions import EntityNotFoundError


@dataclass(frozen=True)
class UploadDocumentCommand:
    """Input payload for storing a new document inside a tenant workspace."""

    tenant_id: UUID
    title: str
    mime_type: str
    content: bytes
    folder_id: UUID | None = None


class UploadDocumentUseCase:
    """Store binary content via StoragePort and persist metadata via repository."""

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        storage: StoragePort,
        folder_repo: FolderRepositoryPort | None = None,
    ) -> None:
        self._document_repo = document_repo
        self._storage = storage
        self._folder_repo = folder_repo

    def execute(self, command: UploadDocumentCommand) -> Document:
        """Validate folder ownership, upload bytes, and persist document metadata."""
        if command.folder_id is not None and self._folder_repo is not None:
            folder = self._folder_repo.get_by_id(command.tenant_id, command.folder_id)
            if folder is None:
                raise EntityNotFoundError(
                    f"Folder {command.folder_id} not found for tenant {command.tenant_id}."
                )

        doc_id = uuid4()
        storage_key = f"{command.tenant_id}/{doc_id}/{command.title}"
        persisted_key = self._storage.put_object(
            storage_key=storage_key,
            content=command.content,
            mime_type=command.mime_type,
        )

        document = Document(
            id=doc_id,
            tenant_id=command.tenant_id,
            title=command.title,
            mime_type=command.mime_type,
            storage_key=persisted_key,
            size_bytes=len(command.content),
            source=DocumentSource.LOCAL,
            folder_id=command.folder_id,
        )
        return self._document_repo.save(document)


class ListDocumentsUseCase:
    """List documents strictly scoped to a single tenant."""

    def __init__(self, document_repo: DocumentRepositoryPort) -> None:
        self._document_repo = document_repo

    def execute(
        self, tenant_id: UUID, folder_id: UUID | None = None
    ) -> list[Document]:
        """Return documents belonging to tenant_id."""
        return self._document_repo.list_by_tenant(
            tenant_id=tenant_id, folder_id=folder_id
        )

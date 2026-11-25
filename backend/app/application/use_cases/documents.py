"""Document management use cases with RBAC and audit logging."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.application.ports import (
    AuditRepositoryPort,
    DocumentRepositoryPort,
    FolderRepositoryPort,
    StoragePort,
)
from app.domain.entities import AuditLog, Document, DocumentSource, Role
from app.domain.exceptions import EntityNotFoundError, UnauthorizedActionError


@dataclass(frozen=True)
class UploadDocumentCommand:
    """Input payload for storing a new document inside a tenant workspace."""

    tenant_id: UUID
    actor_user_id: UUID
    actor_role: Role
    title: str
    mime_type: str
    content: bytes
    folder_id: UUID | None = None


class UploadDocumentUseCase:
    """Enforce RBAC, store binary content via StoragePort, and persist metadata."""

    _ALLOWED_ROLES = {Role.ADMIN, Role.EDITOR}

    def __init__(
        self,
        document_repo: DocumentRepositoryPort,
        storage: StoragePort,
        folder_repo: FolderRepositoryPort | None = None,
        audit_repo: AuditRepositoryPort | None = None,
    ) -> None:
        self._document_repo = document_repo
        self._storage = storage
        self._folder_repo = folder_repo
        self._audit_repo = audit_repo

    def execute(self, command: UploadDocumentCommand) -> Document:
        """Validate RBAC and folder ownership, upload bytes, and persist metadata."""
        if command.actor_role not in self._ALLOWED_ROLES:
            raise UnauthorizedActionError(
                f"Role '{command.actor_role.value}' cannot upload documents."
            )

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
        saved = self._document_repo.save(document)

        if self._audit_repo is not None:
            self._audit_repo.record(
                AuditLog(
                    tenant_id=command.tenant_id,
                    actor_user_id=command.actor_user_id,
                    action="document.uploaded",
                    resource_type="document",
                    resource_id=saved.id,
                )
            )
        return saved


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


class ListAuditLogsUseCase:
    """List audit trail entries for a tenant (ADMIN only)."""

    def __init__(self, audit_repo: AuditRepositoryPort) -> None:
        self._audit_repo = audit_repo

    def execute(
        self, tenant_id: UUID, actor_role: Role, limit: int = 50
    ) -> list[AuditLog]:
        """Return recent audit logs if actor has ADMIN role."""
        if actor_role != Role.ADMIN:
            raise UnauthorizedActionError("Only ADMIN users can view audit logs.")
        return self._audit_repo.list_by_tenant(tenant_id=tenant_id, limit=limit)

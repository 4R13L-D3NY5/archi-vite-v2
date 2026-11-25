"""External DMS integration and synchronization use cases."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.application.ports import (
    AuditRepositoryPort,
    DmsProviderPort,
    DocumentRepositoryPort,
    IntegrationRepositoryPort,
    StoragePort,
)
from app.domain.entities import (
    AuditLog,
    Document,
    DocumentSource,
    IntegrationConnection,
    Role,
)
from app.domain.exceptions import EntityNotFoundError, UnauthorizedActionError


@dataclass(frozen=True)
class ConnectDmsCommand:
    """Input for registering or updating an external DMS connection."""

    tenant_id: UUID
    actor_user_id: UUID
    actor_role: Role
    provider: DocumentSource
    access_token: str
    base_url: str | None = None
    refresh_token: str | None = None


@dataclass(frozen=True)
class SyncDmsCommand:
    """Input for triggering incremental document sync from an external DMS."""

    tenant_id: UUID
    actor_user_id: UUID
    actor_role: Role
    provider: DocumentSource


@dataclass(frozen=True)
class SyncDmsResult:
    """Summary of an incremental DMS synchronization run."""

    synced_count: int
    next_cursor: str | None


class ConnectDmsUseCase:
    """Connect an external DMS provider for a tenant (ADMIN only)."""

    def __init__(
        self,
        integration_repo: IntegrationRepositoryPort,
        audit_repo: AuditRepositoryPort | None = None,
    ) -> None:
        self._integration_repo = integration_repo
        self._audit_repo = audit_repo

    def execute(self, command: ConnectDmsCommand) -> IntegrationConnection:
        """Validate ADMIN role, persist connection, and record audit entry."""
        if command.actor_role != Role.ADMIN:
            raise UnauthorizedActionError(
                "Only ADMIN users can configure external DMS integrations."
            )

        existing = self._integration_repo.get_by_provider(
            command.tenant_id, command.provider
        )
        now = datetime.now(timezone.utc)
        connection = IntegrationConnection(
            id=existing.id if existing else uuid4(),
            tenant_id=command.tenant_id,
            provider=command.provider,
            access_token=command.access_token,
            base_url=command.base_url,
            refresh_token=command.refresh_token,
            sync_cursor=existing.sync_cursor if existing else None,
            is_active=True,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        saved = self._integration_repo.save(connection)

        if self._audit_repo is not None:
            self._audit_repo.record(
                AuditLog(
                    tenant_id=command.tenant_id,
                    actor_user_id=command.actor_user_id,
                    action="integration.connected",
                    resource_type="integration",
                    resource_id=saved.id,
                )
            )
        return saved


class SyncDmsDocumentsUseCase:
    """Pull incremental changes from a connected DMS adapter into tenant storage."""

    _ALLOWED_ROLES = {Role.ADMIN, Role.EDITOR}

    def __init__(
        self,
        integration_repo: IntegrationRepositoryPort,
        document_repo: DocumentRepositoryPort,
        storage: StoragePort,
        providers: dict[DocumentSource, DmsProviderPort],
        audit_repo: AuditRepositoryPort | None = None,
    ) -> None:
        self._integration_repo = integration_repo
        self._document_repo = document_repo
        self._storage = storage
        self._providers = providers
        self._audit_repo = audit_repo

    def execute(self, command: SyncDmsCommand) -> SyncDmsResult:
        """Fetch changes via DmsProviderPort, store files, and advance sync cursor."""
        if command.actor_role not in self._ALLOWED_ROLES:
            raise UnauthorizedActionError(
                f"Role '{command.actor_role.value}' cannot trigger DMS sync."
            )

        connection = self._integration_repo.get_by_provider(
            command.tenant_id, command.provider
        )
        if connection is None or not connection.is_active:
            raise EntityNotFoundError(
                f"No active integration found for provider '{command.provider.value}'."
            )

        adapter = self._providers.get(command.provider)
        if adapter is None:
            raise EntityNotFoundError(
                f"No adapter registered for provider '{command.provider.value}'."
            )

        items, next_cursor = adapter.list_changes(
            connection=connection, cursor=connection.sync_cursor
        )

        synced = 0
        for item in items:
            content = adapter.download_content(connection, item.external_id)
            doc_id = uuid4()
            storage_key = f"{command.tenant_id}/{command.provider.value}/{doc_id}/{item.title}"
            persisted_key = self._storage.put_object(
                storage_key=storage_key,
                content=content,
                mime_type=item.mime_type,
            )
            self._document_repo.save(
                Document(
                    id=doc_id,
                    tenant_id=command.tenant_id,
                    title=item.title,
                    mime_type=item.mime_type,
                    storage_key=persisted_key,
                    size_bytes=len(content),
                    source=item.source,
                    external_id=item.external_id,
                )
            )
            synced += 1

        connection.sync_cursor = next_cursor
        connection.updated_at = datetime.now(timezone.utc)
        self._integration_repo.save(connection)

        if self._audit_repo is not None:
            self._audit_repo.record(
                AuditLog(
                    tenant_id=command.tenant_id,
                    actor_user_id=command.actor_user_id,
                    action="integration.synced",
                    resource_type="integration",
                    resource_id=connection.id,
                )
            )
        return SyncDmsResult(synced_count=synced, next_cursor=next_cursor)

"""In-memory repository adapters for unit tests."""

from uuid import UUID

from app.domain.entities import (
    AuditLog,
    Document,
    DocumentSource,
    Folder,
    IntegrationConnection,
    Tenant,
    User,
)


class InMemoryTenantRepository:
    """In-memory store for Tenant entities."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, Tenant] = {}

    def save(self, tenant: Tenant) -> Tenant:
        self._by_id[tenant.id] = tenant
        return tenant

    def get_by_slug(self, slug: str) -> Tenant | None:
        for tenant in self._by_id.values():
            if tenant.slug == slug:
                return tenant
        return None

    def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        return self._by_id.get(tenant_id)


class InMemoryUserRepository:
    """In-memory store for User entities."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    def save(self, user: User) -> User:
        self._by_id[user.id] = user
        return user

    def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        for user in self._by_id.values():
            if user.tenant_id == tenant_id and user.email == email:
                return user
        return None

    def get_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None:
        user = self._by_id.get(user_id)
        if user is None or user.tenant_id != tenant_id:
            return None
        return user


class InMemoryDocumentRepository:
    """In-memory store for Document entities."""

    def __init__(self) -> None:
        self._items: dict[UUID, Document] = {}

    def save(self, document: Document) -> Document:
        self._items[document.id] = document
        return document

    def get_by_id(self, tenant_id: UUID, document_id: UUID) -> Document | None:
        doc = self._items.get(document_id)
        if doc is None or doc.tenant_id != tenant_id:
            return None
        return doc

    def list_by_tenant(
        self, tenant_id: UUID, folder_id: UUID | None = None
    ) -> list[Document]:
        return [
            doc
            for doc in self._items.values()
            if doc.tenant_id == tenant_id
            and (folder_id is None or doc.folder_id == folder_id)
        ]


class InMemoryFolderRepository:
    """In-memory store for Folder entities."""

    def __init__(self) -> None:
        self._items: dict[UUID, Folder] = {}

    def save(self, folder: Folder) -> Folder:
        self._items[folder.id] = folder
        return folder

    def get_by_id(self, tenant_id: UUID, folder_id: UUID) -> Folder | None:
        folder = self._items.get(folder_id)
        if folder is None or folder.tenant_id != tenant_id:
            return None
        return folder


class InMemoryAuditRepository:
    """In-memory store for AuditLog entities."""

    def __init__(self) -> None:
        self._items: list[AuditLog] = []

    def record(self, entry: AuditLog) -> AuditLog:
        self._items.append(entry)
        return entry

    def list_by_tenant(self, tenant_id: UUID, limit: int = 50) -> list[AuditLog]:
        entries = [e for e in self._items if e.tenant_id == tenant_id]
        return list(reversed(entries))[:limit]


class InMemoryIntegrationRepository:
    """In-memory store for IntegrationConnection entities."""

    def __init__(self) -> None:
        self._items: dict[UUID, IntegrationConnection] = {}

    def save(self, connection: IntegrationConnection) -> IntegrationConnection:
        self._items[connection.id] = connection
        return connection

    def get_by_provider(
        self, tenant_id: UUID, provider: DocumentSource
    ) -> IntegrationConnection | None:
        for conn in self._items.values():
            if conn.tenant_id == tenant_id and conn.provider == provider:
                return conn
        return None

    def list_by_tenant(self, tenant_id: UUID) -> list[IntegrationConnection]:
        return [c for c in self._items.values() if c.tenant_id == tenant_id]

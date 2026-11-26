"""Pure domain entities and value objects for archi-vite-v2."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from app.domain.exceptions import ValidationError


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    """Tenant-scoped RBAC roles."""

    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class DocumentSource(str, Enum):
    """Origin provider for a managed document."""

    LOCAL = "local"
    GOOGLE_DRIVE = "google_drive"
    EXTERNAL_DMS = "external_dms"


@dataclass(frozen=True)
class Tenant:
    """Organization workspace isolating data, connectors, and quotas."""

    name: str
    slug: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("Tenant name cannot be empty.")
        if not self.slug.strip():
            raise ValidationError("Tenant slug cannot be empty.")


@dataclass(frozen=True)
class User:
    """Actor belonging to a tenant with an assigned role."""

    tenant_id: UUID
    email: str
    password_hash: str = ""
    role: Role = Role.VIEWER
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if "@" not in self.email:
            raise ValidationError("User email must be valid.")


@dataclass(frozen=True)
class AuditLog:
    """Immutable audit trail entry for tenant-scoped actions."""

    tenant_id: UUID
    actor_user_id: UUID
    action: str
    resource_type: str
    resource_id: UUID
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class IntegrationConnection:
    """Tenant-scoped configuration and sync cursor for an external DMS provider."""

    tenant_id: UUID
    provider: DocumentSource
    access_token: str
    base_url: str | None = None
    refresh_token: str | None = None
    sync_cursor: str | None = None
    is_active: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if self.provider == DocumentSource.LOCAL:
            raise ValidationError("Integration provider cannot be 'local'.")
        if not self.access_token.strip():
            raise ValidationError("Integration access_token cannot be empty.")


@dataclass(frozen=True)
class DocumentChunk:
    """Indexed text chunk and vector embedding belonging to a tenant document."""

    tenant_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    embedding: list[float]
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class SearchResult:
    """Semantic search match returned by RAG retrieval."""

    document_id: UUID
    document_title: str
    chunk_index: int
    content: str
    score: float


@dataclass
class Folder:
    """Hierarchical container for documents inside a tenant."""

    tenant_id: UUID
    name: str
    parent_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("Folder name cannot be empty.")


@dataclass
class Document:
    """Core document metadata independent of physical storage or external DMS."""

    tenant_id: UUID
    title: str
    mime_type: str
    storage_key: str
    size_bytes: int
    source: DocumentSource = DocumentSource.LOCAL
    external_id: str | None = None
    folder_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValidationError("Document title cannot be empty.")
        if not self.storage_key.strip():
            raise ValidationError("Document storage_key cannot be empty.")
        if self.size_bytes < 0:
            raise ValidationError("Document size_bytes cannot be negative.")

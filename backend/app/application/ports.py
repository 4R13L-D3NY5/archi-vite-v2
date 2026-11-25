"""Application ports defining boundaries between use cases and infrastructure."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.entities import (
    AuditLog,
    Document,
    DocumentSource,
    Folder,
    Role,
    Tenant,
    User,
)


@dataclass(frozen=True)
class ExternalDocumentItem:
    """Normalized metadata returned by external DMS/cloud connectors."""

    external_id: str
    title: str
    mime_type: str
    size_bytes: int
    source: DocumentSource


@dataclass(frozen=True)
class TokenPayload:
    """Authenticated actor claims extracted from an access token."""

    user_id: UUID
    tenant_id: UUID
    role: Role


class TenantRepositoryPort(Protocol):
    """Persistence contract for tenants."""

    def save(self, tenant: Tenant) -> Tenant:
        """Persist a tenant."""

    def get_by_slug(self, slug: str) -> Tenant | None:
        """Fetch a tenant by unique slug."""

    def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        """Fetch a tenant by ID."""


class UserRepositoryPort(Protocol):
    """Persistence contract for tenant-scoped users."""

    def save(self, user: User) -> User:
        """Persist a user."""

    def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        """Fetch a user by email within a tenant."""

    def get_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None:
        """Fetch a user by ID within a tenant."""


class AuditRepositoryPort(Protocol):
    """Persistence contract for immutable audit logs."""

    def record(self, entry: AuditLog) -> AuditLog:
        """Persist an audit log entry."""

    def list_by_tenant(self, tenant_id: UUID, limit: int = 50) -> list[AuditLog]:
        """List recent audit entries for a tenant."""


class PasswordHasherPort(Protocol):
    """Password hashing and verification contract."""

    def hash(self, plain_password: str) -> str:
        """Hash a plain-text password."""

    def verify(self, plain_password: str, password_hash: str) -> bool:
        """Verify a plain-text password against a stored hash."""


class TokenServicePort(Protocol):
    """Access token issuance and verification contract."""

    def create_access_token(self, user: User) -> str:
        """Issue a signed access token for an authenticated user."""

    def decode_access_token(self, token: str) -> TokenPayload:
        """Validate and decode an access token."""


class DocumentRepositoryPort(Protocol):
    """Persistence contract for tenant-scoped documents."""

    def save(self, document: Document) -> Document:
        """Persist a new or updated document."""

    def get_by_id(self, tenant_id: UUID, document_id: UUID) -> Document | None:
        """Fetch a document scoped to a tenant."""

    def list_by_tenant(
        self, tenant_id: UUID, folder_id: UUID | None = None
    ) -> list[Document]:
        """List all documents belonging to a tenant, optionally filtered by folder."""


class FolderRepositoryPort(Protocol):
    """Persistence contract for tenant-scoped folders."""

    def save(self, folder: Folder) -> Folder:
        """Persist a folder."""

    def get_by_id(self, tenant_id: UUID, folder_id: UUID) -> Folder | None:
        """Fetch a folder scoped to a tenant."""


class StoragePort(Protocol):
    """Binary object storage contract (local disk, S3, GCS, etc.)."""

    def put_object(self, storage_key: str, content: bytes, mime_type: str) -> str:
        """Store raw bytes and return the canonical storage key."""

    def get_object(self, storage_key: str) -> bytes:
        """Retrieve raw bytes by storage key."""

    def delete_object(self, storage_key: str) -> None:
        """Remove an object from storage."""


class DmsProviderPort(Protocol):
    """Connector contract for external DMS providers (Google Drive, SharePoint, etc.)."""

    def list_changes(
        self, tenant_id: UUID, cursor: str | None = None
    ) -> tuple[list[ExternalDocumentItem], str | None]:
        """Fetch incremental changes from an external DMS and return the next cursor."""

    def download_content(self, tenant_id: UUID, external_id: str) -> bytes:
        """Download binary content for an external document."""

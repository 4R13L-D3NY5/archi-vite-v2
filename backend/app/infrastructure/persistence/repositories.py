"""SQLAlchemy repository adapters implementing application ports."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities import (
    AuditLog,
    Document,
    DocumentSource,
    Folder,
    Role,
    Tenant,
    User,
)
from app.infrastructure.persistence.models import (
    AuditLogModel,
    DocumentModel,
    FolderModel,
    TenantModel,
    UserModel,
)


class SqlAlchemyTenantRepository:
    """PostgreSQL adapter for TenantRepositoryPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: TenantModel) -> Tenant:
        return Tenant(id=row.id, name=row.name, slug=row.slug, created_at=row.created_at)

    def save(self, tenant: Tenant) -> Tenant:
        row = TenantModel(
            id=tenant.id, name=tenant.name, slug=tenant.slug, created_at=tenant.created_at
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def get_by_slug(self, slug: str) -> Tenant | None:
        row = self._session.scalar(select(TenantModel).where(TenantModel.slug == slug))
        return self._to_domain(row) if row else None

    def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        row = self._session.get(TenantModel, tenant_id)
        return self._to_domain(row) if row else None


class SqlAlchemyUserRepository:
    """PostgreSQL adapter for UserRepositoryPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: UserModel) -> User:
        return User(
            id=row.id,
            tenant_id=row.tenant_id,
            email=row.email,
            password_hash=row.password_hash,
            role=Role(row.role),
            is_active=row.is_active,
            created_at=row.created_at,
        )

    def save(self, user: User) -> User:
        row = UserModel(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        row = self._session.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id, UserModel.email == email
            )
        )
        return self._to_domain(row) if row else None

    def get_by_id(self, tenant_id: UUID, user_id: UUID) -> User | None:
        row = self._session.scalar(
            select(UserModel).where(
                UserModel.tenant_id == tenant_id, UserModel.id == user_id
            )
        )
        return self._to_domain(row) if row else None


class SqlAlchemyFolderRepository:
    """PostgreSQL adapter for FolderRepositoryPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: FolderModel) -> Folder:
        return Folder(
            id=row.id,
            tenant_id=row.tenant_id,
            name=row.name,
            parent_id=row.parent_id,
            created_at=row.created_at,
        )

    def save(self, folder: Folder) -> Folder:
        row = FolderModel(
            id=folder.id,
            tenant_id=folder.tenant_id,
            name=folder.name,
            parent_id=folder.parent_id,
            created_at=folder.created_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def get_by_id(self, tenant_id: UUID, folder_id: UUID) -> Folder | None:
        row = self._session.scalar(
            select(FolderModel).where(
                FolderModel.tenant_id == tenant_id, FolderModel.id == folder_id
            )
        )
        return self._to_domain(row) if row else None


class SqlAlchemyDocumentRepository:
    """PostgreSQL adapter for DocumentRepositoryPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: DocumentModel) -> Document:
        return Document(
            id=row.id,
            tenant_id=row.tenant_id,
            folder_id=row.folder_id,
            title=row.title,
            mime_type=row.mime_type,
            storage_key=row.storage_key,
            size_bytes=row.size_bytes,
            source=DocumentSource(row.source),
            external_id=row.external_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def save(self, document: Document) -> Document:
        row = DocumentModel(
            id=document.id,
            tenant_id=document.tenant_id,
            folder_id=document.folder_id,
            title=document.title,
            mime_type=document.mime_type,
            storage_key=document.storage_key,
            size_bytes=document.size_bytes,
            source=document.source.value,
            external_id=document.external_id,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def get_by_id(self, tenant_id: UUID, document_id: UUID) -> Document | None:
        row = self._session.scalar(
            select(DocumentModel).where(
                DocumentModel.tenant_id == tenant_id, DocumentModel.id == document_id
            )
        )
        return self._to_domain(row) if row else None

    def list_by_tenant(
        self, tenant_id: UUID, folder_id: UUID | None = None
    ) -> list[Document]:
        stmt = select(DocumentModel).where(DocumentModel.tenant_id == tenant_id)
        if folder_id is not None:
            stmt = stmt.where(DocumentModel.folder_id == folder_id)
        rows = self._session.scalars(stmt.order_by(DocumentModel.created_at.desc())).all()
        return [self._to_domain(row) for row in rows]


class SqlAlchemyAuditRepository:
    """PostgreSQL adapter for AuditRepositoryPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _to_domain(row: AuditLogModel) -> AuditLog:
        return AuditLog(
            id=row.id,
            tenant_id=row.tenant_id,
            actor_user_id=row.actor_user_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            created_at=row.created_at,
        )

    def record(self, entry: AuditLog) -> AuditLog:
        row = AuditLogModel(
            id=entry.id,
            tenant_id=entry.tenant_id,
            actor_user_id=entry.actor_user_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            created_at=entry.created_at,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return self._to_domain(row)

    def list_by_tenant(self, tenant_id: UUID, limit: int = 50) -> list[AuditLog]:
        rows = self._session.scalars(
            select(AuditLogModel)
            .where(AuditLogModel.tenant_id == tenant_id)
            .order_by(AuditLogModel.created_at.desc())
            .limit(limit)
        ).all()
        return [self._to_domain(row) for row in rows]

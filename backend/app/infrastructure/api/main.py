"""FastAPI HTTP entrypoint wired to application use cases and PostgreSQL adapters."""

from datetime import datetime
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.application.ports import (
    AuditRepositoryPort,
    DocumentRepositoryPort,
    FolderRepositoryPort,
    StoragePort,
    TenantRepositoryPort,
    TokenPayload,
    UserRepositoryPort,
)
from app.application.use_cases.auth import (
    LoginCommand,
    LoginUseCase,
    RegisterTenantCommand,
    RegisterTenantUseCase,
)
from app.application.use_cases.documents import (
    ListAuditLogsUseCase,
    ListDocumentsUseCase,
    UploadDocumentCommand,
    UploadDocumentUseCase,
)
from app.domain.entities import AuditLog, Document, DocumentSource, Role
from app.domain.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    UnauthorizedActionError,
    ValidationError,
)
from app.infrastructure.config import get_settings
from app.infrastructure.persistence.database import get_db
from app.infrastructure.persistence.repositories import (
    SqlAlchemyAuditRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyFolderRepository,
    SqlAlchemyTenantRepository,
    SqlAlchemyUserRepository,
)
from app.infrastructure.security.auth_adapters import (
    BcryptPasswordHasher,
    JwtTokenService,
)
from app.infrastructure.storage.local_storage import LocalStorageAdapter

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.2.0")
_bearer_scheme = HTTPBearer()
_hasher = BcryptPasswordHasher()
_token_service = JwtTokenService(
    secret_key=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
    expire_minutes=settings.jwt_expire_minutes,
)


def get_tenant_repo(db: Session = Depends(get_db)) -> TenantRepositoryPort:
    return SqlAlchemyTenantRepository(db)


def get_user_repo(db: Session = Depends(get_db)) -> UserRepositoryPort:
    return SqlAlchemyUserRepository(db)


def get_folder_repo(db: Session = Depends(get_db)) -> FolderRepositoryPort:
    return SqlAlchemyFolderRepository(db)


def get_document_repo(db: Session = Depends(get_db)) -> DocumentRepositoryPort:
    return SqlAlchemyDocumentRepository(db)


def get_audit_repo(db: Session = Depends(get_db)) -> AuditRepositoryPort:
    return SqlAlchemyAuditRepository(db)


def get_storage() -> StoragePort:
    return LocalStorageAdapter(settings.storage_base_path)


def get_current_actor(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> TokenPayload:
    """Validate Bearer JWT and return authenticated actor claims."""
    try:
        return _token_service.decode_access_token(credentials.credentials)
    except UnauthorizedActionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


class RegisterTenantRequest(BaseModel):
    tenant_name: str
    tenant_slug: str
    admin_email: str
    admin_password: str


class LoginRequest(BaseModel):
    tenant_slug: str
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: UUID
    user_id: UUID
    role: Role


class DocumentResponse(BaseModel):
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


class AuditLogResponse(BaseModel):
    id: UUID
    actor_user_id: UUID
    action: str
    resource_type: str
    resource_id: UUID
    created_at: datetime

    @classmethod
    def from_domain(cls, entry: AuditLog) -> "AuditLogResponse":
        return cls(
            id=entry.id,
            actor_user_id=entry.actor_user_id,
            action=entry.action,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            created_at=entry.created_at,
        )


@app.get("/health")
def health_check() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": settings.app_name}


@app.post("/api/v1/auth/register", response_model=AuthResponse, status_code=201)
def register_tenant(
    payload: RegisterTenantRequest,
    tenant_repo: TenantRepositoryPort = Depends(get_tenant_repo),
    user_repo: UserRepositoryPort = Depends(get_user_repo),
) -> AuthResponse:
    """Create a new tenant workspace and its initial ADMIN user."""
    use_case = RegisterTenantUseCase(tenant_repo, user_repo, _hasher, _token_service)
    try:
        result = use_case.execute(
            RegisterTenantCommand(
                tenant_name=payload.tenant_name,
                tenant_slug=payload.tenant_slug,
                admin_email=payload.admin_email,
                admin_password=payload.admin_password,
            )
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DuplicateEntityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AuthResponse(
        access_token=result.access_token,
        tenant_id=result.tenant.id,
        user_id=result.user.id,
        role=result.user.role,
    )


@app.post("/api/v1/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    tenant_repo: TenantRepositoryPort = Depends(get_tenant_repo),
    user_repo: UserRepositoryPort = Depends(get_user_repo),
) -> AuthResponse:
    """Authenticate an existing user and issue a JWT."""
    use_case = LoginUseCase(tenant_repo, user_repo, _hasher, _token_service)
    try:
        result = use_case.execute(
            LoginCommand(
                tenant_slug=payload.tenant_slug,
                email=payload.email,
                password=payload.password,
            )
        )
    except UnauthorizedActionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    return AuthResponse(
        access_token=result.access_token,
        tenant_id=result.tenant.id,
        user_id=result.user.id,
        role=result.user.role,
    )


@app.post("/api/v1/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    actor: TokenPayload = Depends(get_current_actor),
    file: UploadFile = File(...),
    folder_id: UUID | None = Form(default=None),
    document_repo: DocumentRepositoryPort = Depends(get_document_repo),
    folder_repo: FolderRepositoryPort = Depends(get_folder_repo),
    audit_repo: AuditRepositoryPort = Depends(get_audit_repo),
    storage: StoragePort = Depends(get_storage),
) -> DocumentResponse:
    """Upload a document into the authenticated actor's tenant workspace."""
    content = await file.read()
    use_case = UploadDocumentUseCase(
        document_repo=document_repo,
        storage=storage,
        folder_repo=folder_repo,
        audit_repo=audit_repo,
    )
    try:
        document = use_case.execute(
            UploadDocumentCommand(
                tenant_id=actor.tenant_id,
                actor_user_id=actor.user_id,
                actor_role=actor.role,
                title=file.filename or "untitled",
                mime_type=file.content_type or "application/octet-stream",
                content=content,
                folder_id=folder_id,
            )
        )
    except UnauthorizedActionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return DocumentResponse.from_domain(document)


@app.get("/api/v1/documents", response_model=list[DocumentResponse])
def list_documents(
    actor: TokenPayload = Depends(get_current_actor),
    folder_id: UUID | None = None,
    document_repo: DocumentRepositoryPort = Depends(get_document_repo),
) -> list[DocumentResponse]:
    """List documents belonging to the authenticated actor's tenant."""
    use_case = ListDocumentsUseCase(document_repo=document_repo)
    docs = use_case.execute(tenant_id=actor.tenant_id, folder_id=folder_id)
    return [DocumentResponse.from_domain(doc) for doc in docs]


@app.get("/api/v1/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    actor: TokenPayload = Depends(get_current_actor),
    limit: int = 50,
    audit_repo: AuditRepositoryPort = Depends(get_audit_repo),
) -> list[AuditLogResponse]:
    """List tenant audit logs (ADMIN only)."""
    use_case = ListAuditLogsUseCase(audit_repo=audit_repo)
    try:
        entries = use_case.execute(
            tenant_id=actor.tenant_id, actor_role=actor.role, limit=limit
        )
    except UnauthorizedActionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return [AuditLogResponse.from_domain(entry) for entry in entries]

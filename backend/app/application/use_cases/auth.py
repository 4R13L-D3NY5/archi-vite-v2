"""Authentication and tenant onboarding use cases."""

from dataclasses import dataclass

from app.application.ports import (
    PasswordHasherPort,
    TenantRepositoryPort,
    TokenServicePort,
    UserRepositoryPort,
)
from app.domain.entities import Role, Tenant, User
from app.domain.exceptions import (
    DuplicateEntityError,
    UnauthorizedActionError,
    ValidationError,
)


@dataclass(frozen=True)
class RegisterTenantCommand:
    """Input for creating a new organization workspace and its admin user."""

    tenant_name: str
    tenant_slug: str
    admin_email: str
    admin_password: str


@dataclass(frozen=True)
class AuthResult:
    """Result returned after successful registration or login."""

    tenant: Tenant
    user: User
    access_token: str


@dataclass(frozen=True)
class LoginCommand:
    """Input for authenticating a user within a tenant workspace."""

    tenant_slug: str
    email: str
    password: str


class RegisterTenantUseCase:
    """Create a tenant and its initial ADMIN user."""

    def __init__(
        self,
        tenant_repo: TenantRepositoryPort,
        user_repo: UserRepositoryPort,
        hasher: PasswordHasherPort,
        token_service: TokenServicePort,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._hasher = hasher
        self._token_service = token_service

    def execute(self, command: RegisterTenantCommand) -> AuthResult:
        """Validate uniqueness, hash password, persist entities, and issue JWT."""
        if len(command.admin_password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")

        normalized_slug = command.tenant_slug.strip().lower()
        if self._tenant_repo.get_by_slug(normalized_slug) is not None:
            raise DuplicateEntityError(
                f"Tenant with slug '{normalized_slug}' already exists."
            )

        tenant = self._tenant_repo.save(
            Tenant(name=command.tenant_name.strip(), slug=normalized_slug)
        )
        user = self._user_repo.save(
            User(
                tenant_id=tenant.id,
                email=command.admin_email.strip().lower(),
                password_hash=self._hasher.hash(command.admin_password),
                role=Role.ADMIN,
            )
        )
        token = self._token_service.create_access_token(user)
        return AuthResult(tenant=tenant, user=user, access_token=token)


class LoginUseCase:
    """Authenticate an active user within a tenant workspace."""

    def __init__(
        self,
        tenant_repo: TenantRepositoryPort,
        user_repo: UserRepositoryPort,
        hasher: PasswordHasherPort,
        token_service: TokenServicePort,
    ) -> None:
        self._tenant_repo = tenant_repo
        self._user_repo = user_repo
        self._hasher = hasher
        self._token_service = token_service

    def execute(self, command: LoginCommand) -> AuthResult:
        """Verify tenant, user status, and password, then issue JWT."""
        tenant = self._tenant_repo.get_by_slug(command.tenant_slug.strip().lower())
        if tenant is None:
            raise UnauthorizedActionError("Invalid credentials.")

        user = self._user_repo.get_by_email(
            tenant.id, command.email.strip().lower()
        )
        if user is None or not user.is_active:
            raise UnauthorizedActionError("Invalid credentials.")

        if not self._hasher.verify(command.password, user.password_hash):
            raise UnauthorizedActionError("Invalid credentials.")

        token = self._token_service.create_access_token(user)
        return AuthResult(tenant=tenant, user=user, access_token=token)

"""Security adapters for password hashing (bcrypt) and JWT tokens."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

from app.application.ports import TokenPayload
from app.domain.entities import Role, User
from app.domain.exceptions import UnauthorizedActionError


class BcryptPasswordHasher:
    """PasswordHasherPort implementation using bcrypt."""

    def hash(self, plain_password: str) -> str:
        """Hash a plain-text password with a random salt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")

    def verify(self, plain_password: str, password_hash: str) -> bool:
        """Verify a plain-text password against a bcrypt hash."""
        if not password_hash:
            return False
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )


class JwtTokenService:
    """TokenServicePort implementation using PyJWT."""

    def __init__(
        self, secret_key: str, algorithm: str = "HS256", expire_minutes: int = 60
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expire_minutes = expire_minutes

    def create_access_token(self, user: User) -> str:
        """Issue a signed JWT containing user, tenant, and role claims."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "role": user.role.value,
            "iat": now,
            "exp": now + timedelta(minutes=self._expire_minutes),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> TokenPayload:
        """Validate JWT signature/expiration and return TokenPayload."""
        try:
            decoded = jwt.decode(
                token, self._secret_key, algorithms=[self._algorithm]
            )
            return TokenPayload(
                user_id=UUID(decoded["sub"]),
                tenant_id=UUID(decoded["tenant_id"]),
                role=Role(decoded["role"]),
            )
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise UnauthorizedActionError("Invalid or expired token.") from exc

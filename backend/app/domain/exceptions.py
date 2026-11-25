"""Domain-level exceptions independent of any transport or persistence layer."""


class DomainError(Exception):
    """Base class for all domain errors."""


class ValidationError(DomainError):
    """Raised when an entity invariant or domain rule is violated."""


class EntityNotFoundError(DomainError):
    """Raised when a requested domain entity does not exist within the tenant."""


class UnauthorizedActionError(DomainError):
    """Raised when an actor lacks permission for a domain action."""


class DuplicateEntityError(DomainError):
    """Raised when creating an entity that violates uniqueness within its scope."""

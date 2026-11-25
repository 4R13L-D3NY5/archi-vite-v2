"""Unit tests for pure domain entities and invariants."""

from uuid import uuid4

import pytest

from app.domain.entities import Document, Folder, Role, Tenant, User
from app.domain.exceptions import ValidationError


def test_tenant_requires_non_empty_name_and_slug() -> None:
    with pytest.raises(ValidationError):
        Tenant(name="   ", slug="acme")
    with pytest.raises(ValidationError):
        Tenant(name="Acme", slug="")


def test_user_validates_email_and_defaults_to_viewer() -> None:
    tenant_id = uuid4()
    user = User(tenant_id=tenant_id, email="ana@acme.com")
    assert user.role == Role.VIEWER

    with pytest.raises(ValidationError):
        User(tenant_id=tenant_id, email="invalid-email")


def test_document_rejects_negative_size_or_empty_title() -> None:
    tenant_id = uuid4()
    with pytest.raises(ValidationError):
        Document(
            tenant_id=tenant_id,
            title="",
            mime_type="application/pdf",
            storage_key="k1",
            size_bytes=10,
        )
    with pytest.raises(ValidationError):
        Document(
            tenant_id=tenant_id,
            title="contract.pdf",
            mime_type="application/pdf",
            storage_key="k1",
            size_bytes=-1,
        )


def test_folder_requires_non_empty_name() -> None:
    with pytest.raises(ValidationError):
        Folder(tenant_id=uuid4(), name="  ")

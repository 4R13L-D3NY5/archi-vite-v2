"""Tests for tenant registration, JWT login, and HTTP RBAC enforcement."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.domain.entities import Role, User
from app.infrastructure.api.main import (
    app,
    get_audit_repo,
    get_document_repo,
    get_folder_repo,
    get_storage,
    get_tenant_repo,
    get_user_repo,
)
from app.infrastructure.persistence.in_memory import (
    InMemoryAuditRepository,
    InMemoryDocumentRepository,
    InMemoryFolderRepository,
    InMemoryTenantRepository,
    InMemoryUserRepository,
)
from app.infrastructure.security.auth_adapters import BcryptPasswordHasher
from app.infrastructure.storage.local_storage import LocalStorageAdapter


def _build_test_client(
    tmp_path: Path,
) -> tuple[TestClient, InMemoryTenantRepository, InMemoryUserRepository]:
    tenant_repo = InMemoryTenantRepository()
    user_repo = InMemoryUserRepository()
    folder_repo = InMemoryFolderRepository()
    doc_repo = InMemoryDocumentRepository()
    audit_repo = InMemoryAuditRepository()
    storage = LocalStorageAdapter(tmp_path)

    app.dependency_overrides[get_tenant_repo] = lambda: tenant_repo
    app.dependency_overrides[get_user_repo] = lambda: user_repo
    app.dependency_overrides[get_folder_repo] = lambda: folder_repo
    app.dependency_overrides[get_document_repo] = lambda: doc_repo
    app.dependency_overrides[get_audit_repo] = lambda: audit_repo
    app.dependency_overrides[get_storage] = lambda: storage

    return TestClient(app), tenant_repo, user_repo


def test_register_login_and_upload_flow(tmp_path: Path) -> None:
    client, _, _ = _build_test_client(tmp_path)
    try:
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "tenant_name": "Acme Corp",
                "tenant_slug": "acme",
                "admin_email": "admin@acme.com",
                "admin_password": "strong-password-123",
            },
        )
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        assert reg.json()["role"] == "admin"

        # Duplicate slug rejected
        dup = client.post(
            "/api/v1/auth/register",
            json={
                "tenant_name": "Acme Two",
                "tenant_slug": "acme",
                "admin_email": "other@acme.com",
                "admin_password": "strong-password-123",
            },
        )
        assert dup.status_code == 409

        # Login succeeds
        login = client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": "acme",
                "email": "admin@acme.com",
                "password": "strong-password-123",
            },
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {token}"}

        # Upload & list documents + audit logs
        upload = client.post(
            "/api/v1/documents",
            headers=headers,
            files={"file": ("report.pdf", b"%PDF-content", "application/pdf")},
        )
        assert upload.status_code == 201

        docs = client.get("/api/v1/documents", headers=headers)
        assert docs.status_code == 200
        assert len(docs.json()) == 1

        audits = client.get("/api/v1/audit-logs", headers=headers)
        assert audits.status_code == 200
        assert len(audits.json()) == 1
        assert audits.json()[0]["action"] == "document.uploaded"
    finally:
        app.dependency_overrides.clear()


def test_viewer_http_upload_returns_403(tmp_path: Path) -> None:
    client, tenant_repo, user_repo = _build_test_client(tmp_path)
    try:
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "tenant_name": "Beta LLC",
                "tenant_slug": "beta",
                "admin_email": "admin@beta.com",
                "admin_password": "strong-password-123",
            },
        )
        tenant_id = tenant_repo.get_by_slug("beta").id  # type: ignore[union-attr]
        user_repo.save(
            User(
                tenant_id=tenant_id,
                email="viewer@beta.com",
                password_hash=BcryptPasswordHasher().hash("viewer-pass-123"),
                role=Role.VIEWER,
            )
        )
        assert reg.status_code == 201

        viewer_login = client.post(
            "/api/v1/auth/login",
            json={
                "tenant_slug": "beta",
                "email": "viewer@beta.com",
                "password": "viewer-pass-123",
            },
        )
        assert viewer_login.status_code == 200
        viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['access_token']}"}

        upload = client.post(
            "/api/v1/documents",
            headers=viewer_headers,
            files={"file": ("secret.pdf", b"data", "application/pdf")},
        )
        assert upload.status_code == 403
    finally:
        app.dependency_overrides.clear()

"""Tests for Google Drive, WebDAV DMS adapters, and HTTP integration endpoints."""

from pathlib import Path
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.domain.entities import DocumentSource, IntegrationConnection
from app.infrastructure.api.main import (
    app,
    get_audit_repo,
    get_dms_providers,
    get_document_repo,
    get_folder_repo,
    get_integration_repo,
    get_storage,
    get_tenant_repo,
    get_user_repo,
)
from app.infrastructure.dms.google_drive_adapter import GoogleDriveAdapter
from app.infrastructure.dms.webdav_dms_adapter import WebDavDmsAdapter
from app.infrastructure.persistence.in_memory import (
    InMemoryAuditRepository,
    InMemoryDocumentRepository,
    InMemoryFolderRepository,
    InMemoryIntegrationRepository,
    InMemoryTenantRepository,
    InMemoryUserRepository,
)
from app.infrastructure.storage.local_storage import LocalStorageAdapter


def _mock_google_drive_client() -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/drive/v3/changes/startPageToken":
            return httpx.Response(200, json={"startPageToken": "page-1"})
        if request.url.path == "/drive/v3/changes":
            return httpx.Response(
                200,
                json={
                    "newStartPageToken": "page-2",
                    "changes": [
                        {
                            "fileId": "drv-1",
                            "removed": False,
                            "file": {
                                "id": "drv-1",
                                "name": "proposal.pdf",
                                "mimeType": "application/pdf",
                                "size": "12",
                            },
                        },
                        {
                            "fileId": "drv-folder",
                            "removed": False,
                            "file": {
                                "id": "drv-folder",
                                "name": "My Folder",
                                "mimeType": "application/vnd.google-apps.folder",
                            },
                        },
                    ],
                },
            )
        if request.url.path == "/drive/v3/files/drv-1":
            return httpx.Response(200, content=b"%PDF-drive-1")
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _mock_webdav_client() -> httpx.Client:
    xml_body = """<?xml version="1.0" encoding="utf-8"?>
    <d:multistatus xmlns:d="DAV:">
      <d:response>
        <d:href>/remote.php/dav/files/admin/</d:href>
        <d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat>
      </d:response>
      <d:response>
        <d:href>/remote.php/dav/files/admin/contract%20v2.pdf</d:href>
        <d:propstat>
          <d:prop>
            <d:resourcetype/>
            <d:getcontenttype>application/pdf</d:getcontenttype>
            <d:getcontentlength>13</d:getcontentlength>
          </d:prop>
        </d:propstat>
      </d:response>
    </d:multistatus>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PROPFIND":
            return httpx.Response(207, text=xml_body)
        if request.method == "GET":
            return httpx.Response(200, content=b"webdav-pdf-v2")
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_google_drive_adapter_filters_folders_and_downloads() -> None:
    adapter = GoogleDriveAdapter(http_client=_mock_google_drive_client())
    conn = IntegrationConnection(
        tenant_id=uuid4(),
        provider=DocumentSource.GOOGLE_DRIVE,
        access_token="ya29.fake",
    )

    items, next_cursor = adapter.list_changes(conn)
    assert next_cursor == "page-2"
    assert len(items) == 1
    assert items[0].title == "proposal.pdf"
    assert adapter.download_content(conn, "drv-1") == b"%PDF-drive-1"


def test_webdav_adapter_parses_propfind_and_downloads() -> None:
    adapter = WebDavDmsAdapter(http_client=_mock_webdav_client())
    conn = IntegrationConnection(
        tenant_id=uuid4(),
        provider=DocumentSource.EXTERNAL_DMS,
        access_token="nc-token",
        base_url="https://dms.example.com",
    )

    items, _ = adapter.list_changes(conn)
    assert len(items) == 1
    assert items[0].title == "contract v2.pdf"
    assert adapter.download_content(conn, items[0].external_id) == b"webdav-pdf-v2"


def test_http_connect_and_sync_google_drive_and_webdav(tmp_path: Path) -> None:
    tenant_repo = InMemoryTenantRepository()
    user_repo = InMemoryUserRepository()
    folder_repo = InMemoryFolderRepository()
    doc_repo = InMemoryDocumentRepository()
    audit_repo = InMemoryAuditRepository()
    integration_repo = InMemoryIntegrationRepository()
    storage = LocalStorageAdapter(tmp_path)

    app.dependency_overrides[get_tenant_repo] = lambda: tenant_repo
    app.dependency_overrides[get_user_repo] = lambda: user_repo
    app.dependency_overrides[get_folder_repo] = lambda: folder_repo
    app.dependency_overrides[get_document_repo] = lambda: doc_repo
    app.dependency_overrides[get_audit_repo] = lambda: audit_repo
    app.dependency_overrides[get_integration_repo] = lambda: integration_repo
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_dms_providers] = lambda: {
        DocumentSource.GOOGLE_DRIVE: GoogleDriveAdapter(_mock_google_drive_client()),
        DocumentSource.EXTERNAL_DMS: WebDavDmsAdapter(_mock_webdav_client()),
    }

    client = TestClient(app)
    try:
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "tenant_name": "Gamma SA",
                "tenant_slug": "gamma",
                "admin_email": "admin@gamma.com",
                "admin_password": "strong-password-123",
            },
        )
        headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Connect & sync Google Drive
        assert (
            client.post(
                "/api/v1/integrations/google_drive",
                headers=headers,
                json={"access_token": "ya29.fake"},
            ).status_code
            == 200
        )
        sync_drv = client.post("/api/v1/integrations/google_drive/sync", headers=headers)
        assert sync_drv.status_code == 200
        assert sync_drv.json() == {"synced_count": 1, "next_cursor": "page-2"}

        # Connect & sync WebDAV DMS
        assert (
            client.post(
                "/api/v1/integrations/external_dms",
                headers=headers,
                json={"access_token": "nc-token", "base_url": "https://dms.example.com"},
            ).status_code
            == 200
        )
        sync_dav = client.post("/api/v1/integrations/external_dms/sync", headers=headers)
        assert sync_dav.status_code == 200
        assert sync_dav.json()["synced_count"] == 1

        # Both documents now listed under tenant
        docs = client.get("/api/v1/documents", headers=headers)
        assert docs.status_code == 200
        assert {d["source"] for d in docs.json()} == {"google_drive", "external_dms"}
    finally:
        app.dependency_overrides.clear()

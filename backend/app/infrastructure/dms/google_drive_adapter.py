"""Google Drive REST API v3 adapter implementing DmsProviderPort."""

import httpx

from app.application.ports import ExternalDocumentItem
from app.domain.entities import DocumentSource, IntegrationConnection
from app.domain.exceptions import ValidationError


class GoogleDriveAdapter:
    """Sync incremental changes and file bytes from Google Drive API v3."""

    _BASE_URL = "https://www.googleapis.com/drive/v3"

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._client = http_client

    def _get_client(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=30.0)

    def _headers(self, connection: IntegrationConnection) -> dict[str, str]:
        return {"Authorization": f"Bearer {connection.access_token}"}

    def list_changes(
        self, connection: IntegrationConnection, cursor: str | None = None
    ) -> tuple[list[ExternalDocumentItem], str | None]:
        """Fetch changed non-folder files since pageToken cursor."""
        client = self._get_client()
        close_after = self._client is None
        try:
            page_token = cursor
            if not page_token:
                start_resp = client.get(
                    f"{self._BASE_URL}/changes/startPageToken",
                    headers=self._headers(connection),
                )
                start_resp.raise_for_status()
                page_token = start_resp.json()["startPageToken"]

            resp = client.get(
                f"{self._BASE_URL}/changes",
                params={
                    "pageToken": page_token,
                    "fields": "newStartPageToken,nextPageToken,changes(fileId,removed,file(id,name,mimeType,size))",
                },
                headers=self._headers(connection),
            )
            resp.raise_for_status()
            data = resp.json()
        finally:
            if close_after:
                client.close()

        items: list[ExternalDocumentItem] = []
        for change in data.get("changes", []):
            if change.get("removed"):
                continue
            file_meta = change.get("file") or {}
            mime = file_meta.get("mimeType", "application/octet-stream")
            if mime == "application/vnd.google-apps.folder":
                continue
            items.append(
                ExternalDocumentItem(
                    external_id=file_meta["id"],
                    title=file_meta.get("name", "untitled"),
                    mime_type=mime,
                    size_bytes=int(file_meta.get("size", 0)),
                    source=DocumentSource.GOOGLE_DRIVE,
                )
            )

        next_cursor = data.get("newStartPageToken") or data.get("nextPageToken") or page_token
        return items, next_cursor

    def download_content(
        self, connection: IntegrationConnection, external_id: str
    ) -> bytes:
        """Download binary content for a Google Drive file ID."""
        if not external_id.strip():
            raise ValidationError("external_id cannot be empty.")

        client = self._get_client()
        close_after = self._client is None
        try:
            resp = client.get(
                f"{self._BASE_URL}/files/{external_id}",
                params={"alt": "media"},
                headers=self._headers(connection),
            )
            resp.raise_for_status()
            return resp.content
        finally:
            if close_after:
                client.close()

"""Standard WebDAV / Nextcloud DMS adapter implementing DmsProviderPort."""

import xml.etree.ElementTree as ET
from urllib.parse import unquote

import httpx

from app.application.ports import ExternalDocumentItem
from app.domain.entities import DocumentSource, IntegrationConnection
from app.domain.exceptions import ValidationError


class WebDavDmsAdapter:
    """List and download documents from a WebDAV-compatible DMS (e.g., Nextcloud)."""

    _DAV_NS = {"d": "DAV:"}

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._client = http_client

    def _get_client(self) -> httpx.Client:
        return self._client or httpx.Client(timeout=30.0)

    def _base_url(self, connection: IntegrationConnection) -> str:
        if not connection.base_url:
            raise ValidationError("WebDAV integration requires base_url.")
        return connection.base_url.rstrip("/")

    def _headers(self, connection: IntegrationConnection) -> dict[str, str]:
        return {"Authorization": f"Bearer {connection.access_token}"}

    def list_changes(
        self, connection: IntegrationConnection, cursor: str | None = None
    ) -> tuple[list[ExternalDocumentItem], str | None]:
        """Query WebDAV folder via PROPFIND (Depth: 1) and return file items."""
        base_url = self._base_url(connection)
        client = self._get_client()
        close_after = self._client is None
        try:
            resp = client.request(
                "PROPFIND",
                base_url,
                headers={**self._headers(connection), "Depth": "1"},
            )
            resp.raise_for_status()
            xml_text = resp.text
        finally:
            if close_after:
                client.close()

        root = ET.fromstring(xml_text)
        items: list[ExternalDocumentItem] = []
        for response_el in root.findall("d:response", self._DAV_NS):
            href_el = response_el.find("d:href", self._DAV_NS)
            prop_el = response_el.find(".//d:prop", self._DAV_NS)
            if href_el is None or prop_el is None or not href_el.text:
                continue

            if prop_el.find("d:resourcetype/d:collection", self._DAV_NS) is not None:
                continue

            href = href_el.text
            title = unquote(href.rstrip("/").split("/")[-1])
            mime_el = prop_el.find("d:getcontenttype", self._DAV_NS)
            size_el = prop_el.find("d:getcontentlength", self._DAV_NS)

            items.append(
                ExternalDocumentItem(
                    external_id=href,
                    title=title or "untitled",
                    mime_type=(mime_el.text if mime_el is not None and mime_el.text else "application/octet-stream"),
                    size_bytes=int(size_el.text) if size_el is not None and size_el.text else 0,
                    source=DocumentSource.EXTERNAL_DMS,
                )
            )

        return items, str(len(items))

    def download_content(
        self, connection: IntegrationConnection, external_id: str
    ) -> bytes:
        """Download binary content from WebDAV resource path or URL."""
        base_url = self._base_url(connection)
        target = (
            external_id
            if external_id.startswith("http")
            else f"{base_url}/{external_id.lstrip('/')}"
        )

        client = self._get_client()
        close_after = self._client is None
        try:
            resp = client.get(target, headers=self._headers(connection))
            resp.raise_for_status()
            return resp.content
        finally:
            if close_after:
                client.close()

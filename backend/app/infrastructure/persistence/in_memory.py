"""In-memory repository adapters for unit tests and early local prototyping."""

from uuid import UUID

from app.domain.entities import Document, Folder


class InMemoryDocumentRepository:
    """Thread-unsafe in-memory store for Document entities."""

    def __init__(self) -> None:
        self._items: dict[UUID, Document] = {}

    def save(self, document: Document) -> Document:
        """Store or overwrite a document."""
        self._items[document.id] = document
        return document

    def get_by_id(self, tenant_id: UUID, document_id: UUID) -> Document | None:
        """Return document only if it belongs to tenant_id."""
        doc = self._items.get(document_id)
        if doc is None or doc.tenant_id != tenant_id:
            return None
        return doc

    def list_by_tenant(
        self, tenant_id: UUID, folder_id: UUID | None = None
    ) -> list[Document]:
        """Return all documents for tenant_id, optionally filtered by folder_id."""
        return [
            doc
            for doc in self._items.values()
            if doc.tenant_id == tenant_id
            and (folder_id is None or doc.folder_id == folder_id)
        ]


class InMemoryFolderRepository:
    """In-memory store for Folder entities."""

    def __init__(self) -> None:
        self._items: dict[UUID, Folder] = {}

    def save(self, folder: Folder) -> Folder:
        """Store or overwrite a folder."""
        self._items[folder.id] = folder
        return folder

    def get_by_id(self, tenant_id: UUID, folder_id: UUID) -> Folder | None:
        """Return folder only if it belongs to tenant_id."""
        folder = self._items.get(folder_id)
        if folder is None or folder.tenant_id != tenant_id:
            return None
        return folder

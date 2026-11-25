"""Unit tests for document use cases and tenant isolation."""

from pathlib import Path
from uuid import uuid4

import pytest

from app.application.use_cases.documents import (
    ListDocumentsUseCase,
    UploadDocumentCommand,
    UploadDocumentUseCase,
)
from app.domain.entities import Folder
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.infrastructure.persistence.in_memory import (
    InMemoryDocumentRepository,
    InMemoryFolderRepository,
)
from app.infrastructure.storage.local_storage import LocalStorageAdapter


def test_upload_and_list_documents_are_tenant_isolated(tmp_path: Path) -> None:
    doc_repo = InMemoryDocumentRepository()
    folder_repo = InMemoryFolderRepository()
    storage = LocalStorageAdapter(tmp_path)

    tenant_a = uuid4()
    tenant_b = uuid4()

    upload_uc = UploadDocumentUseCase(doc_repo, storage, folder_repo)
    list_uc = ListDocumentsUseCase(doc_repo)

    saved = upload_uc.execute(
        UploadDocumentCommand(
            tenant_id=tenant_a,
            title="invoice.pdf",
            mime_type="application/pdf",
            content=b"%PDF-1.4 sample",
        )
    )

    assert saved.size_bytes == 15
    assert storage.get_object(saved.storage_key) == b"%PDF-1.4 sample"
    assert len(list_uc.execute(tenant_id=tenant_a)) == 1
    assert len(list_uc.execute(tenant_id=tenant_b)) == 0


def test_upload_rejects_folder_belonging_to_another_tenant(tmp_path: Path) -> None:
    doc_repo = InMemoryDocumentRepository()
    folder_repo = InMemoryFolderRepository()
    storage = LocalStorageAdapter(tmp_path)

    tenant_a = uuid4()
    tenant_b = uuid4()
    folder_b = folder_repo.save(Folder(tenant_id=tenant_b, name="Private B"))

    upload_uc = UploadDocumentUseCase(doc_repo, storage, folder_repo)

    with pytest.raises(EntityNotFoundError):
        upload_uc.execute(
            UploadDocumentCommand(
                tenant_id=tenant_a,
                title="leak.txt",
                mime_type="text/plain",
                content=b"secret",
                folder_id=folder_b.id,
            )
        )


def test_local_storage_blocks_path_traversal(tmp_path: Path) -> None:
    storage = LocalStorageAdapter(tmp_path)
    with pytest.raises(ValidationError):
        storage.put_object("../escape.txt", b"bad", "text/plain")

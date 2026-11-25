"""Unit tests for document use cases, RBAC, audit trail, and tenant isolation."""

from pathlib import Path
from uuid import uuid4

import pytest

from app.application.use_cases.documents import (
    ListAuditLogsUseCase,
    ListDocumentsUseCase,
    UploadDocumentCommand,
    UploadDocumentUseCase,
)
from app.domain.entities import Folder, Role
from app.domain.exceptions import (
    EntityNotFoundError,
    UnauthorizedActionError,
    ValidationError,
)
from app.infrastructure.persistence.in_memory import (
    InMemoryAuditRepository,
    InMemoryDocumentRepository,
    InMemoryFolderRepository,
)
from app.infrastructure.storage.local_storage import LocalStorageAdapter


def test_upload_and_list_documents_are_tenant_isolated(tmp_path: Path) -> None:
    doc_repo = InMemoryDocumentRepository()
    folder_repo = InMemoryFolderRepository()
    audit_repo = InMemoryAuditRepository()
    storage = LocalStorageAdapter(tmp_path)

    tenant_a = uuid4()
    tenant_b = uuid4()
    actor_a = uuid4()

    upload_uc = UploadDocumentUseCase(doc_repo, storage, folder_repo, audit_repo)
    list_uc = ListDocumentsUseCase(doc_repo)

    saved = upload_uc.execute(
        UploadDocumentCommand(
            tenant_id=tenant_a,
            actor_user_id=actor_a,
            actor_role=Role.EDITOR,
            title="invoice.pdf",
            mime_type="application/pdf",
            content=b"%PDF-1.4 sample",
        )
    )

    assert saved.size_bytes == 15
    assert storage.get_object(saved.storage_key) == b"%PDF-1.4 sample"
    assert len(list_uc.execute(tenant_id=tenant_a)) == 1
    assert len(list_uc.execute(tenant_id=tenant_b)) == 0

    logs = ListAuditLogsUseCase(audit_repo).execute(
        tenant_id=tenant_a, actor_role=Role.ADMIN
    )
    assert len(logs) == 1
    assert logs[0].action == "document.uploaded"
    assert logs[0].resource_id == saved.id


def test_viewer_cannot_upload_or_read_audit_logs(tmp_path: Path) -> None:
    doc_repo = InMemoryDocumentRepository()
    audit_repo = InMemoryAuditRepository()
    storage = LocalStorageAdapter(tmp_path)
    upload_uc = UploadDocumentUseCase(doc_repo, storage, audit_repo=audit_repo)

    with pytest.raises(UnauthorizedActionError):
        upload_uc.execute(
            UploadDocumentCommand(
                tenant_id=uuid4(),
                actor_user_id=uuid4(),
                actor_role=Role.VIEWER,
                title="blocked.pdf",
                mime_type="application/pdf",
                content=b"nope",
            )
        )

    with pytest.raises(UnauthorizedActionError):
        ListAuditLogsUseCase(audit_repo).execute(
            tenant_id=uuid4(), actor_role=Role.EDITOR
        )


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
                actor_user_id=uuid4(),
                actor_role=Role.ADMIN,
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

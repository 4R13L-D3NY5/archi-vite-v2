"""Local filesystem adapter implementing StoragePort."""

from pathlib import Path

from app.domain.exceptions import EntityNotFoundError, ValidationError


class LocalStorageAdapter:
    """Store binary objects safely on local disk under a fixed base directory."""

    def __init__(self, base_path: str | Path) -> None:
        self._base_path = Path(base_path).resolve()
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        target = (self._base_path / storage_key).resolve()
        if not target.is_relative_to(self._base_path):
            raise ValidationError("Invalid storage_key: path traversal detected.")
        return target

    def put_object(self, storage_key: str, content: bytes, mime_type: str) -> str:
        """Write object bytes to disk and return the storage key."""
        target = self._resolve_safe_path(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return storage_key

    def get_object(self, storage_key: str) -> bytes:
        """Read object bytes from disk."""
        target = self._resolve_safe_path(storage_key)
        if not target.is_file():
            raise EntityNotFoundError(f"Object not found for key: {storage_key}")
        return target.read_bytes()

    def delete_object(self, storage_key: str) -> None:
        """Delete an object from disk if it exists."""
        target = self._resolve_safe_path(storage_key)
        if target.is_file():
            target.unlink()

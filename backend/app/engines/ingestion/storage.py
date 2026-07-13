import uuid
from abc import ABC, abstractmethod
from pathlib import Path


class Storage(ABC):
    @abstractmethod
    def save(self, data: bytes, *, suffix: str) -> str: ...

    @abstractmethod
    def load(self, key: str) -> bytes: ...


class LocalStorage(Storage):
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, *, suffix: str) -> str:
        key = f"{uuid.uuid4().hex}{suffix}"
        (self._base / key).write_bytes(data)
        return key

    def load(self, key: str) -> bytes:
        return (self._base / key).read_bytes()


def get_storage(settings) -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_local_path)
    raise ValueError(f"Unknown storage backend: {settings.storage_backend}")
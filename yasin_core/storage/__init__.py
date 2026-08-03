from yasin_core.storage.base import BaseStorage
from yasin_core.storage.json_file import JSONFileStorage
from yasin_core.storage.in_memory import InMemoryStorage
from yasin_core.storage.exceptions import (
    StorageError,
    StorageConnectionError,
    StorageNotFoundError,
    StorageValidationError,
)

_BACKENDS = {"json": JSONFileStorage, "in-memory": InMemoryStorage}


def register_backend(name: str, backend_class):
    _BACKENDS[name] = backend_class


def get_storage(backend_type: str, **kwargs) -> BaseStorage:
    if backend_type not in _BACKENDS:
        raise ValueError(f"Unknown storage backend: {backend_type}")
    try:
        return _BACKENDS[backend_type](**kwargs)
    except Exception as e:
        raise StorageConnectionError(
            f"Failed to initialize storage backend '{backend_type}': {e}"
        ) from e

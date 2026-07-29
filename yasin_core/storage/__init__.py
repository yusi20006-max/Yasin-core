from yasin_core.storage.base import BaseStorage
from yasin_core.storage.json_file import JSONFileStorage


_BACKENDS = {
    "json": JSONFileStorage
}


def register_backend(name, backend_class):

    _BACKENDS[name] = backend_class


def get_storage(backend_type, **kwargs) -> BaseStorage:

    if backend_type not in _BACKENDS:

        raise ValueError(f"Unknown storage backend: {backend_type}")

    return _BACKENDS[backend_type](**kwargs)

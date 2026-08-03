import os
import pytest
from unittest.mock import MagicMock, patch

from yasin_core.storage.exceptions import (
    StorageError,
    StorageConnectionError,
    StorageNotFoundError,
    StorageValidationError,
)
from yasin_core.storage.base import BaseStorage
from yasin_core.storage.in_memory import InMemoryStorage
from yasin_core.storage.json_file import JSONFileStorage
from yasin_core.storage import get_storage, register_backend
from yasin_core.sdk import YasinCoreClient
from yasin_core.runtime.service_manager import RuntimeServiceManager
from yasin_core.runtime.models import ServiceMetadata
from yasin_core.memory.persistent import StorageBackedLongTermMemory
from yasin_core.context.engine import ContextEngine, RuntimeContext


def test_in_memory_storage_provider():
    storage = InMemoryStorage()

    # Initial state and health before initialization
    assert storage.health()["healthy"] is False

    storage.initialize()
    assert storage.health()["healthy"] is True

    # Metadata checks
    meta = storage.metadata
    assert meta["backend_type"] == "in-memory"
    assert meta["persistent"] is False
    assert meta["key_value"] is True

    # Status checks
    status = storage.status()
    assert status["state"] == "active"
    assert status["metadata"] == meta

    # Key-value operations
    assert storage.get("key1") is None
    assert storage.get("key1", "default") == "default"

    storage.set("key1", "value1")
    assert storage.get("key1") == "value1"

    storage.delete("key1")
    assert storage.get("key1") is None

    # Clear operation
    storage.set("a", 1)
    storage.set("b", 2)
    storage.clear()
    assert storage.get("a") is None
    assert storage.get("b") is None

    storage.shutdown()
    assert storage.health()["healthy"] is False


def test_json_file_storage_provider(tmp_path):
    file_path = tmp_path / "test_store.json"
    storage = JSONFileStorage(str(file_path))

    # Initial state should be empty
    assert storage.get("key1") is None

    # Check health and status
    assert storage.health()["healthy"] is True
    meta = storage.metadata
    assert meta["backend_type"] == "json"
    assert meta["persistent"] is True
    assert meta["filepath"] == str(file_path)

    # CRUD operations
    storage.set("k1", "v1")
    assert storage.get("k1") == "v1"

    # Verify persistent state reloading
    storage_reloaded = JSONFileStorage(str(file_path))
    assert storage_reloaded.get("k1") == "v1"

    # Test reload() lifecycle method
    storage.set("k2", "v2")
    storage_reloaded.reload()
    assert storage_reloaded.get("k2") == "v2"

    # Delete
    storage.delete("k1")
    assert storage.get("k1") is None

    # Clear
    storage.set("a", 100)
    storage.clear()
    assert storage.get("a") is None


def test_storage_failures_and_errors(tmp_path):
    # Testing unknown backend type
    with pytest.raises(ValueError) as exc:
        get_storage("unknown-backend-type")
    assert "Unknown storage backend" in str(exc.value)

    # Test initialization error wrapping
    class FailingStorage(BaseStorage):

        def __init__(self, **kwargs):
            raise RuntimeError("Catastrophic connection failure")

        def get(self, key, default=None):
            pass

        def set(self, key, value):
            pass

        def delete(self, key):
            pass

        def clear(self):
            pass

    register_backend("failing", FailingStorage)

    with pytest.raises(StorageConnectionError) as exc:
        get_storage("failing")
    assert "Failed to initialize storage backend" in str(exc.value)

    # Test path creation failure in JSONFileStorage (using write failure)
    # Using an invalid path like a directory that cannot be created (e.g., inside a file)
    invalid_file = tmp_path / "some_file"
    with open(invalid_file, "w") as f:
        f.write("text")

    # Creating a storage path nested inside a file will cause os.makedirs to fail
    nested_path = invalid_file / "sub_dir" / "db.json"
    storage_fail = JSONFileStorage(str(nested_path))
    with pytest.raises(StorageConnectionError):
        storage_fail.set("test", 123)


def test_runtime_service_manager_integration(tmp_path):
    # Test that storage can be managed by RuntimeServiceManager
    manager = RuntimeServiceManager()
    file_path = tmp_path / "managed_store.json"
    storage = JSONFileStorage(str(file_path))

    meta = ServiceMetadata(
        name="storage_service",
        version="1.8.0",
        dependencies=[],
        description="Core Storage Service",
    )

    manager.register_service(storage, meta)
    assert manager.has_service("storage_service")

    # Initialize via manager
    manager.initialize()
    assert manager.get_service("storage_service") is storage

    # Health check integration
    health_report = manager.health()
    assert health_report["healthy"] is True
    assert "storage_service" in health_report["services"]

    # Reload integration
    manager.reload()

    # Shutdown integration
    manager.shutdown()


def test_yasin_core_client_and_di_integration(tmp_path):
    # Verify YasinCoreClient setup with storage
    file_path = tmp_path / "sdk_store.json"
    persistent_storage = JSONFileStorage(str(file_path))

    client = YasinCoreClient(storage=persistent_storage)

    # Exposes storage property
    assert client.storage is persistent_storage

    # DI Container registration checks
    assert client.di_container.resolve(BaseStorage) is persistent_storage
    assert client.di_container.resolve("storage") is persistent_storage

    # Service Registry integration check
    assert client.service_registry.has_service("storage")

    # Memory system integration: since storage is persistent, long-term memory should use StorageBackedLongTermMemory
    assert isinstance(client._long_term_memory, StorageBackedLongTermMemory)


def test_context_persistence_via_storage():
    engine = ContextEngine()
    storage = InMemoryStorage()
    storage.initialize()

    # Create active context with some values
    ctx = engine.create_context(
        data={"user": "Jules", "role": "engineer"},
        metadata={"session": "12345"},
    )

    # Save single context
    engine.save_context_to_storage(ctx.id, storage)

    # Verify it exists in storage
    serialized_data = storage.get(f"context:{ctx.id}")
    assert serialized_data is not None
    assert serialized_data["id"] == ctx.id
    assert serialized_data["data"]["user"] == "Jules"
    assert serialized_data["metadata"]["session"] == "12345"

    # Create a new engine and load it back
    new_engine = ContextEngine()
    loaded_ctx = new_engine.load_context_from_storage(ctx.id, storage)
    assert loaded_ctx is not None
    assert loaded_ctx.id == ctx.id
    assert loaded_ctx.get("user") == "Jules"
    assert loaded_ctx.metadata["session"] == "12345"
    assert new_engine.has_context(ctx.id)

    # Test save/load all contexts
    ctx2 = engine.create_context(data={"system": "active"})
    engine.save_all_contexts_to_storage(storage)

    another_engine = ContextEngine()
    another_engine.load_all_contexts_from_storage(storage)
    assert another_engine.has_context(ctx.id)
    assert another_engine.has_context(ctx2.id)
    assert another_engine.get_context(ctx2.id).get("system") == "active"


def test_sdk_api_compatibility():
    # Verify SDK level imports
    from yasin_core.sdk import (
        BaseStorage,
        JSONFileStorage,
        InMemoryStorage,
        StorageError,
        StorageConnectionError,
        StorageNotFoundError,
        StorageValidationError,
        get_storage,
        register_backend,
    )

    assert BaseStorage is not None
    assert JSONFileStorage is not None
    assert InMemoryStorage is not None
    assert StorageError is not None
    assert StorageConnectionError is not None
    assert StorageNotFoundError is not None
    assert StorageValidationError is not None
    assert get_storage is not None
    assert register_backend is not None

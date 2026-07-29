import os
from yasin_core.storage import get_storage, register_backend
from yasin_core.storage.base import BaseStorage
from yasin_core.storage.json_file import JSONFileStorage


def test_json_file_storage(tmp_path):

    file_path = tmp_path / "test_storage.json"

    storage = JSONFileStorage(str(file_path))


    # Initial state should be empty
    assert storage.get("key1") is None

    assert storage.get("key1", "default") == "default"


    # Set a value and check it
    storage.set("key1", "value1")

    assert storage.get("key1") == "value1"


    # Verify persistence by creating a new instance loading the same file
    new_storage = JSONFileStorage(str(file_path))

    assert new_storage.get("key1") == "value1"


    # Delete key
    storage.delete("key1")

    assert storage.get("key1") is None


    # Verify deleted in persistent storage too
    fresh_storage = JSONFileStorage(str(file_path))

    assert fresh_storage.get("key1") is None


    # Clear all
    storage.set("a", 1)

    storage.set("b", 2)

    storage.clear()

    assert storage.get("a") is None

    assert storage.get("b") is None


def test_get_storage(tmp_path):

    file_path = tmp_path / "test_get_storage.json"

    storage = get_storage("json", filepath=str(file_path))

    assert isinstance(storage, JSONFileStorage)

    storage.set("hello", "world")

    assert storage.get("hello") == "world"

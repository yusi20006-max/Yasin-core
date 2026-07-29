from yasin_core.memory import (
    InMemoryShortTermMemory,
    InMemoryLongTermMemory,
    StorageBackedLongTermMemory,
)
from yasin_core.storage.json_file import JSONFileStorage


def test_in_memory_short_term_memory():

    memory = InMemoryShortTermMemory()


    # Initial checks
    assert memory.get("key") is None

    assert memory.get("key", "default") == "default"


    # Set & Get
    memory.set("key", "val")

    assert memory.get("key") == "val"


    # Delete
    memory.delete("key")

    assert memory.get("key") is None


    # Clear
    memory.set("a", 1)

    memory.set("b", 2)

    memory.clear()

    assert memory.get("a") is None

    assert memory.get("b") is None


def test_in_memory_long_term_memory():

    memory = InMemoryLongTermMemory()


    # Initial checks
    assert memory.get("key") is None

    assert memory.get("key", "default") == "default"


    # Set & Get
    memory.set("key", "val")

    assert memory.get("key") == "val"


    # Delete
    memory.delete("key")

    assert memory.get("key") is None


    # Clear
    memory.set("a", 1)

    memory.set("b", 2)

    memory.clear()

    assert memory.get("a") is None

    assert memory.get("b") is None


def test_storage_backed_long_term_memory(tmp_path):

    file_path = tmp_path / "persistent_memory.json"

    storage = JSONFileStorage(str(file_path))

    memory = StorageBackedLongTermMemory(storage)


    # Initial checks
    assert memory.get("key") is None


    # Set & Get
    memory.set("key", "val")

    assert memory.get("key") == "val"


    # Verify persistence via new instance
    new_storage = JSONFileStorage(str(file_path))

    new_memory = StorageBackedLongTermMemory(new_storage)

    assert new_memory.get("key") == "val"


    # Delete
    memory.delete("key")

    assert memory.get("key") is None

    # Load from the same file to verify persistence of the deletion
    fresh_storage = JSONFileStorage(str(file_path))

    assert fresh_storage.get("key") is None

import time
import pytest
from datetime import datetime, timezone
from yasin_core.memory import (
    InMemoryShortTermMemory,
    InMemoryLongTermMemory,
    StorageBackedLongTermMemory,
    MemoryEntry,
)
from yasin_core.storage.json_file import JSONFileStorage
from yasin_core.events import EventBus
from yasin_core.sdk import YasinCoreClient
from yasin_core.context.engine import ContextEngine, RuntimeContext


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


# --- NEW COMPREHENSIVE V1.9 MEMORY SYSTEM TESTS ---

def test_memory_entry_creation_and_properties():
    entry = MemoryEntry(key="user_123", value="John Doe", metadata={"role": "admin"})
    assert entry.key == "user_123"
    assert entry.value == "John Doe"
    assert entry.metadata == {"role": "admin"}
    assert entry.created_at is not None
    assert entry.expire_at is None
    assert not entry.is_expired()

    # Test serialization
    serialized = entry.to_dict()
    assert serialized["key"] == "user_123"
    assert serialized["value"] == "John Doe"
    assert serialized["metadata"] == {"role": "admin"}

    # Test deserialization
    deserialized = MemoryEntry.from_dict(serialized)
    assert deserialized.key == entry.key
    assert deserialized.value == entry.value
    assert deserialized.metadata == entry.metadata


def test_memory_expiration_passive_ttl():
    memory = InMemoryShortTermMemory()
    memory.set("temp_token", "secret", ttl=1)  # 1 second TTL
    assert memory.get("temp_token") == "secret"

    # Sleep to exceed TTL
    time.sleep(1.1)
    assert memory.get("temp_token") is None
    assert memory.get_entry("temp_token") is None


def test_memory_search_and_filtering():
    memory = InMemoryShortTermMemory()
    memory.set("agent_status", "active", metadata={"type": "agent", "owner": "AI_1"})
    memory.set("user_preferences", "dark_mode", metadata={"type": "user", "owner": "human_1"})
    memory.set("app_config", "v1.2", metadata={"type": "system"})

    # Search (matching key, value, metadata key/value)
    results = memory.search("agent")
    assert len(results) == 1
    assert results[0].key == "agent_status"

    results_value = memory.search("dark_mode")
    assert len(results_value) == 1
    assert results_value[0].key == "user_preferences"

    # Filter by metadata
    filtered = memory.filter({"type": "agent"})
    assert len(filtered) == 1
    assert filtered[0].key == "agent_status"

    filtered_owner = memory.filter({"owner": "human_1"})
    assert len(filtered_owner) == 1
    assert filtered_owner[0].key == "user_preferences"


def test_memory_event_bus_publishing():
    event_bus = EventBus()
    events_triggered = []

    def on_memory_saved(event):
        events_triggered.append(event)

    event_bus.subscribe("memory_saved", on_memory_saved)

    memory = InMemoryShortTermMemory(event_bus=event_bus)
    memory.set("test_key", "test_val", metadata={"test": "meta"})

    assert len(events_triggered) == 1
    assert events_triggered[0].payload["key"] == "test_key"
    assert events_triggered[0].payload["category"] == "short-term"


def test_storage_backed_long_term_memory_v1_9_features(tmp_path):
    file_path = tmp_path / "persistent_v1_9.json"
    storage = JSONFileStorage(str(file_path))
    event_bus = EventBus()

    memory = StorageBackedLongTermMemory(storage, event_bus=event_bus)
    memory.set("persist_key", "persist_val", metadata={"category": "audit"}, ttl=5)

    # Retrieve entry and inspect metadata
    entry = memory.get_entry("persist_key")
    assert entry is not None
    assert entry.value == "persist_val"
    assert entry.metadata == {"category": "audit"}

    # Test search and filter
    search_results = memory.search("audit")
    assert len(search_results) == 1
    assert search_results[0].key == "persist_key"

    filter_results = memory.filter({"category": "audit"})
    assert len(filter_results) == 1


def test_context_engine_memory_integration():
    client = YasinCoreClient()
    context_engine = client.context_engine

    # Create context and make it active
    ctx = context_engine.create_context(data={"env": "prod"})
    from yasin_core.context.manager import active_context
    with active_context(ctx):
        # Save memory should automatically tag the context ID
        client.save_memory("session_token", "12345", category="short-term")
        client.save_memory("session_audit", "success", category="long-term")

    # Retrieve memories belonging to this context ID via ContextEngine
    memories = context_engine.retrieve_context_memories(ctx.id, client)

    assert len(memories["short-term"]) == 1
    assert memories["short-term"][0]["key"] == "session_token"
    assert memories["short-term"][0]["metadata"]["context_id"] == ctx.id

    assert len(memories["long-term"]) == 1
    assert memories["long-term"][0]["key"] == "session_audit"


def test_memory_health_and_status_reporting():
    memory = InMemoryShortTermMemory()
    memory.set("k1", "v1")
    memory.set("k2", "v2")

    # Test health check
    health = memory.health()
    assert health["status"] == "healthy"
    assert health["total_entries"] == 2

    # Test status check
    status = memory.status()
    assert status["state"] == "active"
    assert status["total_entries"] == 2
    assert "k1" in status["keys"]
    assert "k2" in status["keys"]


def test_failure_handling_and_fallback_backward_compatibility(tmp_path):
    file_path = tmp_path / "legacy_corrupted.json"
    storage = JSONFileStorage(str(file_path))

    # Manually seed a primitive non-dict value (simulating old unstructured legacy store)
    storage.set("legacy_key", "legacy_raw_value")

    memory = StorageBackedLongTermMemory(storage)

    # Check that reading still works backward-compatibly without crashing
    assert memory.get("legacy_key") == "legacy_raw_value"

    # Test invalid values and edge cases
    with pytest.raises(ValueError):
        YasinCoreClient().save_memory("key", "val", category="invalid-category")

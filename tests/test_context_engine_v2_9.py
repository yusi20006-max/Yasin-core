import pytest
import time
import datetime
from yasin_core.sdk import YasinCoreClient
from yasin_core.context.engine import ContextEngine, RuntimeContext
from yasin_core.context.manager import active_context, get_current_context
from yasin_core.storage.in_memory import InMemoryStorage


def test_context_expiration_and_auto_pruning():
    client = YasinCoreClient()
    engine = client.context_engine

    # Create a short-term context with 0.1 seconds TTL
    ctx = engine.create_context(
        data={"temp": "value"},
        ttl=0.1,
        tags=["short-term"]
    )

    assert ctx.id is not None
    assert ctx.ttl == 0.1
    assert "short-term" in ctx.tags
    assert ctx.expires_at is not None
    assert ctx.is_expired() is False

    # Retrieve context before expiry
    assert engine.get_context(ctx.id) is ctx

    # Wait for expiry
    time.sleep(0.15)

    # Verify context is considered expired
    assert ctx.is_expired() is True

    # Retrieve context after expiry: should handle expiration and return None
    expired_retrieval = engine.get_context(ctx.id)
    assert expired_retrieval is None

    # Verify it is removed from active list and status
    assert ctx.id not in engine.list_contexts()
    assert ctx.active is False


def test_context_tag_filtering_and_updates():
    client = YasinCoreClient()
    engine = client.context_engine

    ctx1 = engine.create_context(data={"name": "prod-db"}, tags=["database", "prod"])
    ctx2 = engine.create_context(data={"name": "test-db"}, tags=["database", "test"])
    ctx3 = engine.create_context(data={"name": "workflow"}, tags=["workflows", "test"])

    # Test filtering by tags
    db_test_contexts = engine.list_contexts(tags=["database"])
    assert ctx1.id in db_test_contexts
    assert ctx2.id in db_test_contexts
    assert ctx3.id not in db_test_contexts

    prod_contexts = engine.list_contexts(tags=["prod"])
    assert ctx1.id in prod_contexts
    assert ctx2.id not in prod_contexts

    test_workflows = engine.list_contexts(tags=["test", "workflows"])
    assert ctx3.id in test_workflows
    assert ctx2.id not in test_workflows

    # Update metadata and data
    engine.update_context_metadata(ctx1.id, {"owner": "platform", "env": "prod"})
    assert ctx1.metadata["owner"] == "platform"
    assert ctx1.metadata["env"] == "prod"

    engine.update_context_data(ctx1.id, {"connection_limit": 100})
    assert ctx1.get("connection_limit") == 100
    assert ctx1.get("name") == "prod-db"  # Original preserved

    # Add tags
    engine.add_tags(ctx1.id, ["aws", "cloud"])
    assert "aws" in ctx1.tags
    assert "cloud" in ctx1.tags


def test_parent_child_workflow_propagation():
    client = YasinCoreClient()
    engine = client.context_engine

    # Parent workflow context
    parent = engine.create_context(data={"shared_secret": "xyz123", "step": 1})

    # Child task context inheriting from parent
    child = engine.create_context(data={"step": 2, "local_data": "abc"}, parent_id=parent.id)

    # Local resolution
    assert child.get("local_data") == "abc"
    # Overridden value
    assert child.get("step") == 2
    # Fallback to parent
    assert child.get("shared_secret") == "xyz123"


def test_sdk_compatibility_and_event_bus():
    client = YasinCoreClient()
    events_received = []

    # Subscribe to context lifecycle events
    client.event_bus.subscribe("context_created", lambda ev: events_received.append(("created", ev.payload)))
    client.event_bus.subscribe("context_updated", lambda ev: events_received.append(("updated", ev.payload)))
    client.event_bus.subscribe("context_deleted", lambda ev: events_received.append(("deleted", ev.payload)))
    client.event_bus.subscribe("context_expired", lambda ev: events_received.append(("expired", ev.payload)))

    # 1. Create Context
    ctx = client.create_context(data={"session": "active"}, metadata={"source": "sdk"}, ttl=10.0, tags=["sdk-test"])
    assert ctx is not None
    assert len(events_received) == 1
    assert events_received[0][0] == "created"
    assert events_received[0][1]["context_id"] == ctx.id

    # 2. Update Context
    client.update_context_metadata(ctx.id, {"priority": "high"})
    assert len(events_received) == 2
    assert events_received[1][0] == "updated"
    assert events_received[1][1]["context_id"] == ctx.id

    # 3. Retrieve Context memories
    # Populate mock memories with matching context_id
    client.save_memory(key="query1", value="cached", category="short-term", metadata={"context_id": ctx.id})
    client.save_memory(key="query2", value="archived", category="long-term", metadata={"context_id": ctx.id})

    memories = client.retrieve_context_memories(ctx.id)
    assert len(memories["short-term"]) >= 1
    assert len(memories["long-term"]) >= 1
    assert memories["short-term"][0]["key"] == "query1"
    assert memories["long-term"][0]["key"] == "query2"

    # 4. Delete Context
    client.delete_context(ctx.id)
    assert len(events_received) == 3
    assert events_received[2][0] == "deleted"
    assert events_received[2][1]["context_id"] == ctx.id


def test_storage_persistence_integration():
    client = YasinCoreClient()
    engine = client.context_engine
    storage = InMemoryStorage()
    storage.initialize()

    original = engine.create_context(
        data={"app": "yasin"},
        metadata={"tier": "backend"},
        ttl=3600,
        tags=["persistence"]
    )

    # Save to storage
    engine.save_context_to_storage(original.id, storage)

    # Retrieve from storage into a new engine instance
    new_engine = ContextEngine()
    loaded = new_engine.load_context_from_storage(original.id, storage)

    assert loaded is not None
    assert loaded.id == original.id
    assert loaded.parent_id == original.parent_id
    assert loaded.metadata == original.metadata
    assert loaded.get("app") == "yasin"
    assert loaded.ttl == original.ttl
    assert loaded.tags == original.tags
    assert loaded.created_at == original.created_at
    assert loaded.updated_at == original.updated_at
    assert loaded.expires_at == original.expires_at

import pytest
import threading
from typing import Dict, Any

from yasin_core.context import RuntimeContext, ContextEngine, active_context, get_current_context
from yasin_core.core.runtime import YasinRuntime
from yasin_core.sdk import YasinCoreClient


def test_context_engine_lifecycle():
    engine = ContextEngine()

    ctx = engine.create_context(
        data={"user": "yasin"},
        metadata={"scope": "testing", "priority": "high"}
    )

    assert ctx.id is not None
    assert ctx.active is True
    assert ctx.get("user") == "yasin"
    assert ctx.metadata == {"scope": "testing", "priority": "high"}

    assert engine.has_context(ctx.id) is True
    assert engine.get_context(ctx.id) is ctx
    assert engine.list_contexts() == [ctx.id]

    # Test status
    status = engine.get_status()
    assert status["total_contexts"] == 1
    assert status["active_contexts"] == 1
    assert status["contexts"][ctx.id]["metadata"]["scope"] == "testing"

    # Delete context
    engine.delete_context(ctx.id)
    assert engine.has_context(ctx.id) is False
    assert ctx.active is False


def test_context_engine_propagation_and_fallback():
    engine = ContextEngine()

    parent = engine.create_context(data={"global_key": "global_value", "override": "parent_val"})
    child = engine.create_context(data={"local_key": "local_value", "override": "child_val"}, parent_id=parent.id)

    # Simple get checks
    assert child.get("local_key") == "local_value"
    assert child.get("override") == "child_val"

    # Falling back to parent
    assert child.get("global_key") == "global_value"

    # Non-existent keys
    assert child.get("non_existent") is None
    assert child.get("non_existent", "default") == "default"


def test_context_serialization():
    engine = ContextEngine()

    original = engine.create_context(
        data={"token": "abc_123"},
        metadata={"type": "auth"},
        parent_id="parent_uuid"
    )

    payload = original.serialize()
    assert payload["id"] == original.id
    assert payload["parent_id"] == "parent_uuid"
    assert payload["metadata"] == {"type": "auth"}
    assert payload["data"] == {"token": "abc_123"}
    assert payload["active"] is True

    # Deserialize
    deserialized = RuntimeContext.deserialize(payload, engine=engine)
    assert deserialized.id == original.id
    assert deserialized.parent_id == "parent_uuid"
    assert deserialized.metadata == {"type": "auth"}
    assert deserialized.get("token") == "abc_123"
    assert deserialized.active is True


def test_context_engine_thread_safety():
    engine = ContextEngine()
    errors = []

    def worker(i):
        try:
            ctx = engine.create_context(data={f"key_{i}": i})
            assert engine.has_context(ctx.id) is True
            assert engine.get_context(ctx.id).get(f"key_{i}") == i
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(engine.list_contexts()) == 15


def test_context_engine_sdk_integration():
    client = YasinCoreClient()
    assert isinstance(client.context_engine, ContextEngine)

    ctx = client.context_engine.create_context(data={"session": "active"})
    assert client.context_engine.has_context(ctx.id) is True

    # Test thread safety/local isolation using baseline context propagation
    with active_context(ctx):
        current = get_current_context()
        assert current.get("session") == "active"


def test_context_engine_runtime_integration():
    runtime = YasinRuntime()
    assert isinstance(runtime.context_engine, ContextEngine)

    # Create dummy context under runtime context engine
    ctx = runtime.context_engine.create_context(data={"system": "ok"}, metadata={"env": "prod"})

    # Check runtime status includes context status snapshot
    status = runtime.status()
    assert "context" in status
    assert status["context"]["total_contexts"] == 1
    assert status["context"]["contexts"][ctx.id]["metadata"]["env"] == "prod"

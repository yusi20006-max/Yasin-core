import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from yasin_core.events import Event, EventBus
from yasin_core.core.runtime import YasinRuntime
from yasin_core.sdk import YasinCoreClient


# 1. Event Model Tests
def test_event_model_creation():
    event = Event(
        name="test_event",
        payload={"foo": "bar"},
        metadata={"source": "pytest"}
    )
    assert event.name == "test_event"
    assert event.payload == {"foo": "bar"}
    assert event.metadata["source"] == "pytest"
    assert "event_id" in event.metadata
    assert "timestamp" in event.metadata
    assert isinstance(event.timestamp, datetime)
    assert isinstance(event.event_id, str)


def test_event_model_dict_compatibility():
    # Since Event inherits from dict, we should be able to access it like a dict
    event = Event(name="test_event", payload={"key1": "value1", "key2": "value2"})
    assert event["key1"] == "value1"
    assert event.get("key2") == "value2"
    assert "key1" in event
    assert list(event.keys()) == ["key1", "key2"]
    assert list(event.values()) == ["value1", "value2"]
    assert list(event.items()) == [("key1", "value1"), ("key2", "value2")]

    # Check that issubclass and isinstance behave nicely
    assert isinstance(event, dict)


def test_event_serialization():
    event = Event(name="test_event", payload={"foo": "bar"}, metadata={"source": "pytest"})
    serialized = event.to_dict()
    assert serialized["name"] == "test_event"
    assert serialized["payload"] == {"foo": "bar"}
    assert serialized["metadata"]["source"] == "pytest"
    assert "event_id" in serialized
    assert "timestamp" in serialized

    deserialized = Event.from_dict(serialized)
    assert deserialized.name == "test_event"
    assert deserialized.payload == {"foo": "bar"}
    assert deserialized.metadata["source"] == "pytest"
    assert deserialized.event_id == event.event_id


# 2. Event Bus Core Tests
def test_event_bus_basic_pub_sub():
    bus = EventBus()
    received = []

    def handler(evt):
        received.append(evt)

    bus.subscribe("my_event", handler)
    bus.publish("my_event", {"hello": "world"})

    assert len(received) == 1
    assert received[0].name == "my_event"
    assert received[0]["hello"] == "world"


def test_event_bus_multiple_listeners():
    bus = EventBus()
    received1 = []
    received2 = []

    bus.subscribe("my_event", received1.append)
    bus.subscribe("my_event", received2.append)

    bus.publish("my_event", {"hello": "world"})

    assert len(received1) == 1
    assert len(received2) == 1
    assert received1[0]["hello"] == "world"
    assert received2[0]["hello"] == "world"


def test_event_bus_wildcard_subscription():
    bus = EventBus()
    received = []

    bus.subscribe("*", received.append)
    bus.publish("event_a", {"id": 1})
    bus.publish("event_b", {"id": 2})

    assert len(received) == 2
    assert received[0].name == "event_a"
    assert received[1].name == "event_b"


def test_event_bus_unsubscribe():
    bus = EventBus()
    received = []

    def handler(evt):
        received.append(evt)

    bus.subscribe("test_event", handler)
    bus.publish("test_event", {"id": 1})
    assert len(received) == 1

    bus.unsubscribe("test_event", handler)
    bus.publish("test_event", {"id": 2})
    assert len(received) == 1  # Should not receive the second event


def test_event_bus_clear():
    bus = EventBus()
    received = []

    bus.subscribe("event1", received.append)
    bus.subscribe("event2", received.append)
    bus.clear()

    bus.publish("event1", {"id": 1})
    bus.publish("event2", {"id": 2})

    assert len(received) == 0


def test_event_bus_filtering():
    bus = EventBus()
    received = []

    # Only receive events where level is "high"
    filter_func = lambda e: e.get("level") == "high"
    bus.subscribe("alert", received.append, filter_func=filter_func)

    bus.publish("alert", {"level": "low"})
    bus.publish("alert", {"level": "high"})
    bus.publish("alert", {"level": "medium"})

    assert len(received) == 1
    assert received[0]["level"] == "high"


def test_event_bus_error_isolation():
    bus = EventBus()
    received = []

    def broken_handler(evt):
        raise ValueError("Something went wrong in subscriber")

    def safe_handler(evt):
        received.append(evt)

    bus.subscribe("test_event", broken_handler)
    bus.subscribe("test_event", safe_handler)

    # Publishing should not raise any exception, and safe_handler should still be executed
    try:
        bus.publish("test_event", {"foo": "bar"})
    except Exception as exc:
        pytest.fail(f"EventBus did not isolate exception: {exc}")

    assert len(received) == 1
    assert received[0]["foo"] == "bar"


def test_event_bus_history():
    bus = EventBus(max_history_size=3)

    bus.publish("event1")
    bus.publish("event2")
    bus.publish("event3")
    bus.publish("event4")

    # History should be limited to 3
    history = bus.get_history()
    assert len(history) == 3
    assert history[0].name == "event2"
    assert history[1].name == "event3"
    assert history[2].name == "event4"

    # Filter history by name
    assert len(bus.get_history(event_name="event3")) == 1
    assert bus.get_history(event_name="event3")[0].name == "event3"

    # Limit history retrieval
    assert len(bus.get_history(limit=2)) == 2
    assert bus.get_history(limit=2)[0].name == "event3"

    # Clear history
    bus.clear_history()
    assert len(bus.get_history()) == 0


# 3. Async/Sync Execution Tests
def test_async_event_handling_coexistence():
    async def run_test():
        bus = EventBus()
        sync_received = []
        async_received = []

        def sync_handler(evt):
            sync_received.append(evt)

        async def async_handler(evt):
            async_received.append(evt)
            await asyncio.sleep(0.01)

        bus.subscribe("test_event", sync_handler)
        bus.subscribe("test_event", async_handler)

        # Publish asynchronously
        await bus.async_publish("test_event", {"mode": "async"})

        # Wait a bit for the async task to yield/finish
        await asyncio.sleep(0.05)

        assert len(sync_received) == 1
        assert sync_received[0]["mode"] == "async"
        assert len(async_received) == 1
        assert async_received[0]["mode"] == "async"

    asyncio.run(run_test())


def test_sync_handler_forced_async():
    async def run_test():
        bus = EventBus()
        received = []

        def sync_handler(evt):
            received.append(evt)

        # Subscribe with async_handle=True
        bus.subscribe("test_event", sync_handler, async_handle=True)
        bus.publish("test_event", {"mode": "background"})

        # Since it is executed in thread pool, wait briefly
        await asyncio.sleep(0.05)

        assert len(received) == 1
        assert received[0]["mode"] == "background"

    asyncio.run(run_test())


# 4. Runtime & DI Integration Tests
def test_runtime_integration():
    runtime = YasinRuntime()
    assert runtime.event_bus is not None
    assert isinstance(runtime.event_bus, EventBus)

    # Check DI container registrations
    bus_from_di = runtime.container.resolve(EventBus)
    assert bus_from_di is runtime.event_bus

    bus_by_name = runtime.container.resolve("event_bus")
    assert bus_by_name is runtime.event_bus


def test_sdk_client_integration():
    client = YasinCoreClient()
    assert client.event_bus is not None
    assert isinstance(client.event_bus, EventBus)

    # Check DI container in client
    bus_from_di = client.di_container.resolve("event_bus")
    assert bus_from_di is client.event_bus

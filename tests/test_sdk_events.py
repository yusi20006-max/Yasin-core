# Progress: [ ] 75%

from typing import Dict, Any, List
import pytest
from yasin_core.sdk import (
    YasinCoreClient,
    BaseAgent,
    Task,
    AGENT_REGISTERED,
    AGENT_REMOVED,
    AGENT_STARTED,
    AGENT_STOPPED,
    TASK_STARTED,
    TASK_COMPLETED,
    TASK_FAILED,
)


class EventTestAgent(BaseAgent):
    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        if input_data.get("fail", False):
            raise ValueError("Execution error")
        return f"Hello, {input_data.get('name', 'world')}"


def test_sdk_event_bus_integration():
    client = YasinCoreClient()
    bus = client.event_bus
    assert bus is not None

    events_received = []

    def log_event(event_name, data):
        events_received.append((event_name, data))

    # Subscribe to all lifecycle and task events
    bus.subscribe(AGENT_REGISTERED, lambda d: log_event(AGENT_REGISTERED, d))
    bus.subscribe(AGENT_REMOVED, lambda d: log_event(AGENT_REMOVED, d))
    bus.subscribe(AGENT_STARTED, lambda d: log_event(AGENT_STARTED, d))
    bus.subscribe(AGENT_STOPPED, lambda d: log_event(AGENT_STOPPED, d))
    bus.subscribe(TASK_STARTED, lambda d: log_event(TASK_STARTED, d))
    bus.subscribe(TASK_COMPLETED, lambda d: log_event(TASK_COMPLETED, d))
    bus.subscribe(TASK_FAILED, lambda d: log_event(TASK_FAILED, d))

    # 1. Register agent
    agent = EventTestAgent(name="event-agent", description="For testing events")
    client.register_agent(agent)

    assert len(events_received) == 1
    assert events_received[-1] == (AGENT_REGISTERED, {"agent_name": "event-agent"})

    # 2. Start agents
    client.start_agents()
    assert len(events_received) == 2
    assert events_received[-1] == (AGENT_STARTED, {"agent_name": "event-agent"})

    # 3. Execute successful task
    task = client.create_task(id="t-success", name="event-agent", input_data={"name": "Alice"})
    executed_task = client.execute_task(task)

    assert executed_task.status == "completed"
    assert executed_task.result == "Hello, Alice"

    # We should have received TASK_STARTED and TASK_COMPLETED
    assert len(events_received) == 4

    # Verify TASK_STARTED details
    started_event = events_received[-2]
    assert started_event[0] == TASK_STARTED
    assert started_event[1]["task_id"] == "t-success"
    assert started_event[1]["task_name"] == "event-agent"
    assert started_event[1]["task"]["status"] == "running"

    # Verify TASK_COMPLETED details
    completed_event = events_received[-1]
    assert completed_event[0] == TASK_COMPLETED
    assert completed_event[1]["task_id"] == "t-success"
    assert completed_event[1]["task_name"] == "event-agent"
    assert completed_event[1]["result"] == "Hello, Alice"
    assert completed_event[1]["task"]["status"] == "completed"

    # 4. Execute failed task
    failed_task = client.create_task(id="t-fail", name="event-agent", input_data={"fail": True})
    executed_failed_task = client.execute_task(failed_task)

    assert executed_failed_task.status == "failed"

    # We should have received TASK_STARTED and TASK_FAILED
    assert len(events_received) == 6

    # Verify TASK_STARTED details
    started_failed_event = events_received[-2]
    assert started_failed_event[0] == TASK_STARTED
    assert started_failed_event[1]["task_id"] == "t-fail"

    # Verify TASK_FAILED details
    failed_event = events_received[-1]
    assert failed_event[0] == TASK_FAILED
    assert failed_event[1]["task_id"] == "t-fail"
    assert failed_event[1]["task_name"] == "event-agent"
    assert "Execution error" in failed_event[1]["error"]
    assert failed_event[1]["task"]["status"] == "failed"

    # 5. Stop agents
    client.stop_agents()
    assert len(events_received) == 7
    assert events_received[-1] == (AGENT_STOPPED, {"agent_name": "event-agent"})

    # 6. Execute task on stopped agent (should auto-start the agent, which triggers AGENT_STARTED)
    auto_start_task = client.create_task(id="t-auto", name="event-agent", input_data={"name": "Bob"})
    executed_auto_task = client.execute_task(auto_start_task)

    assert executed_auto_task.status == "completed"
    assert executed_auto_task.result == "Hello, Bob"

    # Check that AGENT_STARTED was published due to auto-starting
    # Order of events: TASK_STARTED -> AGENT_STARTED -> TASK_COMPLETED
    assert len(events_received) == 10
    assert events_received[-3][0] == TASK_STARTED
    assert events_received[-2][0] == AGENT_STARTED
    assert events_received[-2][1] == {"agent_name": "event-agent"}
    assert events_received[-1][0] == TASK_COMPLETED

    # Stop agents again for completeness
    client.stop_agents()

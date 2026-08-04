import queue
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

from yasin_core.runtime.interfaces import IService, BaseService
from yasin_core.agents.base import BaseAgent
from yasin_core.agents.task import Task
from yasin_core.agents.planner import Planner, SimplePlanner
from yasin_core.agents.executor import TaskExecutor
from yasin_core.utils.logger import get_logger
from yasin_core.events import Event


class IAgentRuntime(IService, ABC):
    """
    Official abstract interface for the Agent Runtime Integration Layer.
    """

    @abstractmethod
    def register_agent(self, agent: BaseAgent) -> None:
        """Register a new agent with proper contract and security permission checks."""
        pass

    @abstractmethod
    def remove_agent(self, name: str) -> Optional[BaseAgent]:
        """Remove a registered agent."""
        pass

    @abstractmethod
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Retrieve a registered agent."""
        pass

    @abstractmethod
    def list_agents(self) -> List[str]:
        """List all registered agent names."""
        pass

    @abstractmethod
    def start_agents(self) -> None:
        """Start all registered agents."""
        pass

    @abstractmethod
    def stop_agents(self) -> None:
        """Stop all registered agents."""
        pass

    @abstractmethod
    def discover_agents_by_capability(self, capability: str) -> List[BaseAgent]:
        """Discover agents matching a given capability."""
        pass

    @abstractmethod
    def save_agent_state(self, name: str) -> None:
        """Persist agent state to ecosystem storage."""
        pass

    @abstractmethod
    def load_agent_state(self, name: str) -> None:
        """Restore agent state from ecosystem storage."""
        pass

    @abstractmethod
    def send_agent_message(self, sender: str, receiver: str, message: Any) -> None:
        """Send a thread-safe message/payload to another agent's inbox."""
        pass

    @abstractmethod
    def retrieve_agent_messages(self, name: str) -> List[Any]:
        """Drain and retrieve all pending messages from an agent's inbox."""
        pass

    @abstractmethod
    def execute_agent_task(self, task: Task) -> Task:
        """Synchronously execute a Task with active context and metrics collection."""
        pass


class AgentRuntime(BaseService, IAgentRuntime):
    """
    Official thread-safe Agent Runtime Integration Layer implementation.
    """

    def __init__(self, client: Any) -> None:
        super().__init__()
        self.client = client
        self._lock = threading.RLock()
        self._agents: Dict[str, BaseAgent] = {}
        self._executor = TaskExecutor(agent_manager=self)
        self._executor.event_bus = client.event_bus
        self.logger = get_logger("AGENT-RUNTIME")

    # Helper properties for delegation to manager/executor if needed
    @property
    def registry(self):
        return self

    @property
    def event_bus(self):
        return self.client.event_bus

    # Registry support for TaskExecutor compatibility
    def get(self, name: str) -> Optional[BaseAgent]:
        return self.get_agent(name)

    def list(self) -> List[str]:
        return self.list_agents()

    def register(self, agent: BaseAgent) -> None:
        self.register_agent(agent)

    def remove(self, name: str) -> Optional[BaseAgent]:
        return self.remove_agent(name)

    def _validate_permission(self, permission: str) -> None:
        if not hasattr(self.client, "security") or not self.client.security:
            return

        # Resolve active subject from context
        from yasin_core.context.manager import get_current_context
        ctx = get_current_context()
        subject = None
        if ctx:
            subject = ctx.get("security_subject")

        if not subject:
            return

        if ":" in permission:
            action, resource = permission.split(":", 1)
        else:
            action, resource = "execute", permission

        self.client.security.validate_runtime_check(subject, action, resource)

    # IAgentRuntime implementation
    def register_agent(self, agent: BaseAgent) -> None:
        # Validate permissions
        if agent.permissions:
            for permission in agent.permissions:
                try:
                    self._validate_permission(permission)
                except Exception as e:
                    self.logger.error(f"Permission validation failed for registering agent '{agent.name}': {e}")
                    raise

        with self._lock:
            self._agents[agent.name] = agent
            self.logger.info(f"Agent '{agent.name}' registered.")
            if self.client.event_bus:
                from yasin_core.sdk import AGENT_REGISTERED
                self.client.event_bus.publish(
                    AGENT_REGISTERED,
                    Event(name=AGENT_REGISTERED, payload={"agent_name": agent.name})
                )

    def remove_agent(self, name: str) -> Optional[BaseAgent]:
        with self._lock:
            agent = self._agents.pop(name, None)
            if agent:
                self.logger.info(f"Agent '{name}' removed.")
                if self.client.event_bus:
                    from yasin_core.sdk import AGENT_REMOVED
                    self.client.event_bus.publish(
                        AGENT_REMOVED,
                        Event(name=AGENT_REMOVED, payload={"agent_name": name})
                    )
            return agent

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        with self._lock:
            return self._agents.get(name)

    def list_agents(self) -> List[str]:
        with self._lock:
            return list(self._agents.keys())

    def start_agents(self) -> None:
        with self._lock:
            self.logger.info("Starting registered agents...")
            for name, agent in self._agents.items():
                if not agent.running:
                    agent.start()
                    agent.running = True
                    self.logger.info(f"Agent '{name}' started.")
                    if self.client.event_bus:
                        from yasin_core.sdk import AGENT_STARTED
                        self.client.event_bus.publish(
                            AGENT_STARTED,
                            Event(name=AGENT_STARTED, payload={"agent_name": name})
                        )

    def stop_agents(self) -> None:
        with self._lock:
            self.logger.info("Stopping registered agents...")
            for name, agent in self._agents.items():
                if agent.running:
                    agent.stop()
                    agent.running = False
                    self.logger.info(f"Agent '{name}' stopped.")
                    if self.client.event_bus:
                        from yasin_core.sdk import AGENT_STOPPED
                        self.client.event_bus.publish(
                            AGENT_STOPPED,
                            Event(name=AGENT_STOPPED, payload={"agent_name": name})
                        )

    def discover_agents_by_capability(self, capability: str) -> List[BaseAgent]:
        with self._lock:
            matching = []
            for agent in self._agents.values():
                if capability in agent.capabilities:
                    matching.append(agent)
            return matching

    def save_agent_state(self, name: str) -> None:
        import copy
        with self._lock:
            agent = self.get_agent(name)
            if not agent:
                raise ValueError(f"Agent '{name}' not found.")
            storage = self.client.storage
            storage.set(f"agent_state_{name}", copy.deepcopy(agent.state))
            self.logger.info(f"Saved state for agent '{name}'.")

    def load_agent_state(self, name: str) -> None:
        import copy
        with self._lock:
            agent = self.get_agent(name)
            if not agent:
                raise ValueError(f"Agent '{name}' not found.")
            storage = self.client.storage
            state_data = storage.get(f"agent_state_{name}", default={})
            agent.state = copy.deepcopy(state_data)
            self.logger.info(f"Loaded state for agent '{name}'.")

    def send_agent_message(self, sender: str, receiver: str, message: Any) -> None:
        with self._lock:
            receiver_agent = self.get_agent(receiver)
            if not receiver_agent:
                raise ValueError(f"Receiver agent '{receiver}' not found.")

            payload = {
                "sender": sender,
                "message": message,
                "timestamp": time.time()
            }
            receiver_agent.inbox.put(payload)
            self.logger.debug(f"Message sent from '{sender}' to '{receiver}'.")
            if self.client.event_bus:
                self.client.event_bus.publish(
                    "agent_message_sent",
                    Event(name="agent_message_sent", payload={
                        "sender": sender,
                        "receiver": receiver,
                        "timestamp": payload["timestamp"]
                    })
                )

    def retrieve_agent_messages(self, name: str) -> List[Any]:
        with self._lock:
            agent = self.get_agent(name)
            if not agent:
                raise ValueError(f"Agent '{name}' not found.")

            messages = []
            while not agent.inbox.empty():
                try:
                    messages.append(agent.inbox.get_nowait())
                except queue.Empty:
                    break
            return messages

    def execute_agent_task(self, task: Task) -> Task:
        # Resolve target agent name
        agent_name = task.input_data.get("agent_name", task.name)
        agent = self.get_agent(agent_name)
        if not agent:
            # Create a failed task response cleanly
            task.status = "failed"
            task.error = f"Agent '{agent_name}' not found."
            return task

        # Check required agent permissions if any before execution
        if agent.permissions:
            for permission in agent.permissions:
                try:
                    self._validate_permission(permission)
                except Exception as e:
                    self.logger.error(f"Permission validation failed executing task '{task.id}' on '{agent_name}': {e}")
                    task.status = "failed"
                    task.error = str(e)
                    return task

        # Setup context and execute
        start_time = time.time()
        self.logger.info(f"Executing task '{task.id}' on agent '{agent_name}'...")

        # Track metrics
        if hasattr(self.client, "observability") and self.client.observability:
            try:
                self.client.observability.metrics.increment("agent_execution_total", {"agent": agent_name})
            except Exception:
                pass

        # Execute using task executor with context
        executed_task = self._executor.execute_task(task)

        duration = time.time() - start_time
        if executed_task.status == "completed":
            # Save to memory context-aware
            try:
                self.client.save_memory(executed_task.id, executed_task.result, category="short-term")
                self.client.save_memory(executed_task.id, executed_task.result, category="long-term")
            except Exception as e:
                self.logger.warning(f"Failed to auto-save execution outcome to memory: {e}")

            if hasattr(self.client, "observability") and self.client.observability:
                try:
                    self.client.observability.metrics.record_execution_time("agent_execution_duration", duration, {"agent": agent_name})
                except Exception:
                    pass
        else:
            if hasattr(self.client, "observability") and self.client.observability:
                try:
                    self.client.observability.error_tracker.track_error(
                        Exception(executed_task.error),
                        metadata={"task_id": task.id, "agent": agent_name}
                    )
                except Exception:
                    pass

        return executed_task

    # BaseService overrides
    def initialize(self) -> None:
        self.start_agents()

    def shutdown(self) -> None:
        self.stop_agents()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            agents_info = {}
            for name, agent in self._agents.items():
                agents_info[name] = {
                    "running": agent.running,
                    "capabilities": agent.capabilities,
                    "inbox_size": agent.inbox.qsize()
                }
            return {
                "state": "active",
                "registered_agents_count": len(self._agents),
                "agents": agents_info
            }

    def health(self) -> Dict[str, Any]:
        return {"status": "healthy"}

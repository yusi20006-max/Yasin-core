import logging
import threading
import time
from enum import Enum
from typing import Dict, Any, List, Optional

from yasin_core.events import Event


class RuntimeState(Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"
    FAILED = "failed"


class OrchestratorError(Exception):
    """Base exception for Runtime Orchestrator errors."""
    pass


class RuntimeOrchestrator:
    """
    Central execution coordinator of Yasin-Core responsible for managing service startup,
    execution lifecycle, coordination, and shutdown across Yasin ecosystem components.
    """

    def __init__(self, runtime: Any):
        """
        Initialize the orchestrator with a reference to the central YasinRuntime.
        """
        self._lock = threading.RLock()
        self.runtime = runtime
        self._state = RuntimeState.UNINITIALIZED
        self._start_time: Optional[float] = None
        self._stop_time: Optional[float] = None
        self.logger = logging.getLogger("YASIN-RUNTIME-ORCHESTRATOR")

    @property
    def state(self) -> RuntimeState:
        with self._lock:
            return self._state

    def _transition_to(self, new_state: RuntimeState) -> None:
        """
        Transitions to a new state thread-safely and publishes an event.
        """
        old_state = self._state
        self._state = new_state
        self.logger.info(f"Runtime lifecycle transition: {old_state.value} -> {new_state.value}")

        # Integrate with Event Bus
        if hasattr(self.runtime, "event_bus") and self.runtime.event_bus:
            try:
                event = Event(
                    name="runtime_state_changed",
                    payload={
                        "old_state": old_state.value,
                        "new_state": new_state.value,
                        "timestamp": time.time()
                    }
                )
                self.runtime.event_bus.publish("runtime_state_changed", event)
                # Also publish state-specific events
                self.runtime.event_bus.publish(f"runtime_{new_state.value}", event)
            except Exception as e:
                self.logger.error(f"Failed to publish runtime lifecycle event: {e}")

    def start(self) -> None:
        """
        Initiates the dependency-aware startup of all registered services.
        """
        with self._lock:
            if self._state == RuntimeState.RUNNING:
                self.logger.warning("Runtime is already running.")
                return

            if self._state == RuntimeState.INITIALIZING:
                raise OrchestratorError("Runtime is currently initializing.")

            self._transition_to(RuntimeState.INITIALIZING)
            self._start_time = time.time()
            self._stop_time = None

            try:
                # Initialize standard configuration first, if available
                if hasattr(self.runtime, "config") and hasattr(self.runtime.config, "initialize"):
                    try:
                        self.runtime.config.initialize()
                    except Exception as e:
                        self.logger.warning(f"Configuration initialization bypassed or failed: {e}")

                # Initialize all registered services in dependency-respecting topological order
                if hasattr(self.runtime, "registry") and self.runtime.registry:
                    self.runtime.registry.initialize_services()

                self._transition_to(RuntimeState.RUNNING)
                self.logger.info("Yasin-Core central runtime orchestrator successfully started.")

            except Exception as e:
                self._transition_to(RuntimeState.FAILED)
                self.logger.error(f"Orchestrator startup sequence failed: {e}")
                raise OrchestratorError(f"Startup sequence failed: {e}") from e

    def stop(self) -> None:
        """
        Coordinates the shutdown sequence, shutting down services in reverse order.
        """
        with self._lock:
            if self._state in (RuntimeState.STOPPED, RuntimeState.UNINITIALIZED):
                self.logger.warning("Runtime is already stopped or uninitialized.")
                return

            self._transition_to(RuntimeState.SHUTTING_DOWN)

            try:
                # Shutdown all services in reverse initialization order
                if hasattr(self.runtime, "registry") and self.runtime.registry:
                    self.runtime.registry.shutdown_services()

                    # Check if any service failed to stop (stays active)
                    status_info = self.runtime.registry.get_status()
                    services_info = status_info.get("services", status_info)
                    for name, info in services_info.items():
                        if name != "services" and isinstance(info, dict) and str(info.get("state")).upper() == "ACTIVE":
                            raise OrchestratorError(f"Service '{name}' failed to stop (remains active).")

                self._stop_time = time.time()
                self._transition_to(RuntimeState.STOPPED)
                self.logger.info("Yasin-Core central runtime orchestrator successfully stopped.")

            except Exception as e:
                self._transition_to(RuntimeState.FAILED)
                self.logger.error(f"Orchestrator shutdown sequence failed: {e}")
                raise OrchestratorError(f"Shutdown sequence failed: {e}") from e

    def reload(self) -> None:
        """
        Reloads configuration and active services dynamically.
        """
        with self._lock:
            if self._state != RuntimeState.RUNNING:
                raise OrchestratorError(f"Cannot reload unless runtime is in RUNNING state. Current: {self._state.value}")

            self.logger.info("Initiating dynamic runtime reload.")
            try:
                if hasattr(self.runtime, "registry") and self.runtime.registry:
                    self.runtime.registry.reload_services()

                if hasattr(self.runtime, "event_bus") and self.runtime.event_bus:
                    self.runtime.event_bus.publish(
                        "runtime_reloaded",
                        Event(name="runtime_reloaded", payload={"timestamp": time.time()})
                    )
                self.logger.info("Runtime reload completed successfully.")
            except Exception as e:
                self.logger.error(f"Dynamic reload failed: {e}")
                raise OrchestratorError(f"Reload failed: {e}") from e

    def health(self) -> Dict[str, Any]:
        """
        Returns a consolidated health report across the core runtime and all services.
        """
        with self._lock:
            is_healthy = self._state in (RuntimeState.RUNNING, RuntimeState.STOPPED)
            services_report = {}

            if hasattr(self.runtime, "registry") and self.runtime.registry:
                try:
                    services_report = self.runtime.registry.get_health()
                    if services_report.get("healthy") is False:
                        is_healthy = False
                except Exception as e:
                    is_healthy = False
                    services_report = {"error": f"Failed to retrieve health: {e}"}

            return {
                "healthy": is_healthy,
                "state": self._state.value,
                "services": services_report.get("services", services_report)
            }

    def status(self) -> Dict[str, Any]:
        """
        Provides a detailed, structured status report of the entire ecosystem.
        """
        with self._lock:
            uptime = 0.0
            if self._start_time:
                end = self._stop_time or time.time()
                uptime = end - self._start_time

            services_status = {}
            if hasattr(self.runtime, "registry") and self.runtime.registry:
                try:
                    services_status = self.runtime.registry.get_status()
                except Exception as e:
                    services_status = {"error": f"Failed to retrieve status: {e}"}

            context_status = {}
            if hasattr(self.runtime, "context_engine") and self.runtime.context_engine:
                try:
                    context_status = self.runtime.context_engine.get_status()
                except Exception as e:
                    context_status = {"error": f"Failed to retrieve context engine status: {e}"}

            # Retrieve details from DI Container if available
            registered_di_services = []
            if hasattr(self.runtime, "container") and self.runtime.container:
                try:
                    registered_di_services = [str(k) for k in self.runtime.container._registrations.keys()]
                except Exception:
                    pass

            return {
                "name": "Yasin Core Runtime Orchestrator",
                "state": self._state.value,
                "running": self._state == RuntimeState.RUNNING,
                "uptime_seconds": uptime,
                "services": services_status.get("services", services_status),
                "contexts": context_status,
                "di_container": {
                    "registered_services": registered_di_services
                }
            }

    def execute_command(self, command: str, *args: Any, **kwargs: Any) -> Any:
        """
        Executes a CLI or distributed runtime control command.
        """
        command_cleaned = command.strip().lower()
        self.logger.info(f"Executing orchestrator command: {command_cleaned}")

        if command_cleaned == "start":
            self.start()
            return {"status": "success", "message": "Runtime started"}
        elif command_cleaned == "stop":
            self.stop()
            return {"status": "success", "message": "Runtime stopped"}
        elif command_cleaned == "reload":
            self.reload()
            return {"status": "success", "message": "Runtime reloaded"}
        elif command_cleaned == "status":
            return self.status()
        elif command_cleaned == "health":
            return self.health()
        else:
            raise ValueError(f"Unknown orchestrator command: '{command}'")

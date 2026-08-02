import logging
from typing import Dict, List, Any, Optional
from .interfaces import IService
from .models import ServiceMetadata, ServiceState
from .exceptions import (
    ServiceError,
    DuplicateServiceError,
    ServiceNotFoundError,
    DependencyError,
    MissingDependencyError,
    CircularDependencyError
)

logger = logging.getLogger("YASIN-RUNTIME-SERVICE-MANAGER")

class RuntimeServiceManager:
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._metadata: Dict[str, ServiceMetadata] = {}
        self._states: Dict[str, ServiceState] = {}
        self._is_initialized = False

    def register_service(self, service: Any, metadata: ServiceMetadata) -> None:
        """
        Register a service with its metadata.
        """
        name = metadata.name
        if name in self._services:
            raise DuplicateServiceError(f"Service with name '{name}' is already registered.")

        self._services[name] = service
        self._metadata[name] = metadata
        self._states[name] = ServiceState.UNINITIALIZED
        logger.info(f"Registered service: {name} (v{metadata.version})")

    def unregister_service(self, name: str) -> None:
        """
        Unregister a service from the manager.
        """
        if name not in self._services:
            raise ServiceNotFoundError(f"Service '{name}' is not registered.")

        dependents = [svc for svc, meta in self._metadata.items() if name in meta.dependencies]
        if dependents:
            raise DependencyError(
                f"Cannot unregister service '{name}' because other services depend on it: {dependents}"
            )

        if self._states[name] == ServiceState.ACTIVE:
            try:
                if hasattr(self._services[name], "shutdown"):
                    self._services[name].shutdown()
            except Exception as e:
                logger.error(f"Error shutting down service '{name}' during unregistration: {e}")

        del self._services[name]
        del self._metadata[name]
        del self._states[name]
        logger.info(f"Unregistered service: {name}")

    def get_service(self, name: str) -> Any:
        """
        Retrieve a registered service instance by name.
        """
        if name not in self._services:
            raise ServiceNotFoundError(f"Service '{name}' was not found.")
        return self._services[name]

    def list_services(self) -> List[str]:
        """
        List all registered service names.
        """
        return list(self._services.keys())

    def has_service(self, name: str) -> bool:
        """
        Check if a service is registered.
        """
        return name in self._services

    def _get_startup_order(self) -> List[str]:
        """
        Determine the correct startup order of registered services based on dependencies
        using a topological sort algorithm.
        Also detects missing and circular dependencies.
        """
        # First, check for missing dependencies
        for name, meta in self._metadata.items():
            for dep in meta.dependencies:
                if dep not in self._services:
                    raise MissingDependencyError(
                        f"Service '{name}' depends on '{dep}', which is not registered."
                    )

        # Build graph and indegrees
        graph = {name: [] for name in self._services}
        # directed edge from A -> B means A must be initialized before B.
        indegree = {name: 0 for name in self._services}
        for name, meta in self._metadata.items():
            for dep in meta.dependencies:
                graph[dep].append(name)
                indegree[name] += 1

        # Queue of nodes with 0 indegree (no dependencies), sorted to maintain deterministic ordering
        queue = sorted([name for name in self._services if indegree[name] == 0])
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in graph[node]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)
            queue.sort()

        if len(order) < len(self._services):
            raise CircularDependencyError("Circular dependency detected among services.")

        return order

    def initialize(self) -> None:
        """
        Initialize all registered services in dependency-respecting order.
        """
        if self._is_initialized:
            logger.warning("RuntimeServiceManager is already initialized.")
            return

        startup_order = self._get_startup_order()
        logger.info(f"Initializing services in order: {startup_order}")

        for name in startup_order:
            self._states[name] = ServiceState.INITIALIZING
            service = self._services[name]
            try:
                if hasattr(service, "initialize"):
                    service.initialize()
                self._states[name] = ServiceState.ACTIVE
            except Exception as e:
                self._states[name] = ServiceState.FAILED
                logger.error(f"Failed to initialize service '{name}': {e}")
                raise ServiceError(f"Service '{name}' initialization failed: {e}") from e

        self._is_initialized = True
        logger.info("All services successfully initialized.")

    def shutdown(self) -> None:
        """
        Shutdown all active services in the reverse order of initialization.
        """
        # Determine shutdown order by reversing startup order
        try:
            startup_order = self._get_startup_order()
        except Exception:
            startup_order = list(self._services.keys())

        shutdown_order = list(reversed(startup_order))
        logger.info(f"Shutting down services in order: {shutdown_order}")

        for name in shutdown_order:
            if self._states.get(name) == ServiceState.ACTIVE:
                service = self._services[name]
                try:
                    if hasattr(service, "shutdown"):
                        service.shutdown()
                    self._states[name] = ServiceState.STOPPED
                except Exception as e:
                    logger.error(f"Error during shutdown of service '{name}': {e}")

        self._is_initialized = False
        logger.info("All services successfully shut down.")

    def reload(self) -> None:
        """
        Reload all registered services in dependency order.
        """
        try:
            startup_order = self._get_startup_order()
        except Exception as e:
            raise ServiceError(f"Cannot reload services due to dependency error: {e}") from e

        logger.info(f"Reloading services in order: {startup_order}")
        for name in startup_order:
            if self._states.get(name) == ServiceState.ACTIVE:
                service = self._services[name]
                try:
                    if hasattr(service, "reload"):
                        service.reload()
                except Exception as e:
                    logger.error(f"Failed to reload service '{name}': {e}")
                    raise ServiceError(f"Service '{name}' reload failed: {e}") from e

    def health(self) -> Dict[str, Any]:
        """
        Check the overall health of the manager and individual services.
        """
        overall_healthy = True
        services_health = {}

        for name, service in self._services.items():
            state = self._states.get(name, ServiceState.UNINITIALIZED)
            if state == ServiceState.FAILED:
                overall_healthy = False
                services_health[name] = {"healthy": False, "state": state.value, "error": "Initialization failed"}
            elif state == ServiceState.ACTIVE:
                try:
                    if hasattr(service, "health"):
                        h_res = service.health()
                        if isinstance(h_res, bool):
                            is_healthy = h_res
                            details = {}
                        elif isinstance(h_res, dict):
                            is_healthy = h_res.get("healthy", True) and h_res.get("status", "healthy") == "healthy"
                            details = h_res
                        else:
                            is_healthy = True
                            details = {"response": h_res}
                    else:
                        is_healthy = True
                        details = {"status": "healthy"}
                except Exception as e:
                    is_healthy = False
                    details = {"error": str(e)}

                if not is_healthy:
                    overall_healthy = False
                services_health[name] = {"healthy": is_healthy, "state": state.value, "details": details}
            else:
                services_health[name] = {"healthy": True, "state": state.value, "details": "Not initialized / Stopped"}

        return {
            "healthy": overall_healthy,
            "services": services_health
        }

    def status(self) -> Dict[str, Any]:
        """
        Report the status of the service manager and registered services.
        """
        services_status = {}
        for name, service in self._services.items():
            state = self._states.get(name, ServiceState.UNINITIALIZED)
            meta = self._metadata[name]

            custom_status = {}
            if state == ServiceState.ACTIVE and hasattr(service, "status"):
                try:
                    res = service.status()
                    if isinstance(res, dict):
                        custom_status = res
                except Exception as e:
                    custom_status = {"status_error": str(e)}

            # Build status for this service
            svc_info = {
                "state": state.value,
                "version": meta.version,
                "dependencies": meta.dependencies,
                "description": meta.description,
            }
            # Safely merge custom_status keys if they do not collide with core status keys
            for k, v in custom_status.items():
                if k not in svc_info:
                    svc_info[k] = v

            services_status[name] = svc_info

        return {
            "initialized": self._is_initialized,
            "service_count": len(self._services),
            "services": services_status
        }

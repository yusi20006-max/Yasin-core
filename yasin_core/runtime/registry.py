import threading
from typing import Dict, Any, List, Optional
from .service_manager import RuntimeServiceManager
from .models import ServiceMetadata
from .exceptions import ServiceNotFoundError, DuplicateServiceError

class RuntimeServiceRegistry:
    """
    Centralized, thread-safe registry responsible for managing and discovering
    runtime services across the Yasin ecosystem.
    """
    def __init__(self, service_manager: Optional[RuntimeServiceManager] = None):
        self._lock = threading.RLock()
        self._manager = service_manager or RuntimeServiceManager()

    def register_service(
        self,
        name: str,
        service: Any,
        version: str = "1.0.0",
        description: str = "",
        dependencies: Optional[List[str]] = None,
        metadata_dict: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a runtime service with metadata in a thread-safe manner.
        """
        deps = dependencies or []
        meta = ServiceMetadata(
            name=name,
            version=version,
            description=description,
            dependencies=deps,
            metadata=metadata_dict or {}
        )
        with self._lock:
            self._manager.register_service(service, meta)

    def unregister_service(self, name: str) -> None:
        """
        Unregister a service from the registry.
        """
        with self._lock:
            self._manager.unregister_service(name)

    def get_service(self, name: str) -> Any:
        """
        Retrieve a registered service instance by name.
        """
        with self._lock:
            return self._manager.get_service(name)

    def has_service(self, name: str) -> bool:
        """
        Check if a service is registered.
        """
        with self._lock:
            return self._manager.has_service(name)

    def list_services(self) -> List[str]:
        """
        List all registered service names.
        """
        with self._lock:
            return self._manager.list_services()

    def get_service_metadata(self, name: str) -> ServiceMetadata:
        """
        Retrieve the metadata associated with a registered service.
        """
        with self._lock:
            if not self._manager.has_service(name):
                raise ServiceNotFoundError(f"Service '{name}' is not registered.")
            return self._manager._metadata[name]

    def initialize_services(self) -> None:
        """
        Initialize all registered services in dependency order.
        """
        with self._lock:
            self._manager.initialize()

    def shutdown_services(self) -> None:
        """
        Shutdown all registered services in reverse order.
        """
        with self._lock:
            self._manager.shutdown()

    def reload_services(self) -> None:
        """
        Reload all registered services in dependency order.
        """
        with self._lock:
            self._manager.reload()

    def get_health(self) -> Dict[str, Any]:
        """
        Retrieve health status of all registered services.
        """
        with self._lock:
            return self._manager.health()

    def get_status(self) -> Dict[str, Any]:
        """
        Retrieve status of the registry and all registered services.
        """
        with self._lock:
            return self._manager.status()

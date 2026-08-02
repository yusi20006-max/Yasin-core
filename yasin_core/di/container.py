import inspect
import threading
import typing
from typing import Any, Callable, Dict, List, Optional, Type, Union

from .exceptions import DependencyResolutionError, CircularDependencyError
from .interfaces import IDIContainer, ServiceLifetime


class Registration:
    def __init__(
        self,
        key: Union[Type, str],
        lifetime: ServiceLifetime,
        factory_or_class: Optional[Union[Type, Callable[..., Any]]] = None,
        instance: Any = None,
    ):
        self.key = key
        self.lifetime = lifetime
        self.factory_or_class = factory_or_class
        self.instance = instance


class DIContainer(IDIContainer):
    """
    A lightweight, thread-safe, and robust Dependency Injection Container
    for Yasin-Core supporting constructor injection, lifetimes, missing
    dependency detection, and circular dependency protection.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._registrations: Dict[Union[Type, str], Registration] = {}
        self._thread_local = threading.local()

    def register_instance(self, key: Union[Type, str], instance: Any) -> None:
        """Register an existing instance directly as a singleton."""
        with self._lock:
            self._registrations[key] = Registration(
                key=key,
                lifetime=ServiceLifetime.SINGLETON,
                instance=instance
            )

    def register_singleton(
        self, key: Union[Type, str], factory_or_class: Union[Type, Callable[..., Any]]
    ) -> None:
        """Register a singleton class or factory function."""
        with self._lock:
            self._registrations[key] = Registration(
                key=key,
                lifetime=ServiceLifetime.SINGLETON,
                factory_or_class=factory_or_class
            )

    def register_transient(
        self, key: Union[Type, str], factory_or_class: Union[Type, Callable[..., Any]]
    ) -> None:
        """Register a transient (factory) class or factory function."""
        with self._lock:
            self._registrations[key] = Registration(
                key=key,
                lifetime=ServiceLifetime.TRANSIENT,
                factory_or_class=factory_or_class
            )

    def has(self, key: Union[Type, str]) -> bool:
        """Check if a service is registered for the given key."""
        with self._lock:
            return self._find_registration(key) is not None

    def _find_registration(self, key: Union[Type, str]) -> Optional[Registration]:
        if key in self._registrations:
            return self._registrations[key]

        if isinstance(key, type):
            for reg_key, reg in self._registrations.items():
                if isinstance(reg_key, type) and issubclass(reg_key, key):
                    return reg
        return None

    def _get_resolving_stack(self) -> List[Any]:
        if not hasattr(self._thread_local, "resolving"):
            self._thread_local.resolving = []
        return self._thread_local.resolving

    def resolve(self, key: Union[Type, str]) -> Any:
        """Resolve and return the requested service instance."""
        with self._lock:
            # 1. Look up registration
            reg = self._find_registration(key)

            if reg is not None:
                # If it's a singleton and has a cached instance, return it immediately
                if reg.lifetime == ServiceLifetime.SINGLETON and reg.instance is not None:
                    return reg.instance

            # 2. Circular dependency check
            stack = self._get_resolving_stack()
            if key in stack:
                path = " -> ".join(map(str, stack + [key]))
                raise CircularDependencyError(f"Circular dependency detected: {path}")

            stack.append(key)
            try:
                if reg is not None:
                    # Construct/execute factory or class
                    if reg.factory_or_class is not None:
                        instance = self._inject_callable(reg.factory_or_class)
                        if reg.lifetime == ServiceLifetime.SINGLETON:
                            reg.instance = instance
                        return instance
                    else:
                        # Fallback for instance-only registrations
                        return reg.instance
                else:
                    # If not registered, but it is a concrete class, we can autowire it
                    if isinstance(key, type):
                        try:
                            return self._inject_constructor(key)
                        except DependencyResolutionError as e:
                            raise DependencyResolutionError(
                                f"Failed to autowire unregistered class '{key.__name__}': {e}"
                            ) from e
                    else:
                        raise DependencyResolutionError(
                            f"No service registered for key '{key}' and it cannot be autowired."
                        )
            finally:
                stack.pop()

    def _inject_constructor(self, cls: Type[Any]) -> Any:
        try:
            sig = inspect.signature(cls.__init__)
        except (ValueError, TypeError):
            # No __init__ signature (e.g., direct built-ins or no custom constructor)
            return cls()

        try:
            type_hints = typing.get_type_hints(cls.__init__)
        except Exception:
            type_hints = {}

        kwargs = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            param_type = type_hints.get(name, param.annotation)
            if param_type is inspect.Parameter.empty:
                param_type = None

            resolved_val = None
            has_resolved = False

            # 1. Resolve by Type
            if param_type and isinstance(param_type, type):
                if self.has(param_type):
                    resolved_val = self.resolve(param_type)
                    has_resolved = True

            # 2. Resolve by Parameter Name
            if not has_resolved:
                if self.has(name):
                    resolved_val = self.resolve(name)
                    has_resolved = True

            # 3. Use default if available
            if not has_resolved:
                if param.default is not inspect.Parameter.empty:
                    resolved_val = param.default
                    has_resolved = True

            # 4. Error if not resolvable
            if not has_resolved:
                type_name = param_type.__name__ if hasattr(param_type, "__name__") else str(param_type)
                raise DependencyResolutionError(
                    f"Cannot resolve parameter '{name}' of type '{type_name}' for class '{cls.__name__}'."
                )

            kwargs[name] = resolved_val

        return cls(**kwargs)

    def _inject_callable(self, func: Callable[..., Any]) -> Any:
        if isinstance(func, type):
            return self._inject_constructor(func)

        try:
            sig = inspect.signature(func)
        except (ValueError, TypeError):
            return func()

        try:
            type_hints = typing.get_type_hints(func)
        except Exception:
            type_hints = {}

        kwargs = {}
        for name, param in sig.parameters.items():
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue

            param_type = type_hints.get(name, param.annotation)
            if param_type is inspect.Parameter.empty:
                param_type = None

            resolved_val = None
            has_resolved = False

            # 1. Resolve by Type
            if param_type and isinstance(param_type, type):
                if self.has(param_type):
                    resolved_val = self.resolve(param_type)
                    has_resolved = True

            # 2. Resolve by Parameter Name
            if not has_resolved:
                if self.has(name):
                    resolved_val = self.resolve(name)
                    has_resolved = True

            # 3. Use default if available
            if not has_resolved:
                if param.default is not inspect.Parameter.empty:
                    resolved_val = param.default
                    has_resolved = True

            # 4. Error if not resolvable
            if not has_resolved:
                type_name = param_type.__name__ if hasattr(param_type, "__name__") else str(param_type)
                raise DependencyResolutionError(
                    f"Cannot resolve parameter '{name}' of type '{type_name}' for callable '{func.__name__}'."
                )

            kwargs[name] = resolved_val

        return func(**kwargs)

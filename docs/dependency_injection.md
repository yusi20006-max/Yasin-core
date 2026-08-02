# Yasin-Core Dependency Injection (DI) Container

Yasin-Core v1.4 introduces a lightweight, thread-safe, and robust **Dependency Injection (DI) Container** designed to provide clean service composition, decouple modular components, and support advanced automated wiring patterns.

---

## Core Capabilities

### 1. Lifetime Management
The DI Container supports two service lifetimes managed via the `ServiceLifetime` enum:
- **`ServiceLifetime.SINGLETON`**: The service is initialized once, cached, and reused across all subsequent resolutions.
- **`ServiceLifetime.TRANSIENT`**: A new service instance is constructed/executed on every `resolve()` call.

### 2. Flexible Registration
You can register services by their type (class), an interface (base class), or a string key:
- `register_instance(key, instance)`: Register a pre-constructed singleton instance.
- `register_singleton(key, factory_or_class)`: Register a singleton class or factory function.
- `register_transient(key, factory_or_class)`: Register a transient class or factory function.

### 3. Automatic Constructor Injection & Autowiring
When resolving a class, the DI container automatically inspects its constructor (`__init__`) and injects required dependencies.
- **Type-based Lookup**: If a parameter is type-hinted with a class, the container looks up that class or any subclass registered in the container.
- **Name-based Lookup**: If type-based lookup fails or is not annotated, the container falls back to resolving by the parameter's variable name (as a string key).
- **Default Fallback**: If a parameter cannot be resolved but has a default value defined, it falls back to using the default.
- **Autowiring**: You can resolve concrete classes even if they aren't explicitly registered, provided all their dependencies can be resolved.

### 4. Circular Dependency Protection
Resolving recursive dependencies (e.g., Service A depending on Service B, which in turn depends on Service A) is automatically intercepted. The container tracks resolutions per-thread and raises a `CircularDependencyError` with the exact path of the cycle.

### 5. Missing Dependency Detection
If a dependency or parameter cannot be resolved, a descriptive `DependencyResolutionError` is raised indicating the parameter name and expected type.

---

## SDK & Runtime Integration

### YasinCoreClient (Public SDK)
The DI Container is exposed directly via the public SDK client:
```python
from yasin_core.sdk import YasinCoreClient

client = YasinCoreClient()
# Access the container
container = client.di_container
```
Upon initialization, the client pre-registers standard ecosystem services for clean composition:
- `YasinCoreClient` & `"client"`
- `RuntimeServiceRegistry` & `"service_registry"`
- `ContextEngine` & `"context_engine"`
- `"event_bus"`

### YasinRuntime
The core runtime integrates a `container` property pre-registered with:
- `DIContainer` & `"container"`
- `YasinRuntime` & `"runtime"`
- `RuntimeServiceRegistry` & `"registry"`
- `ContextEngine` & `"context_engine"`

---

## Code Example

```python
from abc import ABC
from yasin_core.sdk import YasinCoreClient, IDIContainer

# 1. Define interfaces and implementations
class IEngine(ABC):
    pass

class V8Engine(IEngine):
    pass

class Car:
    # Constructor Injection
    def __init__(self, engine: IEngine, model_name: str = "Model S"):
        self.engine = engine
        self.model_name = model_name

# 2. Setup Container and registrations
client = YasinCoreClient()
container = client.di_container

# Register IEngine to resolve to V8Engine (Singleton)
container.register_singleton(IEngine, V8Engine)

# 3. Resolve
# Car is not explicitly registered, but autowiring automatically constructs it!
car = container.resolve(Car)

print(isinstance(car.engine, V8Engine))  # True
print(car.model_name)                   # "Model S"
```

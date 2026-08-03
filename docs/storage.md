# Yasin-Core Storage Abstraction Layer (v1.8)

The Storage Abstraction Layer in Yasin-Core provides a unified, replacement-friendly, thread-safe interface for storage providers, allowing the ecosystem services to store, retrieve, check health, manage lifecycles, and persist execution states uniformly.

---

## Architecture Diagram

```
                 +-----------------------+
                 |    YasinCoreClient    |
                 +-----------+-----------+
                             |
         +-------------------+-------------------+
         | (DI Container)    | (Service Registry)|
         v                   v                   v
+----------------------------+----------------------------+
| Storage Abstraction Layer                               |
|                                                         |
| - BaseStorage (implements IService lifecycle & health)  |
+----------------------------+----------------------------+
         |                                       |
         v (Concrete Implementation)             v (Concrete Implementation)
+----------------------------+       +----------------------------+
| InMemoryStorage            |       | JSONFileStorage            |
| - Thread-safe (RLock)      |       | - Thread-safe (RLock)      |
| - Key-value in memory      |       | - Persistent JSON files    |
+----------------------------+       +----------------------------+
         |                                       |
         v                                       v
+----------------------------+       +----------------------------+
| Context Engine Integration |       | Memory System Integration  |
| - Context serialization    |       | - Storage-backed long-term |
| - Bulk and single context  |       |   memory system            |
|   save and load methods    |       |                            |
+----------------------------+       +----------------------------+
```

---

## Core Components

### 1. `BaseStorage`
An abstract base class (`yasin_core.storage.base.BaseStorage`) which inherits from `IService` to enable direct lifecycle and health integration.
It provides:
- Standard CRUD methods: `get(key, default)`, `set(key, value)`, `delete(key)`, `clear()`.
- Standard Service lifecycle methods: `initialize()`, `shutdown()`, `reload()`.
- Standard health status: `health()`, reporting `{"status": "healthy", "healthy": True}` or detailed diagnostic data.
- Metadata reporting: `metadata` property returning capacities (e.g. `persistent: bool`, `key_value: bool`).

### 2. Concrete Storage Providers
- **`InMemoryStorage`**: A high-performance, thread-safe (`threading.RLock` protected) dictionary storage, ideal for caching, transient operations, and testing.
- **`JSONFileStorage`**: A thread-safe, persistent local JSON file-based storage, featuring automated directory creation, transaction-like file updates, and path validation.

### 3. Custom Exceptions
Under `yasin_core.storage.exceptions`:
- `StorageError`: Base exception for all storage failures.
- `StorageConnectionError`: Raised when storage paths or backends are inaccessible/unwritable.
- `StorageNotFoundError`: Raised when keys/resources cannot be found.
- `StorageValidationError`: Raised when validation of storage records fails.

---

## System Integrations

### 1. Runtime Integration
When `YasinCoreClient` is initialized, the configured storage instance (defaulting to `InMemoryStorage`) is automatically:
- Registered in the Dependency Injection Container (`client.di_container`) under `BaseStorage` and string name `"storage"`.
- Registered in the `RuntimeServiceRegistry` as `"storage"` to participate in unified topological startup/shutdown sequencing and status audits.

### 2. Memory System Integration
If `YasinCoreClient` is initialized with a persistent storage provider (e.g., `JSONFileStorage`) and no custom `long_term_memory` is supplied, the client automatically instantiates `StorageBackedLongTermMemory` as its long-term memory system. This bridges persistent storage with long-term memory seamlessly!

### 3. Context Persistence
`ContextEngine` features native, thread-safe support for saving/loading context variables and status directly to any `BaseStorage` implementation:
- `save_context_to_storage(context_id, storage)`
- `load_context_from_storage(context_id, storage)`
- `save_all_contexts_to_storage(storage)`
- `load_all_contexts_from_storage(storage)`

---

## Usage Example

### Initializing Storage via Client
```python
from yasin_core.sdk import YasinCoreClient, JSONFileStorage

# Initialize persistent JSON storage
storage = JSONFileStorage("data/my_storage.json")

# Initialize client with storage
client = YasinCoreClient(storage=storage)

# Access storage instance anywhere
client.storage.set("app_version", "1.8.0")
print(client.storage.get("app_version"))  # Output: 1.8.0
```

### Context Persistence
```python
from yasin_core.sdk import YasinCoreClient

client = YasinCoreClient()
engine = client.context_engine

# Create context
ctx = engine.create_context(data={"agent_state": "processing"})

# Save it to storage
engine.save_context_to_storage(ctx.id, client.storage)

# Load it in another instance/session
loaded_ctx = engine.load_context_from_storage(ctx.id, client.storage)
print(loaded_ctx.get("agent_state"))  # Output: processing
```

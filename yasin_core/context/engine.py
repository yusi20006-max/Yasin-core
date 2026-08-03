import uuid
import threading
from typing import Dict, Any, List, Optional
from .manager import Context


class RuntimeContext(Context):
    """
    Enhanced RuntimeContext subclassing the baseline Context class to preserve
    backward compatibility while adding unique identification, parent-child inheritance/propagation,
    custom metadata, and serialization.
    """
    def __init__(
        self,
        context_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        engine: Optional["ContextEngine"] = None
    ):
        super().__init__(data)
        self.id = context_id or str(uuid.uuid4())
        self.parent_id = parent_id
        self.metadata = dict(metadata) if metadata is not None else {}
        self._active = True
        self._engine = engine

    @property
    def active(self) -> bool:
        return self._active

    def deactivate(self) -> None:
        self._active = False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve value by key. Supports parent fallback propagation if parent_id is set
        and the engine is available to look up the parent context.
        """
        if key in self._data:
            return self._data[key]
        if self.parent_id and self._engine:
            parent_ctx = self._engine.get_context(self.parent_id)
            if parent_ctx:
                return parent_ctx.get(key, default)
        return default

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize context to a dictionary.
        """
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
            "data": self.to_dict(),
            "active": self._active
        }

    @classmethod
    def deserialize(cls, payload: Dict[str, Any], engine: Optional["ContextEngine"] = None) -> "RuntimeContext":
        """
        Deserialize dictionary back to a RuntimeContext instance.
        """
        ctx = cls(
            context_id=payload.get("id"),
            parent_id=payload.get("parent_id"),
            data=payload.get("data"),
            metadata=payload.get("metadata"),
            engine=engine
        )
        ctx._active = payload.get("active", True)
        return ctx


class ContextEngine:
    """
    Centralized, thread-safe Context Engine responsible for managing the lifecycle,
    lookup, propagation, isolation, and serialization of runtime contexts across the ecosystem.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._contexts: Dict[str, RuntimeContext] = {}

    def create_context(
        self,
        data: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RuntimeContext:
        """
        Create and track a new thread-safe RuntimeContext.
        """
        with self._lock:
            # If parent_id is specified, verify it exists (optional but good practice)
            ctx = RuntimeContext(
                parent_id=parent_id,
                data=data,
                metadata=metadata,
                engine=self
            )
            self._contexts[ctx.id] = ctx
            return ctx

    def get_context(self, context_id: str) -> Optional[RuntimeContext]:
        """
        Retrieve context by ID thread-safely.
        """
        with self._lock:
            return self._contexts.get(context_id)

    def has_context(self, context_id: str) -> bool:
        """
        Check if context exists thread-safely.
        """
        with self._lock:
            return context_id in self._contexts

    def delete_context(self, context_id: str) -> None:
        """
        Delete and deactivate a context by ID thread-safely.
        """
        with self._lock:
            if context_id in self._contexts:
                self._contexts[context_id].deactivate()
                del self._contexts[context_id]

    def list_contexts(self) -> List[str]:
        """
        List all registered context IDs thread-safely.
        """
        with self._lock:
            return list(self._contexts.keys())

    def clear(self) -> None:
        """
        Clear all managed contexts.
        """
        with self._lock:
            for ctx in self._contexts.values():
                ctx.deactivate()
            self._contexts.clear()

    def get_status(self) -> Dict[str, Any]:
        """
        Retrieve context engine status.
        """
        with self._lock:
            active_count = sum(1 for ctx in self._contexts.values() if ctx.active)
            return {
                "total_contexts": len(self._contexts),
                "active_contexts": active_count,
                "contexts": {
                    cid: {
                        "parent_id": ctx.parent_id,
                        "metadata": ctx.metadata,
                        "active": ctx.active
                    }
                    for cid, ctx in self._contexts.items()
                }
            }

    # Context Engine Memory Integration
    def retrieve_context_memories(self, context_id: str, client: Any) -> Dict[str, List[Any]]:
        """
        Query memory segments automatically associated with a given context ID.
        Returns a dictionary grouping short-term and long-term memory entries.
        """
        with self._lock:
            # Filter memories matching metadata {"context_id": context_id}
            filter_dict = {"context_id": context_id}

            st_memories = []
            if hasattr(client, "short_term_memory"):
                st_memories = client.short_term_memory.filter(filter_dict)

            lt_memories = []
            if hasattr(client, "long_term_memory"):
                lt_memories = client.long_term_memory.filter(filter_dict)

            return {
                "short-term": [entry.to_dict() for entry in st_memories],
                "long-term": [entry.to_dict() for entry in lt_memories]
            }

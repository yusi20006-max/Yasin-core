import uuid
import threading
import datetime
from typing import Dict, Any, List, Optional, Union
from .manager import Context
from yasin_core.storage.base import BaseStorage


class RuntimeContext(Context):
    """
    Enhanced RuntimeContext subclassing the baseline Context class to preserve
    backward compatibility while adding unique identification, parent-child inheritance/propagation,
    custom metadata, serialization, timestamps, TTL, and tag support.
    """

    def __init__(
        self,
        context_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        engine: Optional["ContextEngine"] = None,
        ttl: Optional[Union[int, float]] = None,
        tags: Optional[List[str]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        expires_at: Optional[str] = None,
    ):
        super().__init__(data)
        self.id = context_id or str(uuid.uuid4())
        self.parent_id = parent_id
        self.metadata = dict(metadata) if metadata is not None else {}
        self._active = True
        self._engine = engine
        self.ttl = ttl
        self.tags = list(tags) if tags is not None else []

        # Timestamps
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.created_at = created_at or now_iso
        self.updated_at = updated_at or now_iso

        if expires_at:
            self.expires_at = expires_at
        elif ttl is not None:
            try:
                created_dt = datetime.datetime.fromisoformat(self.created_at)
            except ValueError:
                created_dt = datetime.datetime.now(datetime.timezone.utc)
            self.expires_at = (created_dt + datetime.timedelta(seconds=ttl)).isoformat()
        else:
            self.expires_at = None

    @property
    def active(self) -> bool:
        return self._active

    def deactivate(self) -> None:
        self._active = False

    def is_expired(self) -> bool:
        """
        Check if the context has expired based on expires_at timestamp.
        """
        if not self.expires_at:
            return False
        try:
            now = datetime.datetime.now(datetime.timezone.utc)
            expire_dt = datetime.datetime.fromisoformat(self.expires_at)
            return now >= expire_dt
        except Exception:
            return False

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

    def set(self, key: str, value: Any) -> None:
        """
        Set value by key and update updated_at timestamp.
        """
        super().set(key, value)
        self.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if self._engine:
            self._engine._publish_update_event(self)

    def delete(self, key: str) -> None:
        """
        Delete key and update updated_at timestamp.
        """
        super().delete(key)
        self.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if self._engine:
            self._engine._publish_update_event(self)

    def clear(self) -> None:
        """
        Clear data and update updated_at timestamp.
        """
        super().clear()
        self.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        if self._engine:
            self._engine._publish_update_event(self)

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize context to a dictionary.
        """
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "metadata": self.metadata,
            "data": self.to_dict(),
            "active": self._active,
            "ttl": self.ttl,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def deserialize(
        cls, payload: Dict[str, Any], engine: Optional["ContextEngine"] = None
    ) -> "RuntimeContext":
        """
        Deserialize dictionary back to a RuntimeContext instance.
        """
        ctx = cls(
            context_id=payload.get("id"),
            parent_id=payload.get("parent_id"),
            data=payload.get("data"),
            metadata=payload.get("metadata"),
            engine=engine,
            ttl=payload.get("ttl"),
            tags=payload.get("tags"),
            created_at=payload.get("created_at"),
            updated_at=payload.get("updated_at"),
            expires_at=payload.get("expires_at"),
        )
        ctx._active = payload.get("active", True)
        return ctx


class ContextEngine:
    """
    Centralized, thread-safe Context Engine responsible for managing the lifecycle,
    lookup, propagation, isolation, expiration, and serialization of runtime contexts across the ecosystem.
    """

    def __init__(self, event_bus: Optional[Any] = None):
        self._lock = threading.RLock()
        self._contexts: Dict[str, RuntimeContext] = {}
        self.event_bus = event_bus

    def create_context(
        self,
        data: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[Union[int, float]] = None,
        tags: Optional[List[str]] = None,
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
                engine=self,
                ttl=ttl,
                tags=tags,
            )
            self._contexts[ctx.id] = ctx
            self._publish_event("context_created", {
                "context_id": ctx.id,
                "parent_id": ctx.parent_id,
                "metadata": ctx.metadata,
                "tags": ctx.tags,
                "ttl": ctx.ttl,
            })
            return ctx

    def get_context(self, context_id: str) -> Optional[RuntimeContext]:
        """
        Retrieve context by ID thread-safely.
        """
        with self._lock:
            ctx = self._contexts.get(context_id)
            if ctx:
                if ctx.is_expired():
                    self._handle_expiration(ctx)
                    return None
                return ctx
            return None

    def has_context(self, context_id: str) -> bool:
        """
        Check if context exists thread-safely.
        """
        with self._lock:
            ctx = self._contexts.get(context_id)
            if ctx:
                if ctx.is_expired():
                    self._handle_expiration(ctx)
                    return False
                return True
            return False

    def delete_context(self, context_id: str) -> None:
        """
        Delete and deactivate a context by ID thread-safely.
        """
        with self._lock:
            if context_id in self._contexts:
                ctx = self._contexts[context_id]
                ctx.deactivate()
                del self._contexts[context_id]
                self._publish_event("context_deleted", {"context_id": context_id})

    def list_contexts(self, active_only: bool = True, tags: Optional[List[str]] = None) -> List[str]:
        """
        List all registered context IDs thread-safely.
        """
        with self._lock:
            self.prune_expired_contexts()
            results = []
            for cid, ctx in self._contexts.items():
                if active_only and not ctx.active:
                    continue
                if tags:
                    if not all(tag in ctx.tags for tag in tags):
                        continue
                results.append(cid)
            return results

    def clear(self) -> None:
        """
        Clear all managed contexts.
        """
        with self._lock:
            for ctx in self._contexts.values():
                ctx.deactivate()
            self._contexts.clear()

    def prune_expired_contexts(self) -> None:
        """
        Prune and handle expiration of any expired contexts thread-safely.
        """
        with self._lock:
            expired = [ctx for ctx in self._contexts.values() if ctx.is_expired()]
            for ctx in expired:
                self._handle_expiration(ctx)

    def _handle_expiration(self, ctx: RuntimeContext) -> None:
        """
        Handle deactivation and cleanup of an expired context.
        """
        with self._lock:
            if ctx.id in self._contexts:
                ctx.deactivate()
                del self._contexts[ctx.id]
                self._publish_event("context_expired", {"context_id": ctx.id})

    def update_context_data(self, context_id: str, data: Dict[str, Any]) -> Optional[RuntimeContext]:
        """
        Update context data dictionary by merging new values thread-safely.
        """
        with self._lock:
            ctx = self.get_context(context_id)
            if ctx:
                for k, v in data.items():
                    ctx._data[k] = v
                ctx.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._publish_update_event(ctx)
                return ctx
            return None

    def update_context_metadata(self, context_id: str, metadata: Dict[str, Any]) -> Optional[RuntimeContext]:
        """
        Update context metadata by merging new values thread-safely.
        """
        with self._lock:
            ctx = self.get_context(context_id)
            if ctx:
                ctx.metadata.update(metadata)
                ctx.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._publish_update_event(ctx)
                return ctx
            return None

    def add_tags(self, context_id: str, tags: List[str]) -> Optional[RuntimeContext]:
        """
        Add tags to a context thread-safely.
        """
        with self._lock:
            ctx = self.get_context(context_id)
            if ctx:
                for tag in tags:
                    if tag not in ctx.tags:
                        ctx.tags.append(tag)
                ctx.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._publish_update_event(ctx)
                return ctx
            return None

    def _publish_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        """
        Publish an event on the event bus if available.
        """
        if self.event_bus:
            try:
                self.event_bus.publish(event_name, payload)
            except Exception:
                pass

    def _publish_update_event(self, ctx: RuntimeContext) -> None:
        """
        Publish standard context update event on the event bus.
        """
        self._publish_event("context_updated", {
            "context_id": ctx.id,
            "metadata": ctx.metadata,
            "tags": ctx.tags,
            "updated_at": ctx.updated_at,
        })

    def get_status(self) -> Dict[str, Any]:
        """
        Retrieve context engine status.
        """
        with self._lock:
            self.prune_expired_contexts()
            active_count = sum(1 for ctx in self._contexts.values() if ctx.active)
            return {
                "total_contexts": len(self._contexts),
                "active_contexts": active_count,
                "contexts": {
                    cid: {
                        "parent_id": ctx.parent_id,
                        "metadata": ctx.metadata,
                        "active": ctx.active,
                        "ttl": ctx.ttl,
                        "tags": ctx.tags,
                        "created_at": ctx.created_at,
                        "updated_at": ctx.updated_at,
                        "expires_at": ctx.expires_at,
                    }
                    for cid, ctx in self._contexts.items()
                },
            }

    def save_context_to_storage(
        self, context_id: str, storage: BaseStorage, key_prefix: str = "context:"
    ) -> None:
        """
        Save a single runtime context to storage thread-safely.
        """
        with self._lock:
            ctx = self.get_context(context_id)
            if ctx:
                storage.set(f"{key_prefix}{context_id}", ctx.serialize())

    def load_context_from_storage(
        self, context_id: str, storage: BaseStorage, key_prefix: str = "context:"
    ) -> Optional[RuntimeContext]:
        """
        Load and register a single runtime context from storage thread-safely.
        """
        with self._lock:
            payload = storage.get(f"{key_prefix}{context_id}")
            if payload:
                ctx = RuntimeContext.deserialize(payload, engine=self)
                self._contexts[ctx.id] = ctx
                return ctx
            return None

    def save_all_contexts_to_storage(
        self, storage: BaseStorage, key_prefix: str = "contexts"
    ) -> None:
        """
        Save all managed contexts to storage as a dictionary.
        """
        with self._lock:
            serialized = {
                cid: ctx.serialize() for cid, ctx in self._contexts.items()
            }
            storage.set(key_prefix, serialized)

    def load_all_contexts_from_storage(
        self, storage: BaseStorage, key_prefix: str = "contexts"
    ) -> None:
        """
        Load and merge all contexts from storage thread-safely.
        """
        with self._lock:
            payload = storage.get(key_prefix)
            if payload and isinstance(payload, dict):
                for cid, ctx_payload in payload.items():
                    ctx = RuntimeContext.deserialize(ctx_payload, engine=self)
                    self._contexts[cid] = ctx

    def retrieve_context_memories(self, context_id: str, client: Any) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve memories belonging to the specified context ID.
        """
        with self._lock:
            short_term_entries = client.short_term_memory.filter({"context_id": context_id})
            long_term_entries = client.long_term_memory.filter({"context_id": context_id})
            return {
                "short-term": [entry.to_dict() for entry in short_term_entries],
                "long-term": [entry.to_dict() for entry in long_term_entries],
            }

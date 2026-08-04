import asyncio
import concurrent.futures
import inspect
import logging
import threading
from typing import Any, Dict, List, Optional, Callable

from yasin_core.utils.logger import get_logger
from yasin_core.events.event import Event

# Event Name Constants for backward compatibility
AGENT_REGISTERED = "agent_registered"
AGENT_REMOVED = "agent_removed"
AGENT_STARTED = "agent_started"
AGENT_STOPPED = "agent_stopped"
TASK_STARTED = "task_started"
TASK_COMPLETED = "task_completed"
TASK_FAILED = "task_failed"


class Subscription:
    """Represents a subscriber registration with support for filters and async execution."""
    def __init__(
        self,
        handler: Callable,
        filter_func: Optional[Callable[[Event], bool]] = None,
        async_handle: bool = False
    ):
        self.handler = handler
        self.filter_func = filter_func
        self.async_handle = async_handle


class EventBus:
    """
    Centralized Event Bus architecture for Yasin-Core.
    Supports thread-safe synchronous and asynchronous event publication and subscription,
    filtering, metadata tracing, history logging, and robust error isolation.
    """

    def __init__(self, max_history_size: int = 100):
        """
        Initialize the event bus with bounded event history and asynchronous callback execution.
        
        Parameters:
        	max_history_size (int): Maximum number of published events to retain in history.
        """
        self.logger = get_logger("EVENT_BUS")
        self._lock = threading.RLock()

        # Internal subscription records
        self._subscriptions: Dict[str, List[Subscription]] = {}

        # Backward-compatible simple subscription dictionary: event_name -> list of callable
        self.listeners: Dict[str, List[Callable]] = {}

        # Event history
        self._history: List[Event] = []
        self._max_history_size = max_history_size

        # Thread pool executor for executing synchronous callbacks asynchronously
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=10,
            thread_name_prefix="YasinEventBusAsync"
        )
        self._is_shutdown = False

    def _get_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        """Return an active executor for asynchronous event handlers."""
        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Cannot get executor: EventBus is shut down.")
            if self._executor is None:
                self._executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=10,
                    thread_name_prefix="YasinEventBusAsync"
                )
            return self._executor

    def subscribe(
        self,
        event: str,
        callback: Callable,
        filter_func: Optional[Callable[[Event], bool]] = None,
        async_handle: bool = False
    ) -> None:
        """
        Register a callback for a specific event or all events using the "*" wildcard.
        
        Parameters:
            event (str): Event name, or "*" to receive all events.
            callback (Callable): Callback invoked when a matching event is published.
            filter_func (Optional[Callable[[Event], bool]]): Optional predicate that determines whether the callback handles an event.
            async_handle (bool): Whether to execute the callback on a background thread.
        """
        with self._lock:
            if event not in self._subscriptions:
                self._subscriptions[event] = []

            # Avoid duplicate subscriptions for the same handler on the same event
            for sub in self._subscriptions[event]:
                if sub.handler == callback:
                    return

            sub = Subscription(
                handler=callback,
                filter_func=filter_func,
                async_handle=async_handle
            )
            self._subscriptions[event].append(sub)

            # Sync with the backward-compatible dict
            if event not in self.listeners:
                self.listeners[event] = []
            self.listeners[event].append(callback)

            self.logger.info(f"Subscribed callback to event '{event}'")

    def unsubscribe(self, event: str, callback: Callable) -> None:
        """
        Unsubscribe a callback from a specific event.
        """
        with self._lock:
            if event in self._subscriptions:
                self._subscriptions[event] = [
                    sub for sub in self._subscriptions[event] if sub.handler != callback
                ]
                if not self._subscriptions[event]:
                    del self._subscriptions[event]

            # Sync with backward-compatible dict
            if event in self.listeners:
                self.listeners[event] = [
                    cb for cb in self.listeners[event] if cb != callback
                ]
                if not self.listeners[event]:
                    del self.listeners[event]

            self.logger.info(f"Unsubscribed callback from event '{event}'")

    def clear(self) -> None:
        """
        Clear all event subscriptions.
        """
        with self._lock:
            self._subscriptions.clear()
            self.listeners.clear()
            self.logger.info("Cleared all subscriptions")

    def reset(self) -> None:
        """
        Reset the EventBus shutdown state, allowing it to be restarted.
        """
        with self._lock:
            self._is_shutdown = False
            self._executor = None
            self.logger.info("EventBus executor reset/enabled")

    def shutdown(self) -> None:
        """
        Shut down the event bus's asynchronous executor without waiting for queued tasks to finish.
        """
        with self._lock:
            if self._executor:
                self._executor.shutdown(wait=False)
                self._is_shutdown = True
                self._executor = None
                self.logger.info("EventBus executor shut down")

    def publish(self, event: Any, data: Any = None, **metadata) -> None:
        """
        Publish an event to matching subscribers.
        
        The event may be provided as an `Event` instance or as an event name with
        payload and metadata. Subscribers are invoked synchronously or dispatched
        asynchronously according to their configuration.
        """
        # Normalize to Event object
        if isinstance(event, Event):
            evt_obj = event
        else:
            evt_obj = Event(name=str(event), payload=data, metadata=metadata)

        # Append to history
        with self._lock:
            self._history.append(evt_obj)
            if len(self._history) > self._max_history_size:
                self._history.pop(0)

        # Retrieve and execute all matching handlers (specific and wildcard)
        with self._lock:
            handlers_to_call = list(self._subscriptions.get(evt_obj.name, []))
            wildcards = list(self._subscriptions.get("*", []))

        all_subs = handlers_to_call + wildcards

        for sub in all_subs:
            # Evaluate subscription filter if present
            if sub.filter_func:
                try:
                    if not sub.filter_func(evt_obj):
                        continue
                except Exception as exc:
                    self.logger.error(
                        f"Error evaluating filter for event '{evt_obj.name}': {exc}",
                        exc_info=True
                    )
                    continue

            # Determine execution path
            is_coro = inspect.iscoroutinefunction(sub.handler)
            if is_coro:
                self._execute_async_handler(sub.handler, evt_obj)
            elif sub.async_handle:
                # Sync handler, but requested async execution: dispatch to thread pool
                try:
                    self._get_executor().submit(self._safe_execute_handler, sub.handler, evt_obj)
                except RuntimeError as e:
                    self.logger.error(f"Failed to submit handler to executor after shutdown: {e}")
            else:
                # Synchronous execution
                self._safe_execute_handler(sub.handler, evt_obj)

    async def async_publish(self, event: Any, data: Any = None, **metadata) -> None:
        """
        Publish an event to all matching subscribers.
        
        Parameters:
            event (Any): An Event instance or the event name to publish.
            data (Any): Payload for the event when `event` is an event name.
            **metadata: Additional metadata to attach to the event.
        """
        if isinstance(event, Event):
            evt_obj = event
        else:
            evt_obj = Event(name=str(event), payload=data, metadata=metadata)

        # Append to history
        with self._lock:
            self._history.append(evt_obj)
            if len(self._history) > self._max_history_size:
                self._history.pop(0)

        # Retrieve and execute handlers
        with self._lock:
            handlers_to_call = list(self._subscriptions.get(evt_obj.name, []))
            wildcards = list(self._subscriptions.get("*", []))

        all_subs = handlers_to_call + wildcards

        for sub in all_subs:
            if sub.filter_func:
                try:
                    if not sub.filter_func(evt_obj):
                        continue
                except Exception as exc:
                    self.logger.error(
                        f"Error evaluating filter for event '{evt_obj.name}': {exc}",
                        exc_info=True
                    )
                    continue

            is_coro = inspect.iscoroutinefunction(sub.handler)
            if is_coro:
                # Spawn concurrent async task
                asyncio.create_task(self._safe_execute_async_handler(sub.handler, evt_obj))
            elif sub.async_handle:
                try:
                    self._get_executor().submit(self._safe_execute_handler, sub.handler, evt_obj)
                except RuntimeError as e:
                    self.logger.error(f"Failed to submit handler to executor after shutdown: {e}")
            else:
                self._safe_execute_handler(sub.handler, evt_obj)

    def _execute_async_handler(self, handler: Callable, event: Event) -> None:
        """
        Schedule an asynchronous event handler from synchronous code.
        
        Parameters:
            handler (Callable): The asynchronous callback to execute.
            event (Event): The event passed to the callback.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._safe_execute_async_handler(handler, event), loop)
        else:
            # No running loop in this thread, execute in thread-pool with its own loop
            def run_in_loop():
                """Execute the asynchronous event handler in a new event loop."""
                asyncio.run(self._safe_execute_async_handler(handler, event))
            try:
                self._get_executor().submit(run_in_loop)
            except RuntimeError as e:
                self.logger.error(f"Failed to submit async handler after shutdown: {e}")

    def _safe_execute_handler(self, handler: Callable, event: Event) -> None:
        """
        Robustly execute a sync handler and isolate any errors.
        """
        try:
            handler(event)
        except Exception as exc:
            self.logger.error(
                f"Error in handler execution for event '{event.name}': {exc}",
                exc_info=True
            )

    async def _safe_execute_async_handler(self, handler: Callable, event: Event) -> None:
        """
        Robustly await an async handler and isolate any errors.
        """
        try:
            await handler(event)
        except Exception as exc:
            self.logger.error(
                f"Error in async handler execution for event '{event.name}': {exc}",
                exc_info=True
            )

    def get_history(self, limit: Optional[int] = None, event_name: Optional[str] = None) -> List[Event]:
        """
        Retrieve history of published events with optional filtering and limit.
        """
        with self._lock:
            events = self._history
            if event_name:
                events = [e for e in events if e.name == event_name]
            if limit is not None:
                events = events[-limit:]
            return list(events)

    def clear_history(self) -> None:
        """
        Clear the published events history.
        """
        with self._lock:
            self._history.clear()
            self.logger.info("Cleared event history")

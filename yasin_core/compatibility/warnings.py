import functools
import warnings
import logging
from typing import Any, Callable, Type, Optional, Union

from yasin_core.utils.logger import get_logger


class DeprecationManager:
    """
    Manages deprecation warnings and logging across the Yasin-Core ecosystem.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or get_logger("DEPRECATION-MANAGER")
        self._warnings_count = 0

    def warn(
        self,
        message: str,
        since: Optional[str] = None,
        instead: Optional[str] = None,
        stacklevel: int = 2
    ) -> None:
        """
        Emit and log a deprecation warning.
        """
        self._warnings_count += 1
        full_message = message
        if since:
            full_message += f" (deprecated since version {since})"
        if instead:
            full_message += f". Use '{instead}' instead"

        # Emit standard library warning
        warnings.warn(full_message, DeprecationWarning, stacklevel=stacklevel)

        # Log via structured logger/fallback logger
        self.logger.warning(f"DEPRECATED: {full_message}")

    @property
    def warnings_count(self) -> int:
        return self._warnings_count


# Centralized global manager instance
_manager = DeprecationManager()


def deprecated(
    since: Optional[str] = None,
    instead: Optional[str] = None,
    message: Optional[str] = None
) -> Callable:
    """
    Decorator to mark functions, methods, or classes as deprecated.

    Usage:
        @deprecated(since="1.6.0", instead="new_method")
        def old_method(self):
            pass
    """
    def decorator(func_or_class: Union[Callable, Type]) -> Any:
        if isinstance(func_or_class, type):
            # Class deprecation - wrap the __init__ or construct warning
            orig_init = func_or_class.__init__

            @functools.wraps(orig_init)
            def wrapped_init(self, *args, **kwargs):
                msg = message or f"Class '{func_or_class.__name__}' is deprecated"
                _manager.warn(msg, since=since, instead=instead, stacklevel=3)
                orig_init(self, *args, **kwargs)

            func_or_class.__init__ = wrapped_init
            return func_or_class
        else:
            # Function/method deprecation
            @functools.wraps(func_or_class)
            def wrapper(*args, **kwargs):
                msg = message or f"Function/method '{func_or_class.__name__}' is deprecated"
                _manager.warn(msg, since=since, instead=instead, stacklevel=3)
                return func_or_class(*args, **kwargs)
            return wrapper

    return decorator

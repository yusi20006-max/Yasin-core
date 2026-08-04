import warnings
import functools
from typing import Callable, Any, Dict

class SDKVersionChecker:
    """Verifies version compatibility between SDK client and core components."""
    @staticmethod
    def check_compatibility(sdk_version: str, core_version: str) -> bool:
        """Simple major/minor match check."""
        sdk_parts = sdk_version.split(".")
        core_parts = core_version.split(".")
        if len(sdk_parts) < 2 or len(core_parts) < 2:
            return False
        # Major version must match
        return sdk_parts[0] == core_parts[0]


from typing import Optional, Union, Type

def deprecated(
    since: Optional[str] = None,
    instead: Optional[str] = None,
    message: Optional[str] = None,
    replaced_by: str = ""
):
    """Unified decorator supporting both compatibility and SDK v2 deprecation warning flows."""
    from yasin_core.compatibility.warnings import _manager

    # If replaced_by is provided, map it to instead
    if replaced_by and not instead:
        instead = replaced_by

    def decorator(func_or_class: Union[Callable[..., Any], Type[Any]]) -> Any:
        if isinstance(func_or_class, type):
            orig_init = func_or_class.__init__

            @functools.wraps(orig_init)
            def wrapped_init(self, *args, **kwargs):
                if replaced_by:
                    msg = message or f"{func_or_class.__name__} is deprecated and will be removed in SDK v3."
                else:
                    msg = message or f"Class '{func_or_class.__name__}' is deprecated"
                _manager.warn(msg, since=since, instead=instead, stacklevel=3)
                orig_init(self, *args, **kwargs)

            func_or_class.__init__ = wrapped_init
            return func_or_class
        else:
            @functools.wraps(func_or_class)
            def wrapper(*args, **kwargs):
                if replaced_by:
                    msg = message or f"{func_or_class.__name__} is deprecated and will be removed in SDK v3."
                else:
                    msg = message or f"Function/method '{func_or_class.__name__}' is deprecated"
                _manager.warn(msg, since=since, instead=instead, stacklevel=3)
                return func_or_class(*args, **kwargs)
            return wrapper

    return decorator


class SDKMigrationHelper:
    """Helper class to assist ecosystem users in migrating from V1 payload/API to V2."""
    @staticmethod
    def migrate_task_payload(v1_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a V1 task request payload to V2 format."""
        v2_payload = dict(v1_payload)
        if "meta" not in v2_payload:
            v2_payload["meta"] = {"version": "v2", "migrated": True}
        else:
            v2_payload["meta"] = dict(v2_payload["meta"])
            v2_payload["meta"]["version"] = "v2"
            v2_payload["meta"]["migrated"] = True
        return v2_payload

    @staticmethod
    def migrate_memory_payload(v1_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a V1 memory save payload to V2."""
        v2_payload = dict(v1_payload)
        metadata = v2_payload.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata = dict(metadata)
            metadata["v2_saved"] = True
            metadata["migrated"] = True
            v2_payload["metadata"] = metadata
        return v2_payload

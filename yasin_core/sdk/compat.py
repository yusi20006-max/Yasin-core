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


def deprecated(
    since: Any = None,
    instead: Any = None,
    message: Any = None,
    replaced_by: str = "",
):
    """Unified decorator supporting both SDK v2 stabilization and global compatibility layer."""
    if since is not None or instead is not None or message is not None:
        from yasin_core.compatibility.warnings import deprecated as core_deprecated
        return core_deprecated(since=since, instead=instead, message=message)

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            msg = f"{func.__name__} is deprecated and will be removed in SDK v3."
            if replaced_by:
                msg += f" Please use {replaced_by} instead."
            warnings.warn(msg, category=DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
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

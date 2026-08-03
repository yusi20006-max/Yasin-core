import os
import yaml
import copy
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Type, Callable

from yasin_core.runtime.interfaces import BaseService


class ConfigurationValidationError(ValueError):
    """Exception raised when configuration schema validation fails."""
    pass


class ConfigurationManager(BaseService):
    """
    Centralized, thread-safe configuration manager responsible for loading,
    validating, and providing runtime configuration across the Yasin ecosystem.
    Integrates with Runtime Service Manager and Dependency Injection.
    """

    def __init__(self, path: Optional[Union[str, Path]] = None, defaults_path: Optional[Union[str, Path]] = None):
        super().__init__()
        self._lock = threading.RLock()

        # Determine defaults and active config paths
        if path is None:
            # Check for standard paths or default to package default.yaml
            path = Path(__file__).parent / "default.yaml"

        self._config_path = Path(path)
        self._default_path = Path(defaults_path) if defaults_path else Path(__file__).parent / "default.yaml"

        # Raw and merged configuration structures
        self._defaults: Dict[str, Any] = {}
        self._file_data: Dict[str, Any] = {}
        self._env_data: Dict[str, Any] = {}
        self._overrides: Dict[str, Any] = {}
        self._merged_data: Dict[str, Any] = {}

        # Validation schema and security definitions
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._sensitive_keys: set = set()

        # Backward-compatibility attributes
        self.path = self._config_path
        self.data: Dict[str, Any] = {}

        # Load and validate on initialization
        self.reload()

    # --- Schema and Validation registration ---

    def register_schema(
        self,
        key: str,
        data_type: Type,
        required: bool = False,
        default: Any = None,
        description: str = "",
        validator: Optional[Callable[[Any], bool]] = None,
        sensitive: bool = False
    ) -> None:
        """
        Register a validation schema rule for a configuration key (e.g. 'app.port').
        """
        with self._lock:
            self._schemas[key] = {
                "type": data_type,
                "required": required,
                "default": default,
                "description": description,
                "validator": validator,
                "sensitive": sensitive
            }
            if sensitive:
                self._sensitive_keys.add(key)

            # If the schema specifies a default and the key is not in defaults dict, populate it
            if default is not None:
                parts = key.split(".")
                self._set_deep(self._defaults, parts, default)

            # Re-merge to apply defaults and check schema rules
            self._merged_data = self._merge_configs()
            self.data = self._merged_data
            self.validate()

    def register_plugin_config(
        self,
        plugin_name: str,
        defaults: Dict[str, Any],
        schema: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """
        Dynamically register default configurations and schema validations for a plugin.
        All configurations are namespaced under 'plugins.<plugin_name>'.
        """
        prefix = f"plugins.{plugin_name}"
        with self._lock:
            # Load and flatten defaults to register them correctly
            flat_defaults = self._flatten_dict(defaults)
            for k, v in flat_defaults.items():
                self._set_deep(self._defaults, f"{prefix}.{k}".split("."), v)

            # Load schemas
            if schema:
                for k, s_def in schema.items():
                    schema_key = f"{prefix}.{k}"
                    self.register_schema(
                        key=schema_key,
                        data_type=s_def.get("type", Any),
                        required=s_def.get("required", False),
                        default=s_def.get("default"),
                        description=s_def.get("description", ""),
                        validator=s_def.get("validator"),
                        sensitive=s_def.get("sensitive", False)
                    )
            else:
                # Re-merge without schema definitions
                self._merged_data = self._merge_configs()
                self.data = self._merged_data

    # --- Loading and Lifecycle ---

    def load(self) -> Dict[str, Any]:
        """
        Load (and reload) configurations and return the merged configuration dictionary.
        This provides perfect backward compatibility with existing Settings.load() behavior.
        """
        self.reload()
        return self._merged_data

    def reload(self) -> None:
        """
        Reload all configuration layers (Defaults, File, Environment, Programmatic Overrides)
        and run schema validation.
        """
        with self._lock:
            # 1. Load default.yaml
            if self._default_path.exists():
                self._defaults = self._load_yaml(self._default_path)
            else:
                self._defaults = {}

            # 2. Load active file config
            if self._config_path.exists() and self._config_path != self._default_path:
                self._file_data = self._load_yaml(self._config_path)
            else:
                self._file_data = {}

            # 3. Load Environment Overrides
            self._env_data = self._load_env_overrides()

            # 4. Merge configuration hierarchy
            self._merged_data = self._merge_configs()
            self.data = self._merged_data

            # 5. Perform validation
            self.validate()

    def validate(self) -> None:
        """
        Validate the current merged configuration against the registered schemas.
        Raises ConfigurationValidationError if a rule is violated.
        """
        with self._lock:
            for key, rule in self._schemas.items():
                val = self.get(key)

                # Check required
                if rule.get("required") and val is None:
                    raise ConfigurationValidationError(
                        f"Configuration validation failed: Required key '{key}' is missing."
                    )

                if val is not None:
                    # Check type
                    expected_type = rule.get("type")
                    if expected_type is not Any and not isinstance(val, expected_type):
                        raise ConfigurationValidationError(
                            f"Configuration validation failed: Key '{key}' must be of type "
                            f"{expected_type.__name__}, got {type(val).__name__}."
                        )

                    # Check custom validator
                    validator = rule.get("validator")
                    if validator and not validator(val):
                        raise ConfigurationValidationError(
                            f"Configuration validation failed: Custom validation failed for key '{key}' with value '{val}'."
                        )

    # --- Dynamic Modifiers and Programmatic Overrides ---

    def set(self, key: str, value: Any) -> None:
        """
        Dynamically override/set a configuration value programmatically at runtime.
        """
        with self._lock:
            parts = key.split(".")
            self._set_deep(self._overrides, parts, value)
            self._merged_data = self._merge_configs()
            self.data = self._merged_data
            self.validate()

    def has(self, key: str) -> bool:
        """
        Check if a given configuration key exists.
        """
        with self._lock:
            return self.get(key) is not None

    # --- Retrieve Methods (Helper APIs) ---

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a configuration value by dotted string key path.
        """
        with self._lock:
            keys = key.split(".")
            value = self._merged_data
            for item in keys:
                if isinstance(value, dict):
                    value = value.get(item, default)
                else:
                    return default
            return value if value is not None else default

    def get_string(self, key: str, default: Optional[str] = None) -> Optional[str]:
        val = self.get(key, default)
        return str(val) if val is not None else None

    def get_int(self, key: str, default: Optional[int] = None) -> Optional[int]:
        val = self.get(key, default)
        return int(val) if val is not None else None

    def get_float(self, key: str, default: Optional[float] = None) -> Optional[float]:
        val = self.get(key, default)
        return float(val) if val is not None else None

    def get_bool(self, key: str, default: Optional[bool] = None) -> Optional[bool]:
        val = self.get(key, default)
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val) if val is not None else None

    def get_list(self, key: str, default: Optional[List[Any]] = None) -> Optional[List[Any]]:
        val = self.get(key, default)
        if val is None:
            return None
        if isinstance(val, list):
            return val
        raise TypeError(f"Configuration key '{key}' is not of type list, got {type(val).__name__}")

    def get_dict(self, key: str, default: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        val = self.get(key, default)
        if val is None:
            return None
        if isinstance(val, dict):
            return val
        raise TypeError(f"Configuration key '{key}' is not of type dict, got {type(val).__name__}")

    def get_secure(self, key: str, default: Any = None) -> Any:
        """
        Retrieve sensitive value securely.
        """
        return self.get(key, default)

    # --- Internal Utilities ---

    def _load_yaml(self, path: Path) -> Dict[str, Any]:
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_env_overrides(self) -> Dict[str, Any]:
        env_data = {}
        for env_key, env_val in os.environ.items():
            if env_key.startswith("YASIN_"):
                # Strip prefix
                key_part = env_key[6:]
                # Parse value
                val = self._parse_env_value(env_val)
                self._set_nested_value(env_data, key_part, val)
        return env_data

    def _set_nested_value(self, target_dict: dict, env_key: str, val: Any) -> None:
        env_key_lower = env_key.lower()

        # 1. Split by '__' (explicit nesting)
        if "__" in env_key:
            parts = env_key_lower.split("__")
            self._set_deep(target_dict, parts, val)
            return

        # 2. Match with existing dotted/flattened keys from defaults/schema
        # We try to match lowercased environment variable key structure
        flat_keys = set(self._flatten_dict(self._defaults).keys()) | set(self._schemas.keys())

        # Check if replacing '.' with '_' in any known key matches env_key_lower
        found_key = None
        for k in flat_keys:
            if k.replace(".", "_") == env_key_lower:
                found_key = k
                break

        if found_key:
            parts = found_key.split(".")
            self._set_deep(target_dict, parts, val)
            return

        # Try mapping all underscores directly to dots
        match_key = env_key_lower.replace("_", ".")
        if match_key in flat_keys:
            parts = match_key.split(".")
            self._set_deep(target_dict, parts, val)
            return

        # 3. Fallback to '_' split
        parts = env_key_lower.split("_")
        self._set_deep(target_dict, parts, val)

    def _set_deep(self, d: dict, parts: List[str], val: Any) -> None:
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = val

    def _parse_env_value(self, val: str) -> Any:
        val_lower = val.strip().lower()
        if val_lower == "true":
            return True
        if val_lower == "false":
            return False
        if val_lower in ("none", "null"):
            return None
        # Try numeric parsing
        try:
            if "." in val:
                return float(val)
            return int(val)
        except ValueError:
            pass
        # Try JSON parsing for lists and objects
        if (val.startswith("[") and val.endswith("]")) or (val.startswith("{") and val.endswith("}")):
            try:
                import json
                return json.loads(val)
            except Exception:
                pass
        return val

    def _flatten_dict(self, d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        flat = {}
        for k, v in d.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict):
                flat.update(self._flatten_dict(v, f"{key}."))
            else:
                flat[key] = v
        return flat

    def _merge_configs(self) -> Dict[str, Any]:
        # Merge hierarchy: defaults <- file_data <- env_data <- overrides
        merged = copy.deepcopy(self._defaults)
        self._deep_update(merged, self._file_data)
        self._deep_update(merged, self._env_data)
        self._deep_update(merged, self._overrides)
        return merged

    def _deep_update(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        for k, v in update.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._deep_update(base[k], v)
            else:
                base[k] = copy.deepcopy(v)

    def _mask_sensitive(self, d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        masked = {}
        for k, v in d.items():
            key = f"{prefix}{k}"
            if key in self._sensitive_keys:
                masked[k] = "******"
            elif isinstance(v, dict):
                masked[k] = self._mask_sensitive(v, f"{key}.")
            else:
                masked[k] = v
        return masked

    # --- Runtime Service Manager Compatibility ---

    def initialize(self) -> None:
        """Initialize the service."""
        # Force a reload on initialization
        self.reload()

    def shutdown(self) -> None:
        """Shutdown the service."""
        pass

    def reload_config(self) -> None:
        """Alias for reloading configuration via service manager."""
        self.reload()

    def health(self) -> Dict[str, Any]:
        """Check the health status of the service (unhealthy if validation fails)."""
        try:
            self.validate()
            return {"status": "healthy", "healthy": True}
        except Exception as e:
            return {"status": "unhealthy", "healthy": False, "error": str(e)}

    def status(self) -> Dict[str, Any]:
        """Return the execution and configuration status (masking sensitive values)."""
        masked_config = self._mask_sensitive(self._merged_data)
        return {
            "state": "active",
            "config_path": str(self._config_path),
            "schema_count": len(self._schemas),
            "configuration": masked_config
        }


# Legacy Settings Alias for Backward Compatibility
Settings = ConfigurationManager

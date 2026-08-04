from typing import Any, Dict, Callable, Optional
from yasin_core.compatibility.warnings import _manager


class LegacyAPIAdapter:
    """
    Adapter that wraps a modern class or object to provide legacy method and
    attribute aliases, or translates signatures of deprecated calls.
    """

    def __init__(
        self,
        target_obj: Any,
        alias_mapping: Optional[Dict[str, str]] = None,
        custom_translators: Optional[Dict[str, Callable]] = None,
        since_version: str = "1.0.0"
    ):
        """
        Parameters:
            target_obj: The modern object we are wrapping.
            alias_mapping: Dict of {'legacy_name': 'modern_name'}.
            custom_translators: Dict of {'legacy_name': translator_func(target_obj, *args, **kwargs)}.
            since_version: Version since when the legacy names were deprecated.
        """
        self._target_obj = target_obj
        self._alias_mapping = alias_mapping or {}
        self._custom_translators = custom_translators or {}
        self._since_version = since_version

    def __getattr__(self, name: str) -> Any:
        # Check custom translators first
        if name in self._custom_translators:
            translator_func = self._custom_translators[name]
            _manager.warn(
                f"Legacy method '{name}' is called via adapter",
                since=self._since_version,
                instead=translator_func.__name__
            )
            # Return a callable that executes the translator
            return lambda *args, **kwargs: translator_func(self._target_obj, *args, **kwargs)

        # Check simple alias mapping
        if name in self._alias_mapping:
            modern_name = self._alias_mapping[name]
            _manager.warn(
                f"Legacy attribute/method '{name}' is accessed",
                since=self._since_version,
                instead=modern_name
            )
            return getattr(self._target_obj, modern_name)

        # Fallback to direct target attribute
        return getattr(self._target_obj, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_target_obj", "_alias_mapping", "_custom_translators", "_since_version"):
            super().__setattr__(name, value)
            return

        if name in self._alias_mapping:
            modern_name = self._alias_mapping[name]
            _manager.warn(
                f"Setting legacy attribute '{name}'",
                since=self._since_version,
                instead=modern_name
            )
            setattr(self._target_obj, modern_name, value)
        else:
            setattr(self._target_obj, name, value)

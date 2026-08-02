class PluginError(Exception):
    """Base exception for all plugin-related errors."""
    pass


class PluginDependencyError(PluginError):
    """Exception raised when plugin dependencies are missing, circular, or invalid."""
    pass


class PluginVersionError(PluginError):
    """Exception raised when a plugin is not compatible with the core version."""
    pass


class PluginNotFoundError(PluginError):
    """Exception raised when a requested plugin is not registered."""
    pass


class PluginStateError(PluginError):
    """Exception raised when a plugin operation is performed in an invalid state."""
    pass

class StorageError(Exception):
    """Base exception for all storage errors."""
    pass


class StorageConnectionError(StorageError):
    """Raised when the storage connection fails or the backend is unavailable."""
    pass


class StorageNotFoundError(StorageError):
    """Raised when a requested resource or key is not found in storage."""
    pass


class StorageValidationError(StorageError):
    """Raised when storage data validation fails."""
    pass

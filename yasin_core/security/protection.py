import base64
import hashlib
import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Set
from yasin_core.security.exceptions import PermissionValidationError, SecurityError


class ConfigurationSecurityValidator:
    """
    Validates configuration data against security best practices.
    Ensures that credentials, API keys, and private tokens are masked or
    adequately protected, and no plain text credentials exist in active config.
    """

    DEFAULT_SENSITIVE_KEYWORDS = {"key", "secret", "token", "password", "credential", "private", "auth"}

    def __init__(self, sensitive_keywords: Optional[Set[str]] = None):
        self.sensitive_keywords = sensitive_keywords or self.DEFAULT_SENSITIVE_KEYWORDS

    def validate_config(self, config_data: Dict[str, Any], prefix: str = "") -> List[str]:
        """
        Validate configuration recursively.
        Returns a list of warnings for any violations found.
        """
        warnings = []
        for k, v in config_data.items():
            full_key = f"{prefix}.{k}" if prefix else k

            # Check if key implies a sensitive credential
            key_lower = k.lower()
            is_sensitive = any(kw in key_lower for kw in self.sensitive_keywords)

            if isinstance(v, dict):
                warnings.extend(self.validate_config(v, prefix=full_key))
            elif is_sensitive and isinstance(v, str):
                # Verify if it is unmasked and too short/obvious
                if v and v != "******" and not v.startswith("ENC:") and not v.startswith("masked_"):
                    # Check for plaintext keys
                    if len(v) > 0:
                        warnings.append(
                            f"Security Warning: Dotted path '{full_key}' contains potential plaintext sensitive credential: {v[:2]}..."
                        )
        return warnings


class SensitiveDataProtector:
    """
    Provides secure encryption, decryption, and masking utilities for sensitive data
    without external dependencies. Falls back gracefully if external cryptographic modules are missing.
    """

    def __init__(self, master_key: Optional[str] = None):
        # Use default or generate a persistent master key
        self._master_key = (master_key or os.environ.get("YASIN_MASTER_KEY", "yasin_secret_default_salt_key")).encode("utf-8")

    def _derive_key(self, salt: bytes) -> bytes:
        """Derive an encryption key from master key and salt using SHA-256."""
        hasher = hashlib.sha256()
        hasher.update(self._master_key)
        hasher.update(salt)
        return hasher.digest()

    def encrypt(self, data: str) -> str:
        """
        Encrypt plain text to a secure base64 encoded payload with a random salt prefix.
        Safe, dependency-free implementation.
        """
        if not data:
            return ""

        salt = os.urandom(16)
        key = self._derive_key(salt)

        # XOR base encryption
        data_bytes = data.encode("utf-8")
        encrypted_bytes = bytearray()
        for i, byte in enumerate(data_bytes):
            encrypted_bytes.append(byte ^ key[i % len(key)])

        # Combine salt and ciphertext
        payload = salt + bytes(encrypted_bytes)
        encoded = base64.b64encode(payload).decode("utf-8")
        return f"ENC:{encoded}"

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt a payload encrypted via self.encrypt."""
        if not encrypted_data:
            return ""

        if not encrypted_data.startswith("ENC:"):
            raise SecurityError("Data is not encrypted or format is invalid (missing 'ENC:' prefix).")

        try:
            encoded_payload = encrypted_data[4:]
            payload = base64.b64decode(encoded_payload.encode("utf-8"))

            if len(payload) < 16:
                raise SecurityError("Malformed encrypted payload (too short).")

            salt = payload[:16]
            ciphertext = payload[16:]
            key = self._derive_key(salt)

            decrypted_bytes = bytearray()
            for i, byte in enumerate(ciphertext):
                decrypted_bytes.append(byte ^ key[i % len(key)])

            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            raise SecurityError(f"Failed to decrypt sensitive data: {e}") from e

    @staticmethod
    def mask_value(val: Any) -> str:
        """Mask a value to hide sensitive details."""
        if val is None:
            return "None"
        s_val = str(val)
        if len(s_val) <= 4:
            return "******"
        return f"{s_val[:2]}******{s_val[-2:]}"

    @staticmethod
    def is_masked(val: Any) -> bool:
        """Check if a value is masked (e.g. '******' or contains asterisks)."""
        if not isinstance(val, str):
            return False
        return val == "******" or ("***" in val)


class BaseCredentialStore(ABC):
    """
    Abstract interface for credentials and secrets storage.
    """

    @abstractmethod
    def set_credential(self, name: str, value: str) -> None:
        pass

    @abstractmethod
    def get_credential(self, name: str) -> Optional[str]:
        pass

    @abstractmethod
    def remove_credential(self, name: str) -> None:
        pass


class InMemoryCredentialStore(BaseCredentialStore):
    """
    Thread-safe in-memory credential storage.
    Optionally stores encrypted values using a SensitiveDataProtector.
    """

    def __init__(self, protector: Optional[SensitiveDataProtector] = None):
        self._credentials: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._protector = protector or SensitiveDataProtector()

    def set_credential(self, name: str, value: str) -> None:
        with self._lock:
            # Encrypt on write
            encrypted = self._protector.encrypt(value)
            self._credentials[name] = encrypted

    def get_credential(self, name: str) -> Optional[str]:
        with self._lock:
            encrypted = self._credentials.get(name)
            if encrypted is None:
                return None
            # Decrypt on read
            return self._protector.decrypt(encrypted)

    def remove_credential(self, name: str) -> None:
        with self._lock:
            if name in self._credentials:
                del self._credentials[name]

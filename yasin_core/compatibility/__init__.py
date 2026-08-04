from typing import Any

from yasin_core.compatibility.exceptions import (
    CompatibilityError,
    VersionMismatchError,
    APICompatibilityError,
    MigrationError,
    EcosystemValidationError,
)
from yasin_core.compatibility.version import (
    Version,
    is_compatible,
    VersionNegotiator,
)
from yasin_core.compatibility.api import APICompatibilityChecker
from yasin_core.compatibility.warnings import DeprecationManager, deprecated
from yasin_core.compatibility.adapters import LegacyAPIAdapter
from yasin_core.compatibility.migration import (
    SchemaMigrator,
    ConfigurationMigrator,
    DataMigrator,
)
from yasin_core.compatibility.ecosystem import (
    AgentCompatibilityValidator,
    HubCompatibilityValidator,
    RelayCompatibilityValidator,
    CLICompatibilityValidator,
    RuntimeCompatibilityChecker,
)


class CompatibilityManager:
    """
    Central orchestrator for the migration and compatibility framework.
    Exposed via the public SDK YasinCoreClient.compatibility.
    """

    def __init__(self, client: Any = None):
        self.client = client
        self.checker = RuntimeCompatibilityChecker(client)
        self.version_negotiator = VersionNegotiator()
        self.api_checker = APICompatibilityChecker()
        self.schema_migrator = SchemaMigrator()
        self.config_migrator = ConfigurationMigrator()
        self.data_migrator = DataMigrator()
        self.agent_validator = AgentCompatibilityValidator()
        self.hub_validator = HubCompatibilityValidator()
        self.relay_validator = RelayCompatibilityValidator()
        self.cli_validator = CLICompatibilityValidator()

    def check_runtime(self) -> dict:
        """Helper to run a full compatibility report on the active core runtime."""
        return self.checker.check_runtime_compatibility()


__all__ = [
    "CompatibilityError",
    "VersionMismatchError",
    "APICompatibilityError",
    "MigrationError",
    "EcosystemValidationError",
    "Version",
    "is_compatible",
    "VersionNegotiator",
    "APICompatibilityChecker",
    "DeprecationManager",
    "deprecated",
    "LegacyAPIAdapter",
    "SchemaMigrator",
    "ConfigurationMigrator",
    "DataMigrator",
    "AgentCompatibilityValidator",
    "HubCompatibilityValidator",
    "RelayCompatibilityValidator",
    "CLICompatibilityValidator",
    "RuntimeCompatibilityChecker",
    "CompatibilityManager",
]

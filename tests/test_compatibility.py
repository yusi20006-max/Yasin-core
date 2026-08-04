import pytest
import logging
import warnings
from typing import Any

from yasin_core.sdk import (
    YasinCoreClient,
    Version,
    is_compatible,
    VersionNegotiator,
    APICompatibilityChecker,
    DeprecationManager,
    deprecated,
    LegacyAPIAdapter,
    SchemaMigrator,
    ConfigurationMigrator,
    DataMigrator,
    AgentCompatibilityValidator,
    HubCompatibilityValidator,
    RelayCompatibilityValidator,
    CLICompatibilityValidator,
    RuntimeCompatibilityChecker,
    CompatibilityManager,
    VersionMismatchError,
    APICompatibilityError,
    MigrationError,
)
from yasin_core.compatibility.warnings import _manager


# 1. Version detection and comparison tests
def test_version_parsing_and_comparison():
    v1 = Version("1.6.0")
    v2 = Version("1.7.0-beta")
    v3 = Version("v1.7.0")
    v4 = Version("2.0.1")

    assert v1.major == 1 and v1.minor == 6 and v1.patch == 0 and v1.prerelease == ""
    assert v2.major == 1 and v2.minor == 7 and v2.patch == 0 and v2.prerelease == "beta"
    assert v3.major == 1 and v3.minor == 7 and v3.patch == 0 and v3.prerelease == ""

    # Comparisons
    assert v1 < v2
    assert v2 < v3
    assert v3 < v4
    assert v1 <= v3
    assert v4 > v3
    assert v3 >= v2
    assert v3 == Version("1.7.0")
    assert v1 != v4


# 2. Compatibility validation tests (caret, wildcard, operators)
def test_compatibility_validation():
    # Wildcard
    assert is_compatible("*", "1.6.0")
    assert is_compatible("", "1.6.0")

    # Caret ranges
    assert is_compatible("^1.6.0", "1.6.0")
    assert is_compatible("^1.6.0", "1.7.5")
    assert not is_compatible("^1.6.0", "2.0.0")
    assert not is_compatible("^1.6.0", "1.5.9")

    # Caret on 0.x versions
    assert is_compatible("^0.5.0", "0.5.2")
    assert not is_compatible("^0.5.0", "0.6.0")
    assert is_compatible("^0.0.5", "0.0.5")
    assert not is_compatible("^0.0.5", "0.0.6")

    # Operators
    assert is_compatible(">=1.6.0", "1.6.1")
    assert is_compatible("<=2.0.0", "1.9.9")
    assert is_compatible(">1.5.0", "1.6.0")
    assert is_compatible("<2.0.0", "1.8.0")
    assert is_compatible("==1.6.0", "1.6.0")
    assert is_compatible("!=1.6.0", "1.7.0")


# 3. SDK version negotiation tests
def test_version_negotiator():
    negotiator = VersionNegotiator()
    server_versions = ["1.5.0", "1.6.0", "1.7.0", "2.0.0"]

    # Handshake matching
    best = negotiator.negotiate("^1.5.0", server_versions)
    assert best == "1.7.0"

    best_any = negotiator.negotiate("*", server_versions)
    assert best_any == "2.0.0"

    # Negotiation fails
    with pytest.raises(VersionMismatchError):
        negotiator.negotiate("^3.0.0", server_versions)


# 4. API compatibility check tests
def test_api_compatibility_checker():
    checker = APICompatibilityChecker()

    class ValidTarget:
        id = "test-id"
        def execute_task(self, task):
            return True
        def status(self):
            return "ok"

    class InvalidTarget:
        id = "test-id"
        # execute_task misses 'task' parameter
        def execute_task(self):
            return True

    expected_api = {
        "id": "attribute",
        "execute_task": ["task"],
        "status": []
    }

    # Valid check
    report = checker.check_compatibility(ValidTarget(), expected_api)
    assert report["compatible"] is True
    assert len(report["missing"]) == 0
    assert len(report["mismatched_signatures"]) == 0

    # Invalid check
    report_invalid = checker.check_compatibility(InvalidTarget(), expected_api)
    assert report_invalid["compatible"] is False
    assert "status" in report_invalid["missing"]
    assert "execute_task" in report_invalid["mismatched_signatures"]

    # Raise on error
    with pytest.raises(APICompatibilityError):
        checker.check_compatibility(InvalidTarget(), expected_api, raise_on_error=True)


# 5. Deprecation management and warnings tests
def test_deprecation_warnings(caplog):
    initial_count = _manager.warnings_count

    @deprecated(since="1.6.0", instead="new_func")
    def old_func(x):
        return x * 2

    @deprecated(since="1.6.0")
    class OldClass:
        def __init__(self):
            pass

    # Call deprecated function
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        res = old_func(5)
        assert res == 10
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "deprecated" in str(w[0].message)

    # Instantiate deprecated class
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        obj = OldClass()
        assert isinstance(obj, OldClass)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)

    # Verify count increments
    assert _manager.warnings_count == initial_count + 2

    # Check that warning logs were structured
    assert any("DEPRECATED:" in record.message for record in caplog.records)


# 6. Legacy API Adapter tests
def test_legacy_api_adapter():
    class ModernObj:
        def __init__(self):
            self.modern_field = "modern"
        def execute_task(self, task):
            return f"Processed {task}"

    modern = ModernObj()
    alias_mapping = {
        "legacy_field": "modern_field",
        "execute": "execute_task"
    }

    def custom_execute(target_obj, task_id, priority=0):
        return target_obj.execute_task(f"{task_id} with priority {priority}")

    custom_translators = {
        "legacy_execute_custom": custom_execute
    }

    adapter = LegacyAPIAdapter(
        modern,
        alias_mapping=alias_mapping,
        custom_translators=custom_translators,
        since_version="1.6.0"
    )

    # Test attribute access alias
    assert adapter.legacy_field == "modern"

    # Test attribute setting alias
    adapter.legacy_field = "updated"
    assert modern.modern_field == "updated"

    # Test method alias
    assert adapter.execute("task-1") == "Processed task-1"

    # Test custom translator call
    assert adapter.legacy_execute_custom("task-2", priority=1) == "Processed task-2 with priority 1"

    # Test fallback attribute
    assert adapter.modern_field == "updated"


# 7. Schema migration tests
def test_schema_migrator():
    migrator = SchemaMigrator()

    # Register versioned schema migrations
    migrator.register_migration("1.0", "2.0", lambda d: {**d, "b": d["a"] * 2})
    migrator.register_migration("2.0", "3.0", lambda d: {**d, "c": d["b"] + 10})

    data = {"a": 5}
    migrated = migrator.migrate(data, current_version="1.0", target_version="3.0")
    assert migrated == {"a": 5, "b": 10, "c": 20}

    # If already at target version
    assert migrator.migrate(data, "1.0", "1.0") == data

    # Error on non-existent path
    with pytest.raises(MigrationError):
        migrator.migrate(data, "1.0", "4.0")


# 8. Configuration migration tests
def test_configuration_migrator():
    old_config = {
        "db_host": "127.0.0.1",
        "api_key": "secret",
    }

    migrated = ConfigurationMigrator.migrate_config(
        old_config,
        key_renames={"db_host": "database.host"},
        default_injects={"database.port": 5432, "debug": True},
        custom_migrator=lambda d: {**d, "api_key": d["api_key"].upper()}
    )

    assert migrated["database"] == {"host": "127.0.0.1", "port": 5432}
    assert migrated["debug"] is True
    assert migrated["api_key"] == "SECRET"


# 9. Data migration tests
def test_data_migrator():
    records = [
        {"id": 1, "name": "alice"},
        {"id": 2, "name": "bob"}
    ]

    migrated = DataMigrator.migrate_records(
        records,
        transformer=lambda r: {**r, "name": r["name"].capitalize()}
    )

    assert migrated == [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"}
    ]


# 10. Ecosystem compatibility validation tests
def test_ecosystem_compatibility_validators():
    # Agent Validator
    class CompliantAgent:
        name = "test-agent"
        core_version_compat = "^3.0.0"
        def execute_task(self, task):
            pass

    class NonCompliantAgent:
        pass

    assert AgentCompatibilityValidator.validate(CompliantAgent())["compatible"] is True
    assert AgentCompatibilityValidator.validate(NonCompliantAgent())["compatible"] is False

    # Hub Validator
    compliant_hub = {"id": "hub-1", "version": "1.0.0", "core_version_compat": "*"}
    non_compliant_hub = {"id": "hub-2"}
    assert HubCompatibilityValidator.validate(compliant_hub)["compatible"] is True
    assert HubCompatibilityValidator.validate(non_compliant_hub)["compatible"] is False

    # Relay Validator
    class CompliantRelay:
        core_version_compat = "*"
        def process(self, post):
            pass

    class NonCompliantRelay:
        pass

    assert RelayCompatibilityValidator.validate(CompliantRelay())["compatible"] is True
    assert RelayCompatibilityValidator.validate(NonCompliantRelay())["compatible"] is False

    # CLI Validator
    compliant_cli = {"commands": {"start": "desc"}, "core_version_compat": "^3.0.0"}
    non_compliant_cli = {"commands": "not-a-dict"}
    assert CLICompatibilityValidator.validate(compliant_cli)["compatible"] is True
    assert CLICompatibilityValidator.validate(non_compliant_cli)["compatible"] is False


# 11. Runtime compatibility and CompatibilityManager tests
def test_runtime_compatibility_and_manager():
    client = YasinCoreClient()
    # Populate mock config settings to avoid uninitialized config WARN status
    client.config.settings = {"app": {"debug": True}}
    manager = CompatibilityManager(client)

    # Check manager properties delegating properly
    assert isinstance(manager.checker, RuntimeCompatibilityChecker)
    assert isinstance(manager.version_negotiator, VersionNegotiator)

    # Check full compatibility report
    report = manager.check_runtime()
    assert report["compatible"] is True
    assert report["checks"]["config"]["status"] == "PASS"
    assert report["checks"]["services"]["status"] == "PASS"
    assert report["checks"]["storage"]["status"] == "PASS"
    assert report["checks"]["di"]["status"] == "PASS"

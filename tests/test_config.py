import os
import json
import pytest
import tempfile
from pathlib import Path

from yasin_core.config import ConfigurationManager, ConfigurationValidationError, Settings
from yasin_core.sdk import YasinCoreClient
from yasin_core.core.runtime import YasinRuntime
from yasin_core.di import DIContainer


def test_default_file_loading():
    # Test loading of default.yaml when no custom path is passed
    config = ConfigurationManager()
    assert config.get("app.name") == "Yasin Core"
    assert config.get("runtime.mode") == "development"
    assert isinstance(config.get("plugins.enabled"), list)


def test_custom_file_loading_and_fallback():
    # Create a temporary custom YAML file
    custom_content = """
app:
  name: Custom App Name
  version: 2.0.0
database:
  host: localhost
  port: 5432
"""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(custom_content)
        temp_path = f.name

    try:
        # Load custom configuration
        config = ConfigurationManager(path=temp_path)

        # Verify custom values
        assert config.get("app.name") == "Custom App Name"
        assert config.get("app.version") == "2.0.0"
        assert config.get("database.host") == "localhost"
        assert config.get("database.port") == 5432

        # Verify fallback to default.yaml for keys not present in custom file
        assert config.get("runtime.mode") == "development"
        assert config.get("providers.default") == "local"
    finally:
        os.remove(temp_path)


def test_environment_variable_overrides():
    # Set environment variables with YASIN_ prefix
    os.environ["YASIN_APP_NAME"] = "Env App Name"
    os.environ["YASIN_APP__VERSION"] = "3.1.4"  # Double underscores
    os.environ["YASIN_DATABASE__PORT"] = "9999"  # Integer conversion
    os.environ["YASIN_DATABASE__SECURE"] = "true"  # Boolean conversion
    os.environ["YASIN_DATABASE__PI"] = "3.14159"  # Float conversion
    os.environ["YASIN_DATABASE__NULL_VAL"] = "null"  # Null/None conversion
    os.environ["YASIN_DATABASE__HOSTS"] = '["host1", "host2"]'  # List JSON conversion
    os.environ["YASIN_DATABASE__CREDENTIALS"] = '{"username": "admin"}'  # Dict JSON conversion

    try:
        config = ConfigurationManager()

        # Verify environment variable overrides
        assert config.get("app.name") == "Env App Name"
        assert config.get("app.version") == "3.1.4"
        assert config.get("database.port") == 9999
        assert config.get("database.secure") is True
        assert config.get("database.pi") == 3.14159
        assert config.get("database.null_val") is None
        assert config.get("database.hosts") == ["host1", "host2"]
        assert config.get("database.credentials") == {"username": "admin"}
    finally:
        # Clean up environment variables
        for key in [
            "YASIN_APP_NAME", "YASIN_APP__VERSION", "YASIN_DATABASE__PORT",
            "YASIN_DATABASE__SECURE", "YASIN_DATABASE__PI", "YASIN_DATABASE__NULL_VAL",
            "YASIN_DATABASE__HOSTS", "YASIN_DATABASE__CREDENTIALS"
        ]:
            if key in os.environ:
                del os.environ[key]


def test_environment_variable_structure_match():
    # Register schema and default with specific snake_case / camel_case
    config = ConfigurationManager()
    config.register_schema("app.version_number", str, default="1.0.0")

    # Override with env var using matching underscore format
    os.environ["YASIN_APP_VERSION_NUMBER"] = "9.9.9"
    try:
        config.reload()
        assert config.get("app.version_number") == "9.9.9"
    finally:
        if "YASIN_APP_VERSION_NUMBER" in os.environ:
            del os.environ["YASIN_APP_VERSION_NUMBER"]


def test_schema_validation_type_checks():
    config = ConfigurationManager()

    # Register schema for app.port as integer
    config.register_schema("app.port", int, default=8080)
    assert config.get_int("app.port") == 8080

    # Try overriding with a string - should fail validation
    with pytest.raises(ConfigurationValidationError) as exc:
        config.set("app.port", "invalid-port-string")
    assert "must be of type int" in str(exc.value)


def test_schema_validation_required():
    config = ConfigurationManager()

    # Register a required field that is not in defaults/config
    with pytest.raises(ConfigurationValidationError) as exc:
        config.register_schema("api.secret_key", str, required=True)
    assert "Required key 'api.secret_key' is missing" in str(exc.value)

    # Now set it, registration should succeed
    config.set("api.secret_key", "my-super-secret")
    config.register_schema("api.secret_key", str, required=True)
    assert config.get("api.secret_key") == "my-super-secret"


def test_schema_validation_custom_validator():
    config = ConfigurationManager()

    # Register schema with custom validator
    def port_validator(val):
        return isinstance(val, int) and 1 <= val <= 65535

    config.register_schema("app.port", int, default=8080, validator=port_validator)

    # Set to a valid port
    config.set("app.port", 3000)
    assert config.get_int("app.port") == 3000

    # Set to an invalid port (out of range)
    with pytest.raises(ConfigurationValidationError) as exc:
        config.set("app.port", 99999)
    assert "Custom validation failed" in str(exc.value)


def test_sensitive_value_masking():
    config = ConfigurationManager()

    # Register sensitive key
    config.set("auth.token", "secret12345")
    config.register_schema("auth.token", str, sensitive=True)

    # Retrieve securely / plain-text
    assert config.get("auth.token") == "secret12345"
    assert config.get_secure("auth.token") == "secret12345"

    # Verify status report masks the sensitive value
    status_report = config.status()
    configuration_status = status_report["configuration"]
    assert configuration_status["auth"]["token"] == "******"


def test_runtime_and_di_integration():
    client = YasinCoreClient()

    # 1. Resolve from Client
    assert client.config is not None
    assert isinstance(client.config, ConfigurationManager)

    # 2. Resolve from DIContainer
    container = client.di_container
    resolved_by_class = container.resolve(ConfigurationManager)
    resolved_by_name = container.resolve("config")

    assert resolved_by_class is client.config
    assert resolved_by_name is client.config

    # 3. Resolve from Service Registry
    service_registry = client.service_registry
    service = service_registry.get_service("config")
    assert service is client.config

    # Test Service Registry initialization/shutdown sequence
    assert service.health()["healthy"] is True


def test_runtime_service_manager_lifecycle():
    runtime = YasinRuntime()
    assert runtime.config is not None

    # Verify service registry contains 'config' and is loaded
    assert runtime.registry.has_service("config")

    # Execute start/stop lifecycle
    runtime.start()
    assert runtime.running is True

    runtime.stop()
    assert runtime.running is False


def test_dynamic_plugin_config_registration():
    config = ConfigurationManager()

    # Plugin specific defaults and schema
    plugin_defaults = {
        "host": "plugin-host",
        "port": 1234,
        "api_key": "plugin-api-key"
    }
    plugin_schema = {
        "host": {"type": str, "required": True},
        "port": {"type": int, "required": True},
        "api_key": {"type": str, "sensitive": True}
    }

    # Register plugin configurations dynamically
    config.register_plugin_config("my_test_plugin", defaults=plugin_defaults, schema=plugin_schema)

    # Verify defaults are registered under plugins namespace
    assert config.get("plugins.my_test_plugin.host") == "plugin-host"
    assert config.get_int("plugins.my_test_plugin.port") == 1234
    assert config.get("plugins.my_test_plugin.api_key") == "plugin-api-key"

    # Verify sensitive masking under plugin config status
    status_report = config.status()
    plugin_config_status = status_report["configuration"]["plugins"]["my_test_plugin"]
    assert plugin_config_status["api_key"] == "******"
    assert plugin_config_status["host"] == "plugin-host"

    # Try dynamic overrides and validation failure
    with pytest.raises(ConfigurationValidationError):
        config.set("plugins.my_test_plugin.port", "invalid-port")


def test_helper_getters():
    config = ConfigurationManager()
    config.set("test.string", "abc")
    config.set("test.int", 123)
    config.set("test.float", 123.45)
    config.set("test.bool_true", True)
    config.set("test.bool_false", False)
    config.set("test.bool_str_true", "true")
    config.set("test.list", [1, 2, 3])
    config.set("test.dict", {"a": 1})

    assert config.get_string("test.string") == "abc"
    assert config.get_int("test.int") == 123
    assert config.get_float("test.float") == 123.45
    assert config.get_bool("test.bool_true") is True
    assert config.get_bool("test.bool_false") is False
    assert config.get_bool("test.bool_str_true") is True
    assert config.get_list("test.list") == [1, 2, 3]
    assert config.get_dict("test.dict") == {"a": 1}

    # Check typing error raises
    with pytest.raises(TypeError):
        config.get_list("test.string")
    with pytest.raises(TypeError):
        config.get_dict("test.string")

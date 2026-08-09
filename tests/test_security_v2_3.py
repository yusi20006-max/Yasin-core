import pytest
from typing import Any, Dict, List

from yasin_core.sdk import YasinCoreClient
from yasin_core.security import (
    Permission,
    Role,
    Subject,
    SecurityError,
    AccessDeniedError,
    AuthenticationError,
    PermissionValidationError,
    SecurityManager,
    require_permission,
    AuditLogger,
    SECURITY_EVENT_AUDIT,
    SECURITY_ACCESS_GRANTED,
    SECURITY_ACCESS_DENIED,
)
from yasin_core.security.policy import PolicyEngine, DefaultRBACPolicy
from yasin_core.security.protection import (
    ConfigurationSecurityValidator,
    SensitiveDataProtector,
    InMemoryCredentialStore
)
from yasin_core.events import EventBus, Event
from yasin_core.context.manager import get_current_context


def test_permission_wildcard_matching():
    """Verify fnmatch-style wildcard matching on Permissions."""
    p1 = Permission(name="service:storage:read")
    p2 = Permission(name="service:*:read")
    p3 = Permission(name="plugin:translator:*")
    p4 = Permission(name="*")

    assert p1.matches("service:storage:read")
    assert not p1.matches("service:storage:write")

    assert p2.matches("service:storage:read")
    assert p2.matches("service:database:read")
    assert not p2.matches("service:storage:write")

    assert p3.matches("plugin:translator:load")
    assert p3.matches("plugin:translator:execute")
    assert not p3.matches("plugin:search:execute")

    assert p4.matches("anything:at:all")


def test_role_and_subject_rbac():
    """Test standard RBAC role and subject permission checking."""
    # Create permissions
    read_perm = Permission("service:storage:read")
    write_perm = Permission("service:storage:write")

    # Create Roles
    reader_role = Role(name="reader", permissions=[read_perm])
    writer_role = Role(name="writer", permissions=[write_perm])
    admin_role = Role(name="admin", permissions=["*"])

    # Verify role has_permission
    assert reader_role.has_permission("service:storage:read")
    assert not reader_role.has_permission("service:storage:write")
    assert admin_role.has_permission("service:storage:write")

    # Create Subjects
    subject_user = Subject(id="user-1", subject_type="user", roles=[reader_role])
    subject_admin = Subject(id="admin-1", subject_type="user", roles=[admin_role])
    subject_mixed = Subject(
        id="agent-1",
        subject_type="agent",
        roles=[reader_role],
        permissions=["plugin:translator:execute"]
    )

    policy_engine = PolicyEngine()
    roles_registry = {
        "reader": reader_role,
        "writer": writer_role,
        "admin": admin_role
    }

    # Test policy evaluation
    assert policy_engine.evaluate_all(subject_user, "service:storage:read", roles_registry)
    assert not policy_engine.evaluate_all(subject_user, "service:storage:write", roles_registry)

    assert policy_engine.evaluate_all(subject_admin, "service:storage:write", roles_registry)

    assert policy_engine.evaluate_all(subject_mixed, "service:storage:read", roles_registry)
    assert policy_engine.evaluate_all(subject_mixed, "plugin:translator:execute", roles_registry)
    assert not policy_engine.evaluate_all(subject_mixed, "plugin:translator:load", roles_registry)


def test_sensitive_data_protector_and_credential_store():
    """Verify SensitiveDataProtector encryption/decryption/masking and CredentialStore."""
    protector = SensitiveDataProtector(master_key="my_super_test_master_key")

    plain_text = "my-secret-token-123"
    encrypted = protector.encrypt(plain_text)

    assert encrypted.startswith("ENC:")
    assert encrypted != plain_text

    decrypted = protector.decrypt(encrypted)
    assert decrypted == plain_text

    # Masking test
    assert protector.mask_value("password123") == "pa******23"
    assert protector.mask_value("123") == "******"
    assert protector.mask_value(None) == "None"

    assert protector.is_masked("******")
    assert protector.is_masked("pa******23")
    assert not protector.is_masked("password123")

    # Credential Store test
    store = InMemoryCredentialStore(protector=protector)
    store.set_credential("db_password", "super_secret_db_pass")

    # Check that it's stored encrypted internally
    assert store._credentials["db_password"].startswith("ENC:")

    # Decrypted value is returned
    assert store.get_credential("db_password") == "super_secret_db_pass"

    store.remove_credential("db_password")
    assert store.get_credential("db_password") is None


def test_config_security_validation():
    """Test scanning configuration dictionaries for plain text sensitive credentials."""
    validator = ConfigurationSecurityValidator()

    bad_config = {
        "app": {
            "name": "YasinApp",
            "port": 8080
        },
        "database": {
            "password": "unmasked_plain_password",
            "user": "root"
        },
        "openai": {
            "api_key": "sk-proj-plaintextkey123"
        }
    }

    good_config = {
        "app": {
            "name": "YasinApp",
            "port": 8080
        },
        "database": {
            "password": "******",
            "user": "root"
        },
        "openai": {
            "api_key": "ENC:YmFzZTY0ZW5jb2RlZGFlc3NhbHQ="
        }
    }

    warnings_bad = validator.validate_config(bad_config)
    assert len(warnings_bad) == 2
    assert any("database.password" in w for w in warnings_bad)
    assert any("openai.api_key" in w for w in warnings_bad)

    warnings_good = validator.validate_config(good_config)
    assert len(warnings_good) == 0


def test_security_manager_validation_methods():
    """Test SecurityManager's specific validation methods (service, plugin, agent, API)."""
    client = YasinCoreClient()
    sec = client.security

    # Initialize roles
    reader_role = Role(name="service_reader", permissions=["service:*:read"])
    plugin_executor_role = Role(name="plugin_runner", permissions=["plugin:*:execute"])
    tool_executor_role = Role(name="tool_runner", permissions=["tool:translator:use"])

    sec.register_role(reader_role)
    sec.register_role(plugin_executor_role)
    sec.register_role(tool_executor_role)

    # Register subjects
    agent_subject = Subject(id="agent-007", subject_type="agent", roles=[reader_role, plugin_executor_role, tool_executor_role])
    sec.register_subject(agent_subject)

    # 1. Service access
    assert sec.validate_service_access(agent_subject, "storage", "read")
    with pytest.raises(AccessDeniedError):
        sec.validate_service_access(agent_subject, "storage", "write")

    # 2. Plugin access
    assert sec.validate_plugin_access(agent_subject, "translator", "execute")
    with pytest.raises(AccessDeniedError):
        sec.validate_plugin_access(agent_subject, "translator", "load")

    # 3. Agent capability
    capability_subject = Subject(id="nlp-agent", subject_type="agent", permissions=["capability:summarize"])
    sec.register_subject(capability_subject)
    assert sec.validate_agent_capability("nlp-agent", "summarize")
    with pytest.raises(AccessDeniedError):
        sec.validate_agent_capability("nlp-agent", "web_search")

    # 4. Agent tool execution permission
    class MockTool:
        def __init__(self, name):
            self.name = name

    class MockAgent:
        def __init__(self, name, tools):
            self.name = name
            self.tools = tools

    t1 = MockTool("translator")
    t2 = MockTool("web_search")
    mock_agent = MockAgent("agent-007", [t1, t2])

    assert sec.validate_agent_tool(mock_agent, "translator")
    with pytest.raises(AccessDeniedError):
        sec.validate_agent_tool(mock_agent, "file_write")

    # 5. API key access
    # Register API key subject
    api_subject = Subject(id="api_key:testkey1", subject_type="api", permissions=["api:/v1/query:GET"])
    sec.register_subject(api_subject)

    assert sec.validate_api_access("testkey12345", "/v1/query", "GET")

    # Incorrect permissions
    with pytest.raises(AccessDeniedError):
        sec.validate_api_access("testkey12345", "/v1/query", "POST")

    # Unregistered key
    with pytest.raises(AuthenticationError):
        sec.validate_api_access("wrongkey", "/v1/query", "GET")

    # اعطای دسترسی wildcard (admin) اکنون فقط از طریق ثبت صریح subject ممکن است،
    # نه یک کلید ثابت هاردکد در کد (که یک backdoor امنیتی بود و حذف شده است).
    admin_subject = Subject(id="api_key:realadmi", subject_type="api", permissions=["api:*"])
    sec.register_subject(admin_subject)
    assert sec.validate_api_access("realadminkey123", "/v1/any", "POST")

    # رشته‌ی قدیمی "admin-key" دیگر هیچ دسترسی خاصی نمی‌دهد و باید مثل هر
    # کلید ثبت‌نشده‌ی دیگری رد شود.
    with pytest.raises(AuthenticationError):
        sec.validate_api_access("admin-key", "/v1/any", "POST")


def test_require_permission_decorator():
    """Verify enforcemement of runtime security decorator require_permission."""
    # Set up some dummy function
    @require_permission("service:database:write")
    def write_to_db(subject: Subject, data: str):
        return f"written: {data}"

    user_subject = Subject(id="user-1", subject_type="user", permissions=["service:database:read"])
    admin_subject = Subject(id="admin-1", subject_type="user", permissions=["service:database:write"])

    # Explicit argument
    assert write_to_db(admin_subject, "hello") == "written: hello"

    with pytest.raises(AccessDeniedError):
        write_to_db(user_subject, "hello")

    # Context-based validation: set subject in active context
    client = YasinCoreClient()
    # Register security_manager in DI container so decorator can resolve it
    client.di_container.register_instance(SecurityManager, client.security)

    @require_permission("service:storage:delete")
    def delete_item(item_id: str):
        return f"deleted: {item_id}"

    # No subject in context, raises AccessDeniedError
    with pytest.raises(AccessDeniedError):
        delete_item("item-1")

    # Create execution context and set subject
    ctx = client.create_context({"security_subject": admin_subject})

    # We test with the decorator fallback evaluation
    # To test decorator's fallback without DI resolution, we temporarily unregister SecurityManager
    client.di_container._registrations.pop(SecurityManager, None)

    # If the subject itself has wildcard permission "*"
    super_subject = Subject(id="super-1", subject_type="user", permissions=["*"])
    assert delete_item("item-1", subject=super_subject) == "deleted: item-1"


def test_audit_logging_and_event_bus():
    """Verify AuditLogger history and structured dispatching to the EventBus."""
    bus = EventBus()
    audit_logger = AuditLogger(event_bus=bus)

    audit_events: List[Event] = []
    granted_events: List[Event] = []
    denied_events: List[Event] = []

    bus.subscribe(SECURITY_EVENT_AUDIT, lambda ev: audit_events.append(ev))
    bus.subscribe(SECURITY_ACCESS_GRANTED, lambda ev: granted_events.append(ev))
    bus.subscribe(SECURITY_ACCESS_DENIED, lambda ev: denied_events.append(ev))

    # Log successful access
    audit_logger.log_event(
        action="plugin_load",
        subject_id="agent-01",
        subject_type="agent",
        resource="plugin:translator",
        result="GRANTED",
        details="Access granted by RBACPolicy"
    )

    # Log denied access
    audit_logger.log_event(
        action="service_write",
        subject_id="agent-01",
        subject_type="agent",
        resource="service:database",
        result="DENIED",
        details="Access denied: missing capability"
    )

    # Verify history
    history = audit_logger.get_history()
    assert len(history) == 2
    assert history[0]["action"] == "plugin_load"
    assert history[0]["result"] == "GRANTED"
    assert history[1]["action"] == "service_write"
    assert history[1]["result"] == "DENIED"

    # Filter history
    granted_history = audit_logger.get_history(result="GRANTED")
    assert len(granted_history) == 1
    assert granted_history[0]["action"] == "plugin_load"

    # Verify EventBus listeners received the events
    assert len(audit_events) == 2
    assert len(granted_events) == 1
    assert len(denied_events) == 1

    assert audit_events[0].payload["action"] == "plugin_load"
    assert audit_events[1].payload["action"] == "service_write"

    assert granted_events[0].payload["resource"] == "plugin:translator"
    assert denied_events[0].payload["resource"] == "service:database"

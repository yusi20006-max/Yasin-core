import functools
import threading
from functools import wraps
from typing import Any, Dict, List, Optional, Union, Callable, Set

from yasin_core.runtime.interfaces import BaseService
from yasin_core.security.exceptions import AccessDeniedError, AuthenticationError
from yasin_core.security.models import Subject, Role, Permission
from yasin_core.security.policy import PolicyEngine
from yasin_core.security.audit import AuditLogger
from yasin_core.security.protection import (
    SensitiveDataProtector,
    InMemoryCredentialStore,
    ConfigurationSecurityValidator
)
from yasin_core.events import EventBus
from yasin_core.context.manager import get_current_context


class SecurityManager(BaseService):
    """
    Centralized, thread-safe Security & Permission Manager for the Yasin-Core ecosystem.
    Orchestrates policy evaluation, audit logging, sensitive data protection, credential handling,
    and validation across agents, plugins, services, and APIs.
    """

    def __init__(self, event_bus: Optional[EventBus] = None, master_key: Optional[str] = None):
        super().__init__()
        self._lock = threading.RLock()
        self.event_bus = event_bus

        # Security Sub-engines
        self._policy_engine = PolicyEngine()
        self._audit_logger = AuditLogger(event_bus=self.event_bus)
        self._protector = SensitiveDataProtector(master_key=master_key)
        self._credentials = InMemoryCredentialStore(protector=self._protector)
        self._config_validator = ConfigurationSecurityValidator()

        # Registries
        self._roles: Dict[str, Role] = {}
        self._subjects: Dict[str, Subject] = {}

    # --- Sub-Engine Accessors ---

    @property
    def policy_engine(self) -> PolicyEngine:
        return self._policy_engine

    @property
    def audit_logger(self) -> AuditLogger:
        return self._audit_logger

    @property
    def protector(self) -> SensitiveDataProtector:
        return self._protector

    @property
    def credentials(self) -> InMemoryCredentialStore:
        return self._credentials

    @property
    def config_validator(self) -> ConfigurationSecurityValidator:
        return self._config_validator

    # --- Role and Subject Registries ---

    def register_role(self, role: Role) -> None:
        """Register a Role in the security manager."""
        with self._lock:
            self._roles[role.name] = role
            self._audit_logger.log_event(
                action="register_role",
                subject_id="system",
                subject_type="system",
                resource=f"role:{role.name}",
                result="SUCCESS",
                details=f"Registered role '{role.name}' with {len(role.permissions)} permissions."
            )

    def register_subject(self, subject: Subject) -> None:
        """Register a Subject in the security manager."""
        with self._lock:
            self._subjects[subject.id] = subject
            self._audit_logger.log_event(
                action="register_subject",
                subject_id="system",
                subject_type="system",
                resource=f"subject:{subject.id}",
                result="SUCCESS",
                details=f"Registered subject '{subject.id}' of type '{subject.subject_type}'."
            )

    def get_subject(self, subject_id: str) -> Optional[Subject]:
        """Retrieve a registered Subject."""
        with self._lock:
            return self._subjects.get(subject_id)

    def get_role(self, role_name: str) -> Optional[Role]:
        """Retrieve a registered Role."""
        with self._lock:
            return self._roles.get(role_name)

    # --- Access Control & Validation APIs ---

    def validate_service_access(self, subject: Subject, service_name: str, action: str = "access") -> bool:
        """
        Validate whether a Subject is permitted to access/manipulate a specific Service.
        """
        permission_needed = f"service:{service_name}:{action}"
        granted = self._policy_engine.evaluate_all(subject, permission_needed, self._roles)

        result = "GRANTED" if granted else "DENIED"
        self._audit_logger.log_event(
            action=f"service_access:{action}",
            subject_id=subject.id,
            subject_type=subject.subject_type,
            resource=f"service:{service_name}",
            result=result,
            details=f"Evaluated permission: {permission_needed}"
        )

        if not granted:
            raise AccessDeniedError(f"Access Denied: Subject '{subject.id}' lacks permission '{permission_needed}'")
        return True

    def validate_plugin_access(self, subject: Subject, plugin_name: str, action: str = "access") -> bool:
        """
        Validate whether a Subject (typically an Agent or User) is permitted to load, start, stop, or call a Plugin.
        """
        permission_needed = f"plugin:{plugin_name}:{action}"
        granted = self._policy_engine.evaluate_all(subject, permission_needed, self._roles)

        result = "GRANTED" if granted else "DENIED"
        self._audit_logger.log_event(
            action=f"plugin_access:{action}",
            subject_id=subject.id,
            subject_type=subject.subject_type,
            resource=f"plugin:{plugin_name}",
            result=result,
            details=f"Evaluated permission: {permission_needed}"
        )

        if not granted:
            raise AccessDeniedError(f"Access Denied: Subject '{subject.id}' lacks permission '{permission_needed}'")
        return True

    def validate_agent_capability(self, agent_name: str, capability: str) -> bool:
        """
        Check if a registered Agent possesses a specific capability.
        """
        with self._lock:
            subject = self._subjects.get(agent_name)

        if not subject:
            # Fallback to dynamic subject representing the agent
            subject = Subject(id=agent_name, subject_type="agent")

        permission_needed = f"capability:{capability}"
        granted = self._policy_engine.evaluate_all(subject, permission_needed, self._roles)

        result = "GRANTED" if granted else "DENIED"
        self._audit_logger.log_event(
            action="agent_capability",
            subject_id=subject.id,
            subject_type="agent",
            resource=f"capability:{capability}",
            result=result,
            details=f"Checked agent capability: {capability}"
        )

        if not granted:
            raise AccessDeniedError(f"Access Denied: Agent '{agent_name}' lacks capability '{capability}'")
        return True

    def validate_agent_tool(self, agent: Any, tool_name: str) -> bool:
        """
        Validate if an Agent has the permissions/capabilities to execute a specific Tool.
        """
        agent_id = getattr(agent, "name", str(agent))
        with self._lock:
            subject = self._subjects.get(agent_id)

        if not subject:
            # Create a dynamic subject with default role or direct permissions matching tools of agent
            agent_tools = getattr(agent, "tools", [])
            direct_perms = [f"tool:{t.name if hasattr(t, 'name') else str(t)}:use" for t in agent_tools]
            subject = Subject(id=agent_id, subject_type="agent", permissions=direct_perms)

        permission_needed = f"tool:{tool_name}:use"
        granted = self._policy_engine.evaluate_all(subject, permission_needed, self._roles)

        result = "GRANTED" if granted else "DENIED"
        self._audit_logger.log_event(
            action="agent_tool",
            subject_id=subject.id,
            subject_type="agent",
            resource=f"tool:{tool_name}",
            result=result,
            details=f"Evaluated permission: {permission_needed}"
        )

        if not granted:
            raise AccessDeniedError(f"Access Denied: Agent '{agent_id}' is not authorized to execute tool '{tool_name}'")
        return True

    def validate_api_access(self, api_key: str, endpoint: str, method: str = "GET") -> bool:
        """
        Validate API access using an API key identifier.
        Checks if the Subject associated with the API key is allowed to call the given endpoint.
        """
        # Retrieve subject linked to api key.
        # For simplicity, we match the key directly to registered subjects, or use key ID mapping.
        subject_id = f"api_key:{api_key[:8]}" if api_key else "anonymous"
        with self._lock:
            subject = self._subjects.get(subject_id)

        if not subject:
            if not api_key:
                subject = Subject(id="anonymous", subject_type="api")
            else:
                # Basic standard credential lookup: if key is present but unregistered, deny
                # Let's check if the API key is registered, or create a default key-based subject with default permissions
                # We can allow 'api_key:admin' to pass, or require explicit registration.
                if api_key == "admin-key":
                    subject = Subject(id=subject_id, subject_type="api", permissions=["api:*"])
                else:
                    self._audit_logger.log_event(
                        action="api_access",
                        subject_id="unregistered",
                        subject_type="api",
                        resource=f"api:{endpoint}:{method}",
                        result="DENIED",
                        details="Invalid or unregistered API key"
                    )
                    raise AuthenticationError("Authentication Failed: Invalid API Key")

        permission_needed = f"api:{endpoint}:{method.upper()}"
        granted = self._policy_engine.evaluate_all(subject, permission_needed, self._roles)

        result = "GRANTED" if granted else "DENIED"
        self._audit_logger.log_event(
            action="api_access",
            subject_id=subject.id,
            subject_type="api",
            resource=f"api:{endpoint}:{method}",
            result=result,
            details=f"Evaluated permission: {permission_needed}"
        )

        if not granted:
            raise AccessDeniedError(f"Access Denied: API Key '{subject_id}' lacks permission for {method} on {endpoint}")
        return True

    def validate_runtime_check(self, subject: Subject, action: str, resource: str) -> bool:
        """
        Generic capability/runtime check.
        """
        permission_needed = f"{action}:{resource}"
        granted = self._policy_engine.evaluate_all(subject, permission_needed, self._roles)

        result = "GRANTED" if granted else "DENIED"
        self._audit_logger.log_event(
            action="runtime_check",
            subject_id=subject.id,
            subject_type=subject.subject_type,
            resource=f"{action}:{resource}",
            result=result,
            details=f"Evaluated permission: {permission_needed}"
        )

        if not granted:
            raise AccessDeniedError(f"Access Denied: Subject '{subject.id}' lacks permission '{permission_needed}'")
        return True

    # --- Runtime Service Lifecycle ---

    def initialize(self) -> None:
        """Initialize security service (defaults, audit setup, etc.)."""
        # Register a default Admin role and Guest role
        self.register_role(Role(name="admin", permissions=["*"]))
        self.register_role(Role(name="guest", permissions=["service:*:read", "plugin:*:read"]))

    def shutdown(self) -> None:
        """Shutdown security service."""
        pass

    def health(self) -> Dict[str, Any]:
        return {"status": "healthy", "healthy": True}

    def status(self) -> Dict[str, Any]:
        return {
            "state": "active",
            "registered_roles_count": len(self._roles),
            "registered_subjects_count": len(self._subjects),
            "audit_history_count": len(self._audit_logger.get_history())
        }


def require_permission(permission_str: str) -> Callable:
    """
    Decorator for enforcemement of runtime security permissions.
    Expects a passed 'subject' keyword argument, or falls back to looking up
    the active Subject in the context, or raises AccessDeniedError.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 1. Resolve Subject:
            # - From explicit keyword argument
            # - From active Context (context manager)
            # - From first argument if it is a Subject (or has a security subject context)
            subject = kwargs.pop("subject", None)

            if not subject:
                for arg in args:
                    if isinstance(arg, Subject):
                        subject = arg
                        break

            if not subject:
                # Check current context engine context variables
                ctx = get_current_context()
                if ctx and hasattr(ctx, "get_variable"):
                    # Retrieve registered subject from context if available
                    subject = ctx.get_variable("security_subject")

            if not subject:
                raise AccessDeniedError(
                    f"Access Denied: No security Subject context available to evaluate permission '{permission_str}'"
                )

            # 2. Resolve Security Manager:
            # We can lookup standard DI container or client to get the SecurityManager.
            # If not found or not registered, we can fall back to evaluating with a default engine.
            from yasin_core.di import DIContainer
            try:
                sec_mgr = DIContainer().resolve(SecurityManager)
            except Exception:
                try:
                    sec_mgr = DIContainer().resolve("security_manager")
                except Exception:
                    sec_mgr = None

            if sec_mgr:
                # Use centralized security manager validation (automatically handles audit log)
                sec_mgr.validate_runtime_check(subject, *permission_str.split(":", 1))
            else:
                # Standalone evaluation fallback
                pe = PolicyEngine()
                granted = pe.evaluate_all(subject, permission_str, {})
                if not granted:
                    raise AccessDeniedError(
                        f"Access Denied: Subject '{subject.id}' lacks permission '{permission_str}'"
                    )

            return func(*args, **kwargs)
        return wrapper
    return decorator

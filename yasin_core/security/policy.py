from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from yasin_core.security.models import Subject, Role


class BasePolicy(ABC):
    """
    Abstract interface for evaluating security access control decisions.
    """

    @abstractmethod
    def evaluate(self, subject: Subject, required_permission: str, roles_registry: Dict[str, Role]) -> bool:
        """
        Evaluate if the subject should be granted access to the required permission.

        Args:
            subject: The active security subject.
            required_permission: The capability or permission identifier string to check.
            roles_registry: Global roles registry to look up permission lists mapped to roles.

        Returns:
            True if permission is granted, False otherwise.
        """
        pass


class DefaultRBACPolicy(BasePolicy):
    """
    Standard Role-Based and Capability-Based Access Control policy.
    Checks:
      1. Direct permissions assigned to the Subject.
      2. Permissions inside the Roles belonging to the Subject.
    """

    def evaluate(self, subject: Subject, required_permission: str, roles_registry: Dict[str, Role]) -> bool:
        # 1. Check direct permissions
        for dp in subject.direct_permissions:
            if dp.matches(required_permission):
                return True

        # 2. Check subject's roles
        for role_name in subject.roles:
            # Check if Role object exists directly embedded in the subject
            role_obj = subject._role_objects.get(role_name)

            # If not embedded, lookup in the global roles registry
            if not role_obj:
                role_obj = roles_registry.get(role_name)

            if role_obj and role_obj.has_permission(required_permission):
                return True

        return False


class PolicyEngine:
    """
    Manages and executes security policies to decide access control grants.
    """

    def __init__(self) -> None:
        self._policies: List[BasePolicy] = [DefaultRBACPolicy()]

    def register_policy(self, policy: BasePolicy) -> None:
        """Register a custom security policy."""
        if policy not in self._policies:
            self._policies.append(policy)

    def evaluate_all(self, subject: Subject, required_permission: str, roles_registry: Dict[str, Role]) -> bool:
        """
        Evaluate all registered policies against the subject and permission.
        Returns True if ANY policy grants access (or we can require all, let's say any to allow cumulative grants,
        but allow custom policies to take precedence if desired. Any matching default RBAC or custom policy is standard).
        """
        if not self._policies:
            return False

        for policy in self._policies:
            if policy.evaluate(subject, required_permission, roles_registry):
                return True
        return False

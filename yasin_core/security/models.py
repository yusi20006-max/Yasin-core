import fnmatch
from typing import Any, Dict, List, Optional, Union, Set


class Permission:
    """
    Represents a discrete permission or capability in the system.
    Supports attribute-based access control (ABAC) through dynamic constraints.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        attributes: Optional[Dict[str, Any]] = None
    ):
        self.name = name.strip()
        self.description = description
        self.attributes = attributes or {}

    def matches(self, required: str) -> bool:
        """
        Check if this permission matches the required permission pattern.
        Supports standard wildcards (e.g., 'service:*' matches 'service:read').
        """
        req_clean = required.strip()
        # fnmatchcase evaluates globs like service:* on service:read
        return fnmatch.fnmatchcase(req_clean, self.name) or fnmatch.fnmatchcase(self.name, req_clean)

    def __repr__(self) -> str:
        return f"Permission(name='{self.name}', attributes={self.attributes})"


class Role:
    """
    Groups multiple permissions under a single named role.
    """

    def __init__(
        self,
        name: str,
        permissions: Optional[List[Union[str, Permission]]] = None,
        description: str = ""
    ):
        self.name = name.strip()
        self.description = description
        self.permissions: List[Permission] = []

        if permissions:
            for p in permissions:
                self.add_permission(p)

    def add_permission(self, permission: Union[str, Permission]) -> None:
        """Add a permission to this role."""
        if isinstance(permission, str):
            self.permissions.append(Permission(name=permission))
        elif isinstance(permission, Permission):
            self.permissions.append(permission)
        else:
            raise TypeError("Permission must be a string or a Permission instance.")

    def has_permission(self, required_permission: str) -> bool:
        """Check if any permission in this role matches the required permission."""
        for p in self.permissions:
            if p.matches(required_permission):
                return True
        return False

    def __repr__(self) -> str:
        return f"Role(name='{self.name}', permissions_count={len(self.permissions)})"


class Subject:
    """
    Represents an active security entity (e.g., an Agent, a Plugin, a User, or an API client).
    """

    def __init__(
        self,
        id: str,
        subject_type: str,  # "agent", "plugin", "user", "api" etc.
        roles: Optional[List[Union[str, Role]]] = None,
        permissions: Optional[List[Union[str, Permission]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.id = id.strip()
        self.subject_type = subject_type.strip().lower()
        self.roles: Set[str] = set()
        self.direct_permissions: List[Permission] = []
        self.metadata = metadata or {}

        # Cache of roles list/objects if passed
        self._role_objects: Dict[str, Role] = {}

        if roles:
            for r in roles:
                self.add_role(r)

        if permissions:
            for p in permissions:
                self.add_permission(p)

    def add_role(self, role: Union[str, Role]) -> None:
        """Associate a role with this subject."""
        if isinstance(role, str):
            self.roles.add(role.strip())
        elif isinstance(role, Role):
            self.roles.add(role.name)
            self._role_objects[role.name] = role
        else:
            raise TypeError("Role must be a string or a Role instance.")

    def add_permission(self, permission: Union[str, Permission]) -> None:
        """Add a direct permission assignment to this subject."""
        if isinstance(permission, str):
            self.direct_permissions.append(Permission(name=permission))
        elif isinstance(permission, Permission):
            self.direct_permissions.append(permission)
        else:
            raise TypeError("Permission must be a string or a Permission instance.")

    def get_role_objects(self) -> List[Role]:
        """Return all embedded Role objects."""
        return list(self._role_objects.values())

    def __repr__(self) -> str:
        return f"Subject(id='{self.id}', type='{self.subject_type}', roles={list(self.roles)})"

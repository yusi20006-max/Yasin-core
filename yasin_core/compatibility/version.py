import re
from typing import List, Tuple, Union, Optional, Any
from yasin_core.compatibility.exceptions import VersionMismatchError


class Version:
    """
    Thread-safe and robust semantic version comparison class.
    Parses versions in the form major.minor.patch[-prerelease].
    """

    def __init__(self, version_str: str):
        self.raw = version_str
        self.major, self.minor, self.patch, self.prerelease = self._parse(version_str)

    def _parse(self, version_str: str) -> Tuple[int, int, int, str]:
        # Remove whitespace and leading 'v'
        clean_str = version_str.strip().lstrip("v")

        # Split prerelease
        if "-" in clean_str:
            release_part, prerelease_part = clean_str.split("-", 1)
        else:
            release_part, prerelease_part = clean_str, ""

        # Parse major.minor.patch
        parts = release_part.split(".")
        major = int(re.sub(r"\D", "", parts[0])) if parts and parts[0].isdigit() or re.sub(r"\D", "", parts[0]) else 0
        minor = int(re.sub(r"\D", "", parts[1])) if len(parts) > 1 and (parts[1].isdigit() or re.sub(r"\D", "", parts[1])) else 0
        patch = int(re.sub(r"\D", "", parts[2])) if len(parts) > 2 and (parts[2].isdigit() or re.sub(r"\D", "", parts[2])) else 0

        return major, minor, patch, prerelease_part

    def _as_tuple(self) -> Tuple[int, int, int, bool, str]:
        # Helper to compare. Prerelease empty means a full release, which is higher than a prerelease.
        # So we include a boolean indicating if it is a release version (True) or prerelease (False).
        is_release = self.prerelease == ""
        return (self.major, self.minor, self.patch, is_release, self.prerelease)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Version):
            if isinstance(other, str):
                other = Version(other)
            else:
                return False
        return self._as_tuple() == other._as_tuple()

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: Union["Version", str]) -> bool:
        if isinstance(other, str):
            other = Version(other)
        return self._as_tuple() < other._as_tuple()

    def __le__(self, other: Union["Version", str]) -> bool:
        if isinstance(other, str):
            other = Version(other)
        return self._as_tuple() <= other._as_tuple()

    def __gt__(self, other: Union["Version", str]) -> bool:
        if isinstance(other, str):
            other = Version(other)
        return self._as_tuple() > other._as_tuple()

    def __ge__(self, other: Union["Version", str]) -> bool:
        if isinstance(other, str):
            other = Version(other)
        return self._as_tuple() >= other._as_tuple()

    def __str__(self) -> str:
        if self.prerelease:
            return f"{self.major}.{self.minor}.{self.patch}-{self.prerelease}"
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self) -> str:
        return f"Version('{self.raw}')"


def is_compatible(version_expr: str, core_version: str) -> bool:
    """
    Check if a given core version meets the semver compatibility expression.
    Supports:
      - Wildcard '*'
      - Carat range '^1.6.0' (>= 1.6.0 and < 2.0.0, or for 0.x >= 0.5.0 and < 0.6.0)
      - Operators: >=, <=, >, <, ==, !=
      - Exact match (e.g. '1.6.0')
    """
    if not version_expr or version_expr.strip() == "*":
        return True

    expr = version_expr.strip()
    core_ver = Version(core_version)

    # Handle caret (^) range
    if expr.startswith("^"):
        req_ver_str = expr[1:].strip()
        req_ver = Version(req_ver_str)
        if req_ver.major > 0:
            # ^1.6.0 => >= 1.6.0 and < 2.0.0
            upper_limit = Version(f"{req_ver.major + 1}.0.0")
            return req_ver <= core_ver < upper_limit
        elif req_ver.minor > 0:
            # ^0.5.0 => >= 0.5.0 and < 0.6.0
            upper_limit = Version(f"0.{req_ver.minor + 1}.0")
            return req_ver <= core_ver < upper_limit
        else:
            # ^0.0.5 => >= 0.0.5 and < 0.0.6
            upper_limit = Version(f"0.0.{req_ver.patch + 1}")
            return req_ver <= core_ver < upper_limit

    # Handle operators
    operators = [">=", "<=", ">", "<", "==", "!="]
    op = None
    for o in operators:
        if expr.startswith(o):
            op = o
            req_ver_str = expr[len(o):].strip()
            break
    else:
        req_ver_str = expr
        op = "=="

    req_ver = Version(req_ver_str)

    if op == ">=":
        return core_ver >= req_ver
    elif op == "<=":
        return core_ver <= req_ver
    elif op == ">":
        return core_ver > req_ver
    elif op == "<":
        return core_ver < req_ver
    elif op == "==":
        return core_ver == req_ver
    elif op == "!=":
        return core_ver != req_ver

    return False


class VersionNegotiator:
    """
    Handles SDK/client version negotiation protocols.
    """

    def negotiate(self, client_version_expr: str, server_versions: List[str]) -> str:
        """
        Negotiate the best (highest) compatible version from the list of server-supported
        versions that satisfies the client version requirements expression.

        Raises VersionMismatchError if no compatible version is found.
        """
        compatible_versions = []
        for sv in server_versions:
            if is_compatible(client_version_expr, sv):
                compatible_versions.append(Version(sv))

        if not compatible_versions:
            raise VersionMismatchError(
                f"No compatible version found matching requirement '{client_version_expr}' "
                f"among server versions: {server_versions}"
            )

        # Return the highest compatible version
        best_version = max(compatible_versions)
        return str(best_version)

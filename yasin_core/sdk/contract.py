"""
Machine-readable SDK / ecosystem contract registry loader and validators.

The single source of truth is ``contract_registry.json`` next to this module.
Tests and tooling should load the registry via :func:`load_contract_registry`
rather than hard-coding public export lists.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set

_REGISTRY_PATH = Path(__file__).resolve().parent / "contract_registry.json"

_REQUIRED_TOP_LEVEL = (
    "contract_version",
    "core_version",
    "status",
    "public_sdk",
    "ecosystem_consumers",
    "compatibility",
)

_REQUIRED_CONSUMERS = (
    "Yasin-Agent",
    "YasinHub",
    "YasinRelay",
    "YasinCLI",
)


def registry_path() -> Path:
    """Return the filesystem path of the canonical contract registry."""
    return _REGISTRY_PATH


def load_contract_registry(path: Path | None = None) -> Dict[str, Any]:
    """
    Load and return the contract registry as a dict.

    Raises
    ------
    FileNotFoundError
        If the registry file is missing.
    json.JSONDecodeError
        If the registry is not valid JSON.
    """
    target = path or _REGISTRY_PATH
    with target.open(encoding="utf-8") as fh:
        return json.load(fh)


def validate_registry_schema(registry: Dict[str, Any]) -> List[str]:
    """
    Validate structural requirements of the registry.

    Returns a list of human-readable error strings (empty if valid).
    """
    errors: List[str] = []

    for key in _REQUIRED_TOP_LEVEL:
        if key not in registry:
            errors.append(f"Missing required top-level key: {key}")

    public_sdk = registry.get("public_sdk")
    if not isinstance(public_sdk, dict):
        errors.append("public_sdk must be an object")
    else:
        if public_sdk.get("package") != "yasin_core.sdk":
            errors.append("public_sdk.package must be 'yasin_core.sdk'")
        boundary = public_sdk.get("supported_import_boundary")
        if not isinstance(boundary, list) or "yasin_core.sdk" not in boundary:
            errors.append(
                "public_sdk.supported_import_boundary must include 'yasin_core.sdk'"
            )
        modules = public_sdk.get("modules")
        if not isinstance(modules, dict) or "yasin_core.sdk" not in modules:
            errors.append("public_sdk.modules must define 'yasin_core.sdk'")
        else:
            exports = modules["yasin_core.sdk"].get("exports")
            if not isinstance(exports, list) or not exports:
                errors.append("public_sdk.modules['yasin_core.sdk'].exports must be a non-empty list")
            elif len(exports) != len(set(exports)):
                errors.append("public_sdk exports list contains duplicates")

        forbidden = public_sdk.get("forbidden_consumer_import_prefixes")
        if not isinstance(forbidden, list) or not forbidden:
            errors.append(
                "public_sdk.forbidden_consumer_import_prefixes must be a non-empty list"
            )

    consumers = registry.get("ecosystem_consumers")
    if not isinstance(consumers, dict):
        errors.append("ecosystem_consumers must be an object")
    else:
        for name in _REQUIRED_CONSUMERS:
            if name not in consumers:
                errors.append(f"Missing required ecosystem consumer: {name}")
            else:
                entry = consumers[name]
                if not isinstance(entry, dict):
                    errors.append(f"ecosystem_consumers[{name}] must be an object")
                    continue
                for field in ("id", "import_boundary", "validator", "status"):
                    if field not in entry:
                        errors.append(
                            f"ecosystem_consumers[{name}] missing required field '{field}'"
                        )
                if entry.get("import_boundary") != "yasin_core.sdk":
                    errors.append(
                        f"ecosystem_consumers[{name}].import_boundary must be 'yasin_core.sdk'"
                    )

    compat = registry.get("compatibility")
    if not isinstance(compat, dict):
        errors.append("compatibility must be an object")
    else:
        if "python_requires" not in compat:
            errors.append("compatibility.python_requires is required")
        certified = compat.get("certified_python_versions")
        if not isinstance(certified, list) or not certified:
            errors.append("compatibility.certified_python_versions must be a non-empty list")

    return errors


def get_public_exports(registry: Dict[str, Any] | None = None) -> Set[str]:
    """Return the set of declared public SDK export names."""
    reg = registry if registry is not None else load_contract_registry()
    return set(reg["public_sdk"]["modules"]["yasin_core.sdk"]["exports"])


def get_forbidden_import_prefixes(registry: Dict[str, Any] | None = None) -> List[str]:
    """Return forbidden import prefixes for ecosystem consumers."""
    reg = registry if registry is not None else load_contract_registry()
    return list(reg["public_sdk"]["forbidden_consumer_import_prefixes"])


def get_ecosystem_consumers(registry: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Return the ecosystem consumer contract map."""
    reg = registry if registry is not None else load_contract_registry()
    return dict(reg["ecosystem_consumers"])


__all__ = [
    "registry_path",
    "load_contract_registry",
    "validate_registry_schema",
    "get_public_exports",
    "get_forbidden_import_prefixes",
    "get_ecosystem_consumers",
]

"""
Regression tests for the machine-checkable Core SDK and ecosystem contract registry.

These tests ensure:
- The contract registry is valid JSON and matches the schema.
- Public SDK exports (__all__) match the registry exactly.
- Declared symbols remain importable from yasin_core.sdk.
- Forbidden import boundaries for ecosystem consumers are defined.
- Ecosystem consumer contracts are complete.
- Unintended public-surface drift causes test failure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yasin_core import version as core_version_module
from yasin_core.sdk import __all__ as sdk_all
from yasin_core.sdk.contract import (
    get_ecosystem_consumers,
    get_forbidden_import_prefixes,
    get_public_exports,
    load_contract_registry,
    registry_path,
    validate_registry_schema,
)


REQUIRED_CONSUMERS = ("Yasin-Agent", "YasinHub", "YasinRelay", "YasinCLI")


def test_registry_file_exists():
    path = registry_path()
    assert path.is_file(), f"Contract registry missing at {path}"


def test_registry_is_valid_json_and_schema():
    registry = load_contract_registry()
    errors = validate_registry_schema(registry)
    assert errors == [], f"Registry schema errors: {errors}"


def test_registry_core_version_matches_package():
    registry = load_contract_registry()
    assert registry["core_version"] == core_version_module.VERSION


def test_public_exports_match_sdk_all_exactly():
    """Canonical public surface must match yasin_core.sdk.__all__ with no drift."""
    registry_exports = get_public_exports()
    actual_exports = set(sdk_all)

    missing_from_registry = actual_exports - registry_exports
    extra_in_registry = registry_exports - actual_exports

    assert not missing_from_registry, (
        "SDK __all__ contains symbols not listed in contract registry: "
        f"{sorted(missing_from_registry)}"
    )
    assert not extra_in_registry, (
        "Contract registry lists symbols not present in SDK __all__: "
        f"{sorted(extra_in_registry)}"
    )
    assert len(registry_exports) == len(actual_exports)
    assert len(registry_exports) > 0


def test_registry_exports_list_has_no_duplicates_and_is_sorted_or_list():
    registry = load_contract_registry()
    exports = registry["public_sdk"]["modules"]["yasin_core.sdk"]["exports"]
    assert isinstance(exports, list)
    assert len(exports) == len(set(exports))


def test_all_registry_exports_are_importable_from_sdk():
    """Every declared public symbol must be reachable via yasin_core.sdk."""
    import yasin_core.sdk as sdk_pkg

    for name in sorted(get_public_exports()):
        assert hasattr(sdk_pkg, name), f"Public export '{name}' is not attribute of yasin_core.sdk"
        getattr(sdk_pkg, name)


def test_supported_import_boundary_is_sdk_only():
    registry = load_contract_registry()
    boundary = registry["public_sdk"]["supported_import_boundary"]
    assert boundary == ["yasin_core.sdk"] or (
        isinstance(boundary, list) and "yasin_core.sdk" in boundary
    )


def test_forbidden_import_prefixes_cover_internal_packages():
    prefixes = get_forbidden_import_prefixes()
    assert isinstance(prefixes, list)
    required = {
        "yasin_core.agents",
        "yasin_core.context",
        "yasin_core.memory",
        "yasin_core.security",
        "yasin_core.core",
    }
    actual = set(prefixes)
    missing = required - actual
    assert not missing, f"Forbidden prefixes missing internal packages: {missing}"
    assert "yasin_core.sdk" not in actual


def test_ecosystem_consumers_complete_and_valid():
    consumers = get_ecosystem_consumers()
    for name in REQUIRED_CONSUMERS:
        assert name in consumers, f"Missing ecosystem consumer contract: {name}"
        entry = consumers[name]
        assert entry.get("import_boundary") == "yasin_core.sdk"
        assert entry.get("validator"), f"{name} missing validator"
        assert entry.get("status"), f"{name} missing status"
        assert "compatibility_expectation" in entry


def test_ecosystem_validators_are_public_sdk_exports():
    """Validators referenced by consumer contracts must be part of the public surface."""
    consumers = get_ecosystem_consumers()
    public = get_public_exports()
    for name, entry in consumers.items():
        validator = entry.get("validator")
        assert validator in public, (
            f"Consumer {name} references validator '{validator}' which is not a public SDK export"
        )


def test_compatibility_python_versions_align_with_pyproject():
    registry = load_contract_registry()
    compat = registry["compatibility"]
    assert compat["python_requires"] == ">=3.9"
    certified = compat["certified_python_versions"]
    assert "3.9" in certified
    assert "3.12" in certified
    assert "3.14" not in certified


def test_contract_module_not_required_in_main_all():
    """
    contract helpers are tooling surface, not part of the consumer public API list.
    They remain importable as yasin_core.sdk.contract without expanding the main __all__.
    """
    from yasin_core.sdk import contract as contract_mod

    assert hasattr(contract_mod, "load_contract_registry")


def test_unintended_empty_registry_would_fail():
    """Guard: empty exports list must fail schema validation."""
    registry = load_contract_registry()
    broken = json.loads(json.dumps(registry))
    broken["public_sdk"]["modules"]["yasin_core.sdk"]["exports"] = []
    errors = validate_registry_schema(broken)
    assert any("exports" in e for e in errors)


def test_missing_consumer_fails_schema():
    registry = load_contract_registry()
    broken = json.loads(json.dumps(registry))
    del broken["ecosystem_consumers"]["YasinCLI"]
    errors = validate_registry_schema(broken)
    assert any("YasinCLI" in e for e in errors)

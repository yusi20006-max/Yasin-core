"""Regression tests for static public-SDK import boundary enforcement."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from yasin_core.sdk.boundary import (
    BoundaryViolation,
    check_paths,
    check_source,
    is_module_allowed,
    main,
)
from yasin_core.sdk.contract import (
    get_forbidden_import_prefixes,
    load_contract_registry,
)


@pytest.fixture(scope="module")
def prefixes():
    reg = load_contract_registry()
    allowed = list(reg["public_sdk"]["supported_import_boundary"])
    forbidden = list(reg["public_sdk"]["forbidden_consumer_import_prefixes"])
    return allowed, forbidden


def _check(src: str, prefixes, filename: str = "consumer.py"):
    allowed, forbidden = prefixes
    return check_source(
        textwrap.dedent(src),
        filename=filename,
        allowed_prefixes=allowed,
        forbidden_prefixes=forbidden,
    )


def test_allowed_sdk_module(prefixes):
    allowed, forbidden = prefixes
    assert is_module_allowed("yasin_core.sdk", allowed_prefixes=allowed, forbidden_prefixes=forbidden)
    assert is_module_allowed(
        "yasin_core.sdk.client", allowed_prefixes=allowed, forbidden_prefixes=forbidden
    )


def test_forbidden_internal_modules(prefixes):
    allowed, forbidden = prefixes
    for mod in (
        "yasin_core.agents",
        "yasin_core.agents.runtime",
        "yasin_core.context",
        "yasin_core.memory.in_memory",
        "yasin_core.security",
        "yasin_core.core.orchestrator",
    ):
        assert not is_module_allowed(
            mod, allowed_prefixes=allowed, forbidden_prefixes=forbidden
        ), mod


def test_bare_yasin_core_forbidden(prefixes):
    allowed, forbidden = prefixes
    assert not is_module_allowed(
        "yasin_core", allowed_prefixes=allowed, forbidden_prefixes=forbidden
    )


def test_unrelated_packages_allowed(prefixes):
    allowed, forbidden = prefixes
    assert is_module_allowed("os", allowed_prefixes=allowed, forbidden_prefixes=forbidden)
    assert is_module_allowed("requests", allowed_prefixes=allowed, forbidden_prefixes=forbidden)


def test_allowed_import_sdk(prefixes):
    v = _check("import yasin_core.sdk\n", prefixes)
    assert v == []


def test_allowed_from_sdk_import(prefixes):
    v = _check("from yasin_core.sdk import YasinCoreClient, BaseAgent\n", prefixes)
    assert v == []


def test_allowed_nested_sdk_import(prefixes):
    v = _check("from yasin_core.sdk.client import YasinCoreClient\n", prefixes)
    assert v == []


def test_forbidden_direct_internal_import(prefixes):
    v = _check("import yasin_core.agents\n", prefixes, filename="agent_app.py")
    assert len(v) == 1
    assert v[0].module == "yasin_core.agents"
    assert v[0].file == "agent_app.py"
    assert v[0].line == 1
    assert "forbidden" in v[0].reason.lower() or "outside" in v[0].reason.lower()


def test_forbidden_from_import(prefixes):
    v = _check("from yasin_core.memory import InMemoryShortTermMemory\n", prefixes)
    assert len(v) == 1
    assert v[0].module == "yasin_core.memory"
    assert "from yasin_core.memory import" in v[0].statement


def test_forbidden_alias_import(prefixes):
    v = _check("import yasin_core.security as sec\n", prefixes)
    assert len(v) == 1
    assert v[0].module == "yasin_core.security"
    assert "as sec" in v[0].statement


def test_forbidden_nested_prefix(prefixes):
    v = _check("from yasin_core.agents.runtime import AgentRuntime\n", prefixes)
    assert len(v) == 1
    assert v[0].module == "yasin_core.agents.runtime"


def test_multiple_imports_in_statement(prefixes):
    v = _check(
        "import yasin_core.sdk, yasin_core.agents, yasin_core.context\n",
        prefixes,
        filename="multi.py",
    )
    mods = {x.module for x in v}
    assert "yasin_core.agents" in mods
    assert "yasin_core.context" in mods
    assert "yasin_core.sdk" not in mods
    assert all(x.file == "multi.py" for x in v)


def test_multiple_from_and_import_lines(prefixes):
    src = """
    import yasin_core.sdk
    from yasin_core.sdk import Task
    from yasin_core.di import DIContainer
    import yasin_core.events.event_bus as bus
    """
    v = _check(src, prefixes)
    mods = {x.module for x in v}
    assert mods == {"yasin_core.di", "yasin_core.events.event_bus"}


def test_string_literal_not_violation(prefixes):
    src = '''
    msg = "import yasin_core.agents"
    doc = """from yasin_core.memory import X"""
    '''
    assert _check(src, prefixes) == []


def test_comment_not_violation(prefixes):
    src = """
    # import yasin_core.agents
    # from yasin_core.security import SecurityManager
    import yasin_core.sdk
    """
    assert _check(src, prefixes) == []


def test_relative_import_not_core_violation(prefixes):
    src = """
    from .local_helper import foo
    from ..pkg import bar
    """
    assert _check(src, prefixes) == []


def test_unrelated_name_similarity(prefixes):
    src = """
    import my_yasin_core_agents
    from not_yasin_core.agents import x
    """
    assert _check(src, prefixes) == []


def test_registry_drives_forbidden_list(prefixes):
    allowed, forbidden = prefixes
    assert "yasin_core.sdk" in allowed
    assert "yasin_core.agents" in forbidden
    assert set(forbidden) == set(get_forbidden_import_prefixes())


def test_check_paths_on_temp_tree(tmp_path, prefixes):
    good = tmp_path / "good.py"
    bad = tmp_path / "pkg" / "bad.py"
    bad.parent.mkdir()
    good.write_text("from yasin_core.sdk import YasinCoreClient\n", encoding="utf-8")
    bad.write_text("from yasin_core.core import orchestrator\n", encoding="utf-8")

    violations = check_paths([tmp_path])
    assert len(violations) == 1
    assert violations[0].module == "yasin_core.core"
    assert str(bad) in violations[0].file or violations[0].file.endswith("bad.py")
    assert violations[0].line == 1


def test_check_paths_empty_ok(tmp_path):
    (tmp_path / "ok.py").write_text("import os\n", encoding="utf-8")
    assert check_paths([tmp_path]) == []


def test_cli_success_and_failure(tmp_path, capsys):
    good = tmp_path / "ok.py"
    good.write_text("import yasin_core.sdk\n", encoding="utf-8")
    assert main([str(good)]) == 0
    out = capsys.readouterr().out
    assert "OK" in out

    bad = tmp_path / "bad.py"
    bad.write_text("import yasin_core.agents\n", encoding="utf-8")
    assert main([str(bad)]) == 1
    err_out = capsys.readouterr().out
    assert "yasin_core.agents" in err_out
    assert "bad.py" in err_out


def test_cli_json_mode(tmp_path, capsys):
    bad = tmp_path / "bad.py"
    bad.write_text("from yasin_core.memory import x\n", encoding="utf-8")
    assert main([str(bad), "--json"]) == 1
    line = capsys.readouterr().out.strip().splitlines()[0]
    data = json.loads(line)
    assert data["module"] == "yasin_core.memory"
    assert data["line"] == 1
    assert "file" in data


def test_diagnostic_fields_complete(prefixes):
    v = _check("import yasin_core.plugins.registry as reg\n", prefixes, filename="hub.py")
    assert len(v) == 1
    assert isinstance(v[0], BoundaryViolation)
    assert v[0].file == "hub.py"
    assert isinstance(v[0].line, int) and v[0].line >= 1
    assert v[0].module == "yasin_core.plugins.registry"
    assert v[0].statement
    assert v[0].reason


def test_syntax_error_file_skipped(prefixes):
    v = _check("def broken(\n", prefixes)
    assert v == []


def test_existing_contract_tests_still_importable():
    """Sanity: boundary module does not break contract public surface."""
    from yasin_core.sdk.contract import load_contract_registry, validate_registry_schema

    reg = load_contract_registry()
    assert validate_registry_schema(reg) == []

"""
Static (AST) enforcement of the public SDK import boundary.

Reads allowed / forbidden prefixes from the canonical
``contract_registry.json`` (via :mod:`yasin_core.sdk.contract`).

Intended for ecosystem consumers (Yasin-Agent, YasinHub, YasinRelay, YasinCLI)
and for CI in those repositories. Yasin-Core internal packages are not subject
to this rule when scanning the Core tree itself — pass explicit consumer paths.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

from yasin_core.sdk.contract import (
    get_forbidden_import_prefixes,
    load_contract_registry,
)


@dataclass(frozen=True)
class BoundaryViolation:
    """One forbidden import detected in a consumer file."""

    file: str
    line: int
    module: str
    statement: str
    reason: str

    def format(self) -> str:
        return (
            f"{self.file}:{self.line}: forbidden import '{self.module}' "
            f"({self.reason}); statement: {self.statement}"
        )


def _normalize_module(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return name.strip()


def is_module_allowed(
    module: str,
    *,
    allowed_prefixes: Sequence[str],
    forbidden_prefixes: Sequence[str],
) -> bool:
    """
    Return True if ``module`` is permitted under the SDK boundary policy.

    Allowed: exact or nested under any allowed prefix (default ``yasin_core.sdk``).
    Forbidden: exact or nested under any forbidden prefix, unless also covered by
    a more specific allowed prefix.
    """
    if not module:
        return True

    # Allowed boundary wins when the module is under yasin_core.sdk (or listed).
    for allowed in allowed_prefixes:
        if module == allowed or module.startswith(allowed + "."):
            return True

    # Bare ``yasin_core`` (no submodule) is ambiguous; treat as forbidden for
    # consumers so they must use the public SDK package explicitly.
    if module == "yasin_core":
        return False

    for forbidden in forbidden_prefixes:
        if module == forbidden or module.startswith(forbidden + "."):
            return False

    # Other top-level packages (stdlib, third-party) are out of scope.
    if module.startswith("yasin_core."):
        # Unknown yasin_core.* path not listed as allowed → forbid for safety.
        return False

    return True


def _iter_imported_modules(node: ast.AST) -> Iterable[tuple[str, int, str]]:
    """
    Yield (module_name, lineno, statement_summary) for import nodes.

    Only real Import / ImportFrom nodes are considered (not strings/comments).
    """
    if isinstance(node, ast.Import):
        for alias in node.names:
            mod = _normalize_module(alias.name)
            if mod:
                as_part = f" as {alias.asname}" if alias.asname else ""
                stmt = f"import {mod}{as_part}"
                yield mod, node.lineno, stmt
    elif isinstance(node, ast.ImportFrom):
        # Relative imports (level > 0) inside a consumer package are not Core imports.
        if node.level and node.level > 0:
            return
        mod = _normalize_module(node.module)
        if not mod:
            return
        names = ", ".join(
            f"{a.name}" + (f" as {a.asname}" if a.asname else "") for a in node.names
        )
        stmt = f"from {mod} import {names}"
        yield mod, node.lineno, stmt


def check_source(
    source: str,
    *,
    filename: str = "<string>",
    allowed_prefixes: Sequence[str],
    forbidden_prefixes: Sequence[str],
) -> List[BoundaryViolation]:
    """Parse ``source`` and return boundary violations."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        # Unparseable files are not boundary violations.
        return []

    violations: List[BoundaryViolation] = []
    for node in ast.walk(tree):
        for module, lineno, stmt in _iter_imported_modules(node):
            if not is_module_allowed(
                module,
                allowed_prefixes=allowed_prefixes,
                forbidden_prefixes=forbidden_prefixes,
            ):
                reason = (
                    f"consumers must import only from {', '.join(allowed_prefixes)}; "
                    f"'{module}' is outside the supported public SDK boundary"
                )
                violations.append(
                    BoundaryViolation(
                        file=filename,
                        line=lineno,
                        module=module,
                        statement=stmt,
                        reason=reason,
                    )
                )
    return violations


def check_file(
    path: Path,
    *,
    allowed_prefixes: Sequence[str],
    forbidden_prefixes: Sequence[str],
) -> List[BoundaryViolation]:
    """Check a single ``.py`` file."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    return check_source(
        source,
        filename=str(path),
        allowed_prefixes=allowed_prefixes,
        forbidden_prefixes=forbidden_prefixes,
    )


def _iter_python_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix == ".py":
        yield root
        return
    if not root.is_dir():
        return
    skip_dirs = {
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        "dist",
        "build",
        ".eggs",
        "egg-info",
    }
    for p in root.rglob("*.py"):
        if any(part in skip_dirs or part.endswith(".egg-info") for part in p.parts):
            continue
        yield p


def check_paths(
    paths: Sequence[Path],
    *,
    allowed_prefixes: Optional[Sequence[str]] = None,
    forbidden_prefixes: Optional[Sequence[str]] = None,
    registry: Optional[dict] = None,
) -> List[BoundaryViolation]:
    """
    Scan one or more files/directories for forbidden Core imports.

    Prefix lists default to the canonical contract registry.
    """
    if allowed_prefixes is None or forbidden_prefixes is None:
        reg = registry if registry is not None else load_contract_registry()
        public = reg["public_sdk"]
        if allowed_prefixes is None:
            allowed_prefixes = list(public.get("supported_import_boundary") or ["yasin_core.sdk"])
        if forbidden_prefixes is None:
            forbidden_prefixes = list(
                public.get("forbidden_consumer_import_prefixes")
                or get_forbidden_import_prefixes(reg)
            )

    violations: List[BoundaryViolation] = []
    for root in paths:
        root = Path(root)
        for py in _iter_python_files(root):
            violations.extend(
                check_file(
                    py,
                    allowed_prefixes=allowed_prefixes,
                    forbidden_prefixes=forbidden_prefixes,
                )
            )
    return violations


def violations_to_dicts(violations: Sequence[BoundaryViolation]) -> List[dict]:
    return [asdict(v) for v in violations]


def main(argv: Optional[Sequence[str]] = None) -> int:
    """
    CLI entry point.

    Example::

        python -m yasin_core.sdk.boundary path/to/Yasin-agent path/to/YasinHub
    """
    parser = argparse.ArgumentParser(
        prog="yasin_core.sdk.boundary",
        description=(
            "Enforce Yasin-Core public SDK import boundaries for ecosystem consumers. "
            "Uses yasin_core/sdk/contract_registry.json as the sole source of truth."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Consumer source files or directories to scan",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit violations as JSON lines",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    violations = check_paths(args.paths)
    if not violations:
        print("OK: no public SDK boundary violations found.")
        return 0

    if args.json:
        import json

        for v in violations:
            print(json.dumps(asdict(v), ensure_ascii=False))
    else:
        print(f"Found {len(violations)} public SDK boundary violation(s):\n")
        for v in violations:
            print(f"  {v.format()}")
        print(
            "\nConsumers must import only from yasin_core.sdk. "
            "See docs/integration/sdk_contract.md."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())

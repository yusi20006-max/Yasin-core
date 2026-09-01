# Yasin-Core Public SDK & Ecosystem Contract

**Canonical source of truth:** `yasin_core/sdk/contract_registry.json`

This document describes the machine-checkable contract for the public SDK surface and the supported boundaries for ecosystem consumers. Implementation, tests, and this documentation are kept in sync.

## Goals

- One canonical definition of the public Yasin-Core SDK surface
- Machine-readable registry validated by automated tests
- Explicit compatibility / import boundaries for Yasin-Agent, YasinHub, YasinRelay, and YasinCLI
- Regression protection against accidental public-export or boundary drift
- No breaking API changes required to adopt the contract

## Canonical public SDK surface

Consumers **must** import from:

```python
from yasin_core.sdk import YasinCoreClient, BaseAgent, Task, ...
```

The full list of public symbols is the `exports` array under:

`public_sdk.modules["yasin_core.sdk"].exports`

in `contract_registry.json`. That list is required to match `yasin_core.sdk.__all__` exactly; see `tests/test_sdk_contract.py`.

### Supported import boundary

| Allowed | Forbidden for ecosystem consumers |
| --- | --- |
| `yasin_core.sdk` | `yasin_core.agents`, `yasin_core.context`, `yasin_core.memory`, `yasin_core.security`, `yasin_core.core`, and other internal packages listed in `forbidden_consumer_import_prefixes` |

Direct imports of Core internals by Yasin-Agent / YasinHub / YasinRelay / YasinCLI are **outside the supported contract**.

## Ecosystem consumers

| Consumer | Validator (public SDK) | Import boundary |
| --- | --- | --- |
| Yasin-Agent | `AgentCompatibilityValidator` | `yasin_core.sdk` |
| YasinHub | `HubCompatibilityValidator` | `yasin_core.sdk` |
| YasinRelay | `RelayCompatibilityValidator` | `yasin_core.sdk` |
| YasinCLI | `CLICompatibilityValidator` | `yasin_core.sdk` |

Each consumer entry in the registry records role, expected compatibility constraint, and status. Runtime validators live in the compatibility framework and are re-exported via the public SDK.

Related narrative docs:

- `docs/architecture/BOUNDARIES.md`
- `docs/integration/yasin_agent_contract.md`

## Contract versioning

| Field | Meaning |
| --- | --- |
| `contract_version` | Version of the **registry schema / contract document** (independent semver) |
| `core_version` | Must match `yasin_core.version.VERSION` |
| `status` | e.g. `stable` |

When the public export set changes in a compatible way, update:

1. `yasin_core/sdk/__init__.py` (`__all__`)
2. `yasin_core/sdk/contract_registry.json` (exports list and `core_version` if needed)
3. Tests / this documentation if behavior or boundaries change

Breaking removals of public symbols require an explicit major/compatibility decision and must not be silent.

## How the registry is validated

```bash
pytest tests/test_sdk_contract.py -v
```

Coverage includes:

- Registry JSON + schema validity
- `core_version` alignment with package version
- Exact match between registry exports and `yasin_core.sdk.__all__`
- Importability of every declared public symbol
- Forbidden internal import prefixes
- Completeness of the four ecosystem consumer contracts
- Python certified version list alignment with project policy

Tooling can also load the registry programmatically:

```python
from yasin_core.sdk.contract import (
    load_contract_registry,
    validate_registry_schema,
    get_public_exports,
)
```

The `yasin_core.sdk.contract` module is a **tooling / validation** surface. It is intentionally not required on the main consumer `__all__` list so the runtime public API remains focused.

## Compatibility & Python support

See `docs/PHASE6_PYTHON_MATRIX.md` and the `compatibility` section of the registry:

- `python_requires`: `>=3.9`
- Certified: 3.9–3.13
- Primary CI: 3.9, 3.12

## Design constraints (Issue #101)

- No redesign of current Yasin-Core architecture
- Additive, non-breaking changes only
- Single source of truth (this registry), not duplicated competing manifests
- Existing public behavior preserved

## Import boundary enforcement

Policy in the registry is enforced by a **static AST checker** (no runtime imports of consumer code):

```bash
python -m yasin_core.sdk.boundary path/to/consumer/src
```

Implementation: `yasin_core/sdk/boundary.py`.

### What is detected

- `import yasin_core.<internal>`
- `import yasin_core.<internal> as alias`
- `from yasin_core.<internal> import ...`
- nested modules under any `forbidden_consumer_import_prefixes` entry
- multiple names in a single `import` statement

### What is allowed

- `import yasin_core.sdk` and `from yasin_core.sdk import ...`
- nested modules under the supported boundary (e.g. `yasin_core.sdk.client`)
- stdlib / third-party packages
- relative imports inside the consumer package

Strings and comments are ignored (AST-only).

### Diagnostics

Each violation reports **file**, **line**, **module**, **statement**, and **reason**.

JSON mode for CI tooling:

```bash
python -m yasin_core.sdk.boundary --json path/to/src
```

Exit code `1` when any violation is found; `0` when clean.

### Integrating ecosystem repositories

Yasin-Agent, YasinHub, YasinRelay, and YasinCLI should:

1. Depend on a Yasin-Core version that includes this checker.
2. Add a CI step, for example:

```yaml
- run: pip install -e ../Yasin-core
- run: python -m yasin_core.sdk.boundary src/
```

3. Fix any reported imports by switching to `yasin_core.sdk`.

This repository does not modify those external codebases in-place; enforcement is reusable and intended to run **in each consumer's CI** against that consumer's source tree.

### Changing the boundary

Update **only** `yasin_core/sdk/contract_registry.json`, then ensure:

- `tests/test_sdk_contract.py` still passes (export / schema drift)
- `tests/test_sdk_boundary.py` still passes (enforcement)
- documentation reflects the new prefixes

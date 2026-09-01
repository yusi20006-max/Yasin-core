# Phase 6 Python Compatibility Matrix

Yasin-Core declares `requires-python = ">=3.9"` in `pyproject.toml`.

**Certified runtime versions** (authoritative, also recorded in `yasin_core/sdk/contract_registry.json`):

- 3.9
- 3.10
- 3.11
- 3.12
- 3.13

CI:

- Primary workflow (`.github/workflows/ci.yml`): 3.9, 3.12
- Extended matrix (`.github/workflows/python-matrix.yml`): all certified versions above

Python 3.14 is **not** certified. The matrix intentionally stays within the versions the project has validated and does not expand beyond `requires-python` without explicit certification.

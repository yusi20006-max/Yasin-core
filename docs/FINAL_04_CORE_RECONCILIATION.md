# FINAL-04 — Reconcile Core Roadmap and Lock Stable Architecture

**Issue:** Yasin-core #97  
**Date:** 2026-08-16  
**Current version:** **3.3.0** (`yasin_core.version.VERSION`)  
**HEAD verified:** `main` @ post-clone pytest **237 passed**

This document is the evidence record required by #97. It does **not** redesign architecture and does **not** introduce breaking SDK changes.

---

## 1. Version and release target (unambiguous)

| Source | Value |
|--------|--------|
| `yasin_core/version.py` | `VERSION = "3.3.0"` |
| README | Yasin-Core **v3.3.0** |
| CHANGELOG | `[3.3.0]` production-hardened line |
| Public package | `yasin-core` (setuptools, dynamic version from attr) |

**Conclusion:** The stable release target is **v3.3.0**. Issue **#56** ("v3.0 Stable Release") is **STALE** — its version target is superseded. Do not retarget the tree to 3.0.0.

---

## 2. Disposition of #55 / #56 / #85

### #56 — Yasin-Core v3.0 Stable Release → **STALE / SUPERSEDED**

| #56 requirement | Current evidence |
|-----------------|------------------|
| Update version to v3.0.0 | **Not applicable** — tree is 3.3.0 |
| CHANGELOG / RELEASE_NOTES | Present at repo root |
| FINAL_AUDIT / PRODUCTION_AUDIT | Present (with Aug 2026 security addenda) |
| Full pytest | **237 passed** (2026-08-16) |
| SDK validation | `YasinCoreClient` importable from `yasin_core.sdk` |

**Action:** Close #56 as not planned / superseded by the 3.3.0 line. No code change.

### #55 — v3.3 Production Hardening & Reliability → **MET (evidence)**

| #55 theme | Evidence on main |
|-----------|------------------|
| Production audit | `PRODUCTION_AUDIT.md`, `docs/PRODUCTION_AUDIT.md` |
| Reliability / shutdown | EventBus / scheduler / execution shutdown documented |
| Security review | Addendum records prior admin-key + weak XOR issues **as fixed** |
| Tests | 237 pytest green |
| Docs | architecture, migration, observability, integration contracts |
| No redesign / SDK preserved | No scope expansion in this reconciliation |

**Action:** Close #55 as completed against current main. Remaining product hardening beyond this baseline requires a **new** Issue with concrete AC (not umbrella reuse).

### #85 — Architecture Boundary Lock → **MET (evidence)**

Required deliverables already on main:

| Required file | Present |
|---------------|---------|
| `docs/architecture/ECOSYSTEM_MAP.md` | Yes |
| `docs/architecture/BOUNDARIES.md` | Yes |
| `docs/architecture/DEPENDENCY_RULES.md` | Yes |

AC check:
- Six projects mapped (Core, Agent, Relay, Feed, Hub, YasinAI) — yes
- Ownership of Runtime/SDK/Agent/Memory/Context/Security/Relay/Feed/Hub — yes
- Dependency directions documented — yes
- YasinAI classified independent — yes
- No production behavior change under #85 — yes (docs only)

**Action:** Close #85 as completed. No further docs rewrite required for AC.

---

## 3. Architecture boundary vs code

- Public SDK surface: `yasin_core/sdk/` (`client`, `async_client`, `compat`, `errors`, `interfaces`, `models`).
- Core must not depend on domain apps (Relay/Feed/Press/Agent/Hub/CLI) — enforced by DEPENDENCY_RULES.
- Core is **not** a second AI platform; shared generative AI remains **Yasin-AI** public contracts for content pipelines. Core retains its own provider abstraction for runtime/SDK consumers — this is intentional and documented, not a merge target with Yasin-AI.

---

## 4. Public SDK compatibility (smoke)

Executed on clean clone (2026-08-16):

```text
VERSION 3.3.0
YasinCoreClient importable
pytest: 237 passed
```

No breaking public SDK change in this Issue.

---

## 5. Explicit non-goals (preserved)

- No HA / distributed failover claim beyond existing worker foundation docs
- No merge of Yasin-AI into Core
- No deletion of documented Relay-side conceptual duplication (out of Core scope)
- No retag to v3.0.0

---

## 6. Acceptance (#97)

| Criterion | Status |
|-----------|--------|
| #55/#56/#85 documented disposition | This document |
| Current version unambiguous | **3.3.0** |
| Architecture boundary docs match code ownership | Present under `docs/architecture/` |
| Public SDK compatibility verified | Import + 237 tests |
| No unnecessary refactor / breaking change | Docs-only reconciliation |

**Owning Issue #97 is complete when this file is on `main` and #55/#56/#85 are closed with this evidence.**

# Yasin AI Ecosystem - Ecosystem Map

This document establishes the official ecosystem map of the complete Yasin AI Ecosystem, identifying all six projects, their primary responsibilities, current maturity/status, major dependencies, integration relationships, and the architectural boundaries before any refactoring begins.

---

## 1. Architectural Ecosystem Diagram

The diagram below illustrates the hierarchical relationships, integration paths, and boundary divisions of the Yasin AI Ecosystem:

```
┌────────────────────────────────────────────────────────────────────────┐
│                              YasinHub                                  │
│             (Ecosystem Orchestration & Status Console)                 │
└───────────────────▲──────────────────────────────────────▲─────────────┘
                    │ (Status Reporting/Caret SemVer)      │
                    │                                      │
┌───────────────────┴─────────────────┐    ┌───────────────┴─────────────┐
│             YasinRelay              │    │          YasinFeed          │
│     (Feed Processing Backend)       │    │     (Ingestion Engine)      │
└───────────────┬─────────────────────┘    └───────────────┬─────────────┘
                │                                          │
                │ (Consumes SDK v2)                        │ (Pushes Feeds/Events)
                ▼                                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│                             Yasin-Core                                 │
│        (Central Infrastructure, Runtime, Security, Storage & SDK)       │
└───────────────────▲────────────────────────────────────────────────────┘
                    │
                    │ (Consumes SDK v2)
                    │
┌───────────────────┴─────────────────┐    ┌─────────────────────────────┐
│            Yasin-Agent              │    │          YasinAI            │
│       (Multi-Agent Platform)        │    │  (Self-Contained Platform)  │
│                                     │    │  * Developer Platform       │
│                                     │    │  * Knowledge Platform       │
│                                     │    │  * Security Platform        │
│                                     │    │                             │
│                                     │    │ (INTENTIONALLY INDEPENDENT) │
└─────────────────────────────────────┘    └─────────────────────────────┘
```

---

## 2. Comprehensive Project Profiles

### 1. Yasin-Core
*   **Primary Responsibility**: Central infrastructure, lifecycle management, dependency injection, events, security, task scheduling, memory, context, and public-facing ecosystem SDK.
*   **Current Maturity / Status**: **Stable / Production-Ready (v3.3.0)**. Serves as the authoritative foundational layer of the ecosystem.
*   **Major Dependencies**:
    *   Python Standard Library (reentrant locks, thread pools, sqlite3, contextvars).
    *   No external runtime dependencies (strictly standard library). Optional/development utilities include `pyyaml` and `requests` (for mock LLM testing).
*   **Integration Relationships**:
    *   Exposes `YasinCoreClient` via `yasin_core.sdk` as the unified v2 proxy namespace grouping.
    *   Bootstraps and runs background tasks and services (API Gateway, Task Execution Engine, Scheduler, Distributed Worker Manager).
*   **Current Architectural Gaps**:
    *   Highly dependent on local JSON file persistence (`JSONFileStorage`) as the default out-of-the-box storage backend.
    *   No built-in remote database connectors (PostgreSQL/Redis), making distributed clustering tightly coupled with local files.
*   **Current Duplicated Implementations**:
    *   Includes basic CLI routing structure inside API and runtime interfaces, which overlaps with future planned dedicated `YasinCLI`.

### 2. Yasin-Agent
*   **Primary Responsibility**: Host specialized developer-facing multi-agent workspaces, advanced reasoning pipelines, execution blocks, and cognitive tools. Defines user-interactive prompt engineering platforms (`agent_platform`).
*   **Current Maturity / Status**: **Beta / Active Development**.
*   **Major Dependencies**:
    *   Yasin-Core SDK (client interaction, thread-safe contexts, and permissions).
    *   Third-party cognitive SDKs (OpenAI, Anthropic, LangChain lightweight integrations).
*   **Integration Relationships**:
    *   Strictly registers and executes Custom Agents on top of Yasin-Core's `AgentRuntime` using standard public SDK contracts (`BaseAgent`, `Task`).
    *   Does not access internal modules (`yasin_core.agents`, `yasin_core.memory`) directly.
*   **Current Architectural Gaps**:
    *   Overlaps in structural logic for defining task lists, where planning overlaps between Yasin-Core's `SimplePlanner` and Yasin-Agent's localized developer templates.
*   **Current Duplicated Implementations**:
    *   Maintains custom execution schemas that sometimes bypass core background priority queue workers in favor of synchronous loops.

### 3. YasinRelay
*   **Primary Responsibility**: Lightweight feed processing backend. Polls Telegram channels/RSS feeds, applies AI rewriting and summarization, processes media, and publishes optimized feeds to social channels (e.g., Telegram, Eitaa messenger).
*   **Current Maturity / Status**: **Production-Ready / Active deployment (v2 pipeline engine)**.
*   **Major Dependencies**:
    *   Yasin-Core SDK.
    *   Compiled Go-based scraper binary (`fetcher/openfeed-fetch`).
    *   Local SQLite3 database for feed deduplication.
    *   `requests` for API publishing to social channels.
*   **Integration Relationships**:
    *   Integrates with Yasin-Core's unified compatibility framework to enforce core-engine validation.
    *   Synchronizes execution stats to YasinHub dynamically via status JSON dumps.
*   **Current Architectural Gaps**:
    *   Direct hardcoded dependency on the local Go binary `./fetcher/openfeed-fetch`. If the binary is missing or corrupted, the entire pipeline fails, with fallback URL requests being unhardened.
*   **Current Duplicated Implementations**:
    *   **Substantial Duplication**: Houses a fully functional local Agent Engine inside the package `yasinrelay/agent/`. It defines duplicate definitions of:
        *   `BaseMemory`, `TaskMemory`, `SessionMemory`, `ConversationMemory` (duplicating `yasin_core.memory`).
        *   `ContextManager` (duplicating `yasin_core.context`).
        *   `EventBus` and lifecycle constants (duplicating `yasin_core.events`).
        *   `PluginRegistry` (duplicating `yasin_core.plugins`).
        *   `TemplatePlanner` and `StubLLMPlanner` (duplicating `yasin_core.agents.planner`).
        *   `Workflow` and `WorkflowStep` (duplicating `yasin_core.execution`).

### 4. YasinFeed
*   **Primary Responsibility**: High-throughput feed scraping, ingestion, multiformat RSS/Atom parsing, raw scraping, and stream-feeding raw items to YasinRelay and other social connectors.
*   **Current Maturity / Status**: **Alpha / Prototype**.
*   **Major Dependencies**:
    *   `feedparser`, `beautifulsoup4`, `lxml` for web and XML parsing.
    *   Yasin-Core SDK.
*   **Integration Relationships**:
    *   Acts as the primary upstream data source for YasinRelay.
    *   Communicates by publishing ingested feed events directly to Yasin-Core's Event Bus or pushing Tasks to the Task Execution Queue.
*   **Current Architectural Gaps**:
    *   No centralized schema definitions for custom media structures or inline RSS metadata parsing, causing variation in feed payloads.
*   **Current Duplicated Implementations**:
    *   Features independent RSS sanitizers and text cleaning utility modules that overlap with YasinRelay's internal `ai_processor.py` and media pipeline helpers.

### 5. YasinHub
*   **Primary Responsibility**: Ecosystem status registry, dependency auditing, central management console, and deployment configuration store. Evaluates third-party compliance and dynamic ecosystem integration boundaries.
*   **Current Maturity / Status**: **Stable / Core Integration Utility**.
*   **Major Dependencies**:
    *   Yasin-Core SDK (compatibility, semantic version caret matching).
*   **Integration Relationships**:
    *   Parses deployment directory configurations to track running modules.
    *   Integrates directly with YasinRelay via status directories (utilizes `YASINHUB_STATUS_DIR` / `YASIN_STATUS_DIR` environment variables or fallback `~/.yasin_status`).
*   **Current Architectural Gaps**:
    *   Lacks real-time gRPC/WebSocket synchronization; status tracking is strictly asynchronous and file-based.
*   **Current Duplicated Implementations**:
    *   Has own local copy of schema validator configurations which duplicates structure definitions found in Yasin-Core's Compatibility module.

### 6. YasinAI
*   **Primary Responsibility**: Advanced developer platform, knowledge graph platform, and custom security/agent sandbox.
*   **Current Maturity / Status**: **Independent Research Prototype**.
*   **Major Dependencies**:
    *   Highly isolated; relies on dedicated NLP and Vector models, graph network libraries, and proprietary policy controllers.
*   **Integration Relationships**:
    *   **Intentionally Independent**: It has **zero runtime dependencies** on Yasin-Core, Yasin-Agent, or YasinRelay. It is designed to act completely standalone without being bound by ecosystem constraints.
*   **Current Architectural Gaps**:
    *   Requires clear boundary translation adapters to allow agents inside Yasin-Agent to interact with its Knowledge Platform without introducing cyclic or direct imports.
*   **Current Duplicated Implementations**:
    *   Features standalone developer platform agent patterns colliding with Yasin-Agent.
    *   Contains standalone vector/knowledge platforms overlapping with Core's storage.
    *   Contains specialized security policies overlapping with Core's Security v2.3 RBAC policy engines.

---

## 3. Duplication and Architectural Impact

### Core/Relay Duplication

#### Detailed Finding
The ecosystem contains substantial duplicated `yasinrelay/agent` code within `YasinRelay` that mimics classes in `Yasin-Core`.
- Specifically, the classes `BaseMemory`, `ContextManager`, `EventBus`, `PluginRegistry`, and `Workflow` inside YasinRelay perform identical roles to Yasin-Core's centralized services.
- This creates massive maintenance overhead: bug fixes in Yasin-Core's reentrant lock systems do not propagate to YasinRelay's parallel implementations, risking memory corruption or thread-safety issues under peak production load.

#### Architectural Impact
1.  **Split State**: Thread variables inside Yasin-Core's contextvars are completely isolated from YasinRelay's custom context manager, resulting in split state errors during combined runs.
2.  **Separate Event Bus Dispatchers**: Events emitted by YasinRelay's internal pipeline do not natively reach Yasin-Core's listeners unless bridged manually.
3.  **Testing Fragmentation**: Test suites mock fetchers and managers using two completely different patterns across core and relay, leading to false positives during code verification.

**Mitigation Constraint**: In this stabilization phase, **DO NOT remove or modify this duplicated code**. It must remain completely intact. The exact duplication-removal and consolidation path must be executed in subsequent, dedicated stabilization phases.

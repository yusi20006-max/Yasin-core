# Changelog

All notable changes to the **Yasin-Core** framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.0.0] - 2025-02-23

### Added
- **Official Agent Runtime Integration Layer (v3.0)**: Centralized and thread-safe registration, dynamic discovery via name and tag capability matching, execution queues, state persistence, context management, and security validation.
- **Migration & Compatibility Framework (v3.2)**: Independent Semantic Version parsing, caret range (`^`) and wildcard matching, dynamic API signature/inspection helpers, deprecation warnings with DeprecationManager, legacy API adapter, configuration schema/pathfinding and data migrators, and full ecosystem (Agent, CLI, Hub, Relay) validators.
- **Security & Permission Layer (v2.3)**: Centralized Access Control (RBAC), thread-safe custom exceptions, policy evaluation engine, asterisk masking and sensitive configuration validation, structural security event audit logging, and `@require_permission` runtime decorator.
- **AI Provider Abstraction Layer (v2.8)**: Modular providers (`MockProvider`, `LocalProvider`, and `OpenAICompatibleProvider`) with routing, fallback chaining, tokens/metrics tracking, and sensitive configuration masking.
- **Centralized Scheduler and Background Jobs (v2.6)**: 5-field dependency-free cron parsing helper, background thread jobs runner, job lifecycle tracking with Event Bus integration, and JSON persistence.
- **Distributed Worker Architecture Foundation (v2.7)**: WorkerState models, capability-based discovery, balanced routing, heartbeats, and failover/task re-queuing mechanisms.
- **Observability & Metrics System (v2.4)**: Thread-safe counters, gauges, histograms, structured JSON formatting, error tracker, performance timers, and non-blocking metric gathering.
- **Unified Public SDK v2 (v3.1)**: Exposes API groupings (`agents`, `tasks`, `memory`, `context`, `tools`) under a client `.v2` property while retaining full backward compatibility.
- **API Gateway Layer (v2.2)**: Extensible API Gateway, request models, standardized responses, and WSGI wrapper support.
- **Plugin System Core Foundation (v1.6)**: Fully isolated lifecycle states with circular dependency validation, file discovery, and Agent runtime bridge.

### Fixed
- Fixed an initialization bug in the SDK client `YasinCoreClient` where `self._compatibility` was referenced but never constructed.
- Aligned SDK-level and compatibility-level `@deprecated` decorators to support both keyword parameter formats (`since`/`instead` vs `replaced_by`) within a single unified implementation.
- Standardized `Event` model dictionary subclassing to prevent regression with primitive legacy tests.

---

## [2.0.0] - 2024-11-12

### Added
- **Centralized Orchestration Core**: Introduced `RuntimeOrchestrator` to manage dependency-aware service startup/shutdown sequencing.
- **Persistent Storage Abstraction**: Modular storage interface (`BaseStorage`, `JSONFileStorage`, and `InMemoryStorage`) to handle file serialization safely via reentrant locks.
- **Modular Memory Architecture**: Short-term and long-term memory providers featuring passive TTL-based expiration and context propagation.
- **Event Bus Layer**: Lightweight in-memory event dispatching engine supporting async thread-pool executors.

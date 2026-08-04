# Yasin-Core v3.3.0

[English](#english) | [فارسی](#فارسی)

---

## English

### Overview

Yasin-Core is the central runtime layer of the Yasin AI Ecosystem. It provides the shared execution, runtime, context, security, compatibility, SDK, and observability foundations used by the rest of the ecosystem.

This repository is currently under release-freeze validation for `v3.3.0`. Feature development is frozen while documentation consistency, audit alignment, production-readiness checks, and repository identity are being finalized.

### Core Capabilities

- Agent runtime and task execution primitives
- Context and memory management
- API gateway and integration surfaces
- Compatibility and migration support across ecosystem components
- Storage, security, and observability building blocks
- Plugin, provider, and SDK extension points

### Repository Structure

Key top-level areas:

- `yasin_core/agents/` - agent primitives, planning, runtime, tools, and task models
- `yasin_core/api/` - API gateway, authentication, models, and error handling
- `yasin_core/compatibility/` - adapters, migration, warnings, and version coordination
- `yasin_core/config/` - configuration schema and default settings
- `yasin_core/context/` - context engine and context management
- `yasin_core/core/` - bootstrap, lifecycle, orchestrator, and runtime foundations
- `yasin_core/di/` - dependency injection container and interfaces
- `yasin_core/events/` - event model and event bus
- `yasin_core/execution/` - execution engine, queueing, workers, distributed execution, and scheduler
- `yasin_core/memory/` - in-memory and persistent memory abstractions
- `yasin_core/observability/` - logging, metrics, performance, and monitoring services
- `yasin_core/plugins/` - plugin contracts, bridge, registry, and exceptions
- `yasin_core/providers/` - provider interfaces and adapters
- `yasin_core/runtime/` - runtime interfaces, models, registry, and service manager
- `yasin_core/sdk/` - public SDK clients, interfaces, models, and compatibility helpers
- `yasin_core/security/` - audit, policy, protection, models, and security manager
- `yasin_core/storage/` - storage interfaces and implementations

### Version

Current validated repository version:

- `Yasin-Core 3.3.0`

### Release Status

Current release-freeze priorities:

- Documentation consistency
- Repository identity correction
- Audit and production validation
- Changelog and release note alignment
- Final review before release tagging

### Documentation

Important repository documents:

- `docs/architecture.md`
- `RELEASE_NOTES.md`
- `CHANGELOG.md`
- `FINAL_AUDIT_REPORT.md`
- `PRODUCTION_AUDIT.md`
- `docs/PRODUCTION_AUDIT.md`

Note: some archived or historical documents may still contain legacy or cross-project references. The canonical identity of this repository is `Yasin-Core`.

### Testing

Typical test entry point:
```bash
pytest

The repository includes tests for runtime, agents, API, compatibility, execution, scheduler, storage, SDK, observability, security, and integration behavior.

### Ecosystem Position

Yasin-Core serves as the shared backend and runtime foundation for the broader Yasin ecosystem, including compatibility surfaces used by components such as YasinCLI, YasinHub, YasinRelay, and agent-related tooling.

---

## فارسی

### معرفی

یاسین-کور (`Yasin-Core`) لایه مرکزی runtime در اکوسیستم هوش مصنوعی یاسین است. این مخزن زیرساخت‌های مشترک مربوط به اجرا، runtime، مدیریت context، امنیت، سازگاری، SDK و observability را برای سایر اجزای اکوسیستم فراهم می‌کند.

این مخزن در حال حاضر در وضعیت release-freeze و بازبینی نهایی برای نسخه `3.3.0` قرار دارد. توسعه قابلیت‌های جدید متوقف شده تا یکپارچگی مستندات، هم‌راستاسازی audit، بررسی آمادگی production و اصلاح هویت مخزن نهایی شود.

### قابلیت‌های اصلی

- زیرساخت runtime عامل‌ها و اجرای task
- مدیریت context و memory
- درگاه API و سطوح integration
- سازگاری و migration بین اجزای اکوسیستم
- اجزای پایه برای storage، security و observability
- نقاط توسعه برای plugin، provider و SDK

### ساختار مخزن

بخش‌های اصلی در سطح بالا:

- `yasin_core/agents/` - ماژول‌های عامل، planning، runtime، ابزارها و مدل‌های task
- `yasin_core/api/` - درگاه API، احراز هویت، مدل‌ها و مدیریت خطا
- `yasin_core/compatibility/` - آداپترها، migration، هشدارها و هماهنگی نسخه‌ها
- `yasin_core/config/` - ساختار پیکربندی و تنظیمات پیش‌فرض
- `yasin_core/context/` - موتور context و مدیریت context
- `yasin_core/core/` - bootstrap، lifecycle، orchestrator و هسته runtime
- `yasin_core/di/` - container و interfaceهای dependency injection
- `yasin_core/events/` - مدل event و event bus
- `yasin_core/execution/` - موتور اجرا، صف، worker، اجرای توزیع‌شده و scheduler
- `yasin_core/memory/` - abstractionهای memory موقت و پایدار
- `yasin_core/observability/` - logging، metrics، performance و سرویس‌های پایش
- `yasin_core/plugins/` - قراردادها، bridge، registry و exceptionهای plugin
- `yasin_core/providers/` - interfaceها و adapterهای provider
- `yasin_core/runtime/` - interfaceها، مدل‌ها، registry و service manager
- `yasin_core/sdk/` - کلاینت‌های عمومی SDK، modelها، interfaceها و helperهای سازگاری
- `yasin_core/security/` - audit، policy، protection، modelها و security manager
- `yasin_core/storage/` - interfaceها و پیاده‌سازی‌های storage

### نسخه

نسخه تاییدشده فعلی مخزن:

- `Yasin-Core 3.3.0`

### وضعیت انتشار

اولویت‌های فعلی در مرحله freeze:

- یکپارچگی مستندات
- اصلاح هویت مخزن
- اعتبارسنجی audit و production
- هم‌راستاسازی changelog و release notes
- بازبینی نهایی پیش از release tag

### مستندات مهم

فایل‌های مهم این مخزن:

- `docs/architecture.md`
- `RELEASE_NOTES.md`
- `CHANGELOG.md`
- `FINAL_AUDIT_REPORT.md`
- `PRODUCTION_AUDIT.md`
- `docs/PRODUCTION_AUDIT.md`

نکته: ممکن است بعضی فایل‌های قدیمی یا آرشیوی هنوز شامل ارجاعات legacy یا بین‌پروژه‌ای باشند. هویت canonical این مخزن `Yasin-Core` است.

### تست

دستور معمول برای اجرای تست‌ها:

bash
pytest

این مخزن شامل تست‌هایی برای runtime، agents، API، compatibility، execution، scheduler، storage، SDK، observability، security و integration است.

### جایگاه در اکوسیستم

Yasin-Core به‌عنوان هسته backend و runtime مشترک برای اکوسیستم یاسین عمل می‌کند و بستر سازگاری لازم را برای اجزایی مانند `YasinCLI`، `YasinHub`، `YasinRelay` و ابزارهای مرتبط با agent فراهم می‌سازد.

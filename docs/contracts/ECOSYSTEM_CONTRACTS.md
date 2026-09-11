# Yasin Ecosystem Shared Contracts (Yasin-Core)

Ownership: `Yasin-Core` (`yasin_core.contracts`, re-exported from the public
boundary `yasin_core.sdk`).

## Position in the architecture

```text
PWA → YasinHub → Runit → Services        (lifecycle: YasinHub owns)
YasinCLI → YasinHub → Runit → Services   (CLI is a client)
Services → Yasin-Core contracts          (shared observation language)
```

Contracts describe **observable state only**. They grant no lifecycle
power: no process control, no Runit logic, no PID/port ownership checks,
no transport, no secrets. YasinHub remains the sole Control Plane;
YasinCLI remains its client. Nothing here may become a second
Control Plane.

## Modules

- `contracts.health` — `HealthState` (HEALTHY / DEGRADED / UNHEALTHY /
  UNKNOWN) and `HealthReport` snapshots with strict validation and
  JSON round-trips.
- `contracts.services` — `ServiceStatusValue` (the ecosystem-verified
  observation vocabulary: RUNNING / STOPPED / FAILED / UNKNOWN / IDLE /
  SUCCESS / STALE), `ServiceStatus` snapshots, `ControlAction`, and
  `ControlResult` verdicts matching the Control Plane payload shapes.
  Read models: holding a verdict never authorizes an operation.
- `contracts.errors` — `ErrorCode` categories, `ErrorInfo` records, and
  `redact_secrets()` hygiene for any failure surfaced outward.

## Rules for consumers

1. Import from `yasin_core.sdk` only (enforced by `contract_registry.json`
   and `python -m yasin_core.sdk.boundary`).
2. Unknown enum strings fail validation loudly (`ValueError`) — consumers
   must handle version skew explicitly instead of guessing state.
3. `is_healthy` is true only for an explicit HEALTHY verdict.
4. Error messages are redacted at construction; still never put secrets
   into messages in the first place.

## Non-goals

Lifecycle management, service supervision, configuration migration,
provider specifics, and any Hub/CLI implementation details are
explicitly out of scope for this package.

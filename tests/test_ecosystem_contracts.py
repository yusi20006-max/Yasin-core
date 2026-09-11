"""Issue #106: shared ecosystem contracts (health, service status, errors).

No network, no processes, no Hub dependency: Hub-shaped payloads below are
local fixtures mirroring the verified Hub response shapes, used only to
prove the contracts accept real-world data.
"""

import ast
from pathlib import Path

import pytest

from yasin_core.contracts import (
    ControlAction,
    ControlResult,
    ErrorCode,
    ErrorInfo,
    HealthReport,
    HealthState,
    ServiceStatus,
    ServiceStatusValue,
    coerce_control_action,
    coerce_error_code,
    coerce_health_state,
    coerce_status_value,
    redact_secrets,
)
from yasin_core.sdk.contract import (
    get_public_exports,
    load_contract_registry,
    validate_registry_schema,
)


def test_health_states_cover_observation_vocabulary():
    assert {m.value for m in HealthState} == {"HEALTHY", "DEGRADED", "UNHEALTHY", "UNKNOWN"}
    assert coerce_health_state("healthy") is HealthState.HEALTHY
    assert coerce_health_state(" Degraded ") is HealthState.DEGRADED
    with pytest.raises(ValueError):
        coerce_health_state("RUNNING")


def test_health_report_round_trip_and_gates():
    report = HealthReport(service="yasin-ai", state=HealthState.HEALTHY, message="ok")
    assert report.is_healthy is True
    clone = HealthReport.from_dict(report.to_dict())
    assert clone == report
    assert HealthReport(service="x", state=HealthState.UNKNOWN).is_healthy is False
    with pytest.raises(ValueError):
        HealthReport(service="  ", state=HealthState.HEALTHY).validate()
    with pytest.raises(ValueError):
        HealthReport.from_dict({"service": "x", "state": "bogus"})


def test_service_status_values_match_ecosystem_vocabulary():
    assert {m.value for m in ServiceStatusValue} >= {
        "RUNNING", "STOPPED", "FAILED", "UNKNOWN", "IDLE", "SUCCESS", "STALE",
    }
    assert coerce_status_value("running") is ServiceStatusValue.RUNNING
    with pytest.raises(ValueError):
        coerce_status_value("STARTING")


def test_service_status_snapshot_round_trip():
    snapshot = ServiceStatus(
        name="yasinrelay", status=ServiceStatusValue.RUNNING,
        pid=4876, running=True, message="observed running",
    )
    clone = ServiceStatus.from_dict(snapshot.to_dict())
    assert clone == snapshot
    assert clone.pid == 4876 and clone.running is True
    with pytest.raises(ValueError):
        ServiceStatus(name="", status=ServiceStatusValue.RUNNING).validate()
    with pytest.raises(ValueError):
        ServiceStatus(name="x", status=ServiceStatusValue.RUNNING, pid=-5).validate()
    with pytest.raises(ValueError):
        ServiceStatus.from_dict({"name": "x", "status": "FLYING"})


def test_control_result_matches_hub_verdict_shape():
    # Local fixture shaped like the verified Hub control payload.
    hub_shaped = {
        "service": "yasin-ai", "action": "restart", "success": True,
        "status": "RUNNING", "pid": 4774, "message": "observed running",
    }
    verdict = ControlResult.from_dict(hub_shaped)
    assert verdict.service == "yasin-ai"
    assert verdict.action is ControlAction.RESTART
    assert verdict.success is True
    assert verdict.to_dict()["action"] == "restart"
    refused = ControlResult.from_dict({
        "service": "yasinfeed", "action": "start", "success": False,
        "status": "FAILED", "pid": None, "message": "refused",
    })
    assert refused.success is False and refused.pid is None
    with pytest.raises(ValueError):
        ControlResult.from_dict({**hub_shaped, "action": "explode"})
    with pytest.raises(ValueError):
        coerce_control_action("")


def test_error_info_redacts_at_construction():
    record = ErrorInfo(code=ErrorCode.REFUSED, message="denied token=SECRET-ABC password=hunter2")
    assert "SECRET-ABC" not in record.message
    assert "hunter2" not in record.message
    assert "***" in record.message
    assert record.code is ErrorCode.REFUSED
    clone = ErrorInfo.from_dict(record.to_dict())
    assert clone == record
    assert redact_secrets(None) != ""
    with pytest.raises(ValueError):
        coerce_error_code("MELTDOWN")


def test_contracts_exposed_through_public_sdk_boundary():
    import yasin_core.sdk as sdk

    for name in (
        "HealthState", "HealthReport", "coerce_health_state",
        "ServiceStatusValue", "ControlAction", "ServiceStatus", "ControlResult",
        "coerce_status_value", "coerce_control_action",
        "ErrorCode", "ErrorInfo", "redact_secrets", "coerce_error_code",
    ):
        assert name in sdk.__all__, name
        assert hasattr(sdk, name), name


def test_registry_validates_and_declares_new_contracts():
    registry = load_contract_registry()
    assert validate_registry_schema(registry) == []
    assert registry["contract_version"] == "1.1.0"
    exports = get_public_exports(registry)
    assert {"ServiceStatus", "ControlResult", "HealthReport", "ErrorInfo", "redact_secrets"} <= exports
    # Additive only: previously declared exports still present.
    assert "YasinCoreClient" in exports and "EventBus" in exports


def test_contracts_modules_are_dependency_free_and_powerless():
    # Shared contracts must not import the ecosystem, the stdlib process
    # surface, or anything that could manage a lifecycle.
    root = Path(__file__).resolve().parents[1] / "yasin_core" / "contracts"
    forbidden = ("yasin_core", "subprocess", "os.kill", "signal", "socket", "runit", "sv ")
    for module in ("__init__.py", "health.py", "services.py", "errors.py"):
        tree = ast.parse((root / module).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        assert not (imported & {"yasin_core", "subprocess", "socket", "signal"}), (module, imported)
        source = (root / module).read_text(encoding="utf-8")
        for token in ("os.kill", "SIGKILL", "SIGTERM", "Popen", "runit"):
            assert token not in source, (module, token)

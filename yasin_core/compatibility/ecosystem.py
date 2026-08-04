from typing import Any, Dict, List, Optional
from yasin_core.compatibility.exceptions import EcosystemValidationError
from yasin_core.compatibility.version import is_compatible
from yasin_core.version import VERSION


class AgentCompatibilityValidator:
    """
    Validates if a given agent instance or agent class is compatible with the core ecosystem.
    """

    @staticmethod
    def validate(agent: Any) -> Dict[str, Any]:
        """
        Verify that an agent possesses core properties (name, execute_task or execute)
        and compatible version constraints.
        """
        report = {"compatible": True, "errors": []}

        # Check name
        if not hasattr(agent, "name") or not isinstance(getattr(agent, "name"), str):
            report["compatible"] = False
            report["errors"].append("Agent must have a string 'name' attribute.")

        # Check execution capabilities
        if not hasattr(agent, "execute_task") and not hasattr(agent, "execute"):
            report["compatible"] = False
            report["errors"].append("Agent must implement either 'execute_task' or 'execute' method.")

        # Check core compatibility constraint
        core_compat = getattr(agent, "core_version_compat", "*")
        if not is_compatible(core_compat, VERSION):
            report["compatible"] = False
            report["errors"].append(
                f"Agent version compatibility '{core_compat}' is not compatible with core version '{VERSION}'"
            )

        return report


class HubCompatibilityValidator:
    """
    Validates Hub metadata, packaging structures, or integration definitions.
    """

    @staticmethod
    def validate(hub_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that the Hub package metadata structure is correct and compatible.
        """
        report = {"compatible": True, "errors": []}

        required_fields = ["id", "version", "core_version_compat"]
        for field in required_fields:
            if field not in hub_metadata:
                report["compatible"] = False
                report["errors"].append(f"Hub metadata is missing required field '{field}'.")

        if report["compatible"]:
            compat = hub_metadata["core_version_compat"]
            if not is_compatible(compat, VERSION):
                report["compatible"] = False
                report["errors"].append(
                    f"Hub package compatibility '{compat}' is incompatible with core version '{VERSION}'"
                )

        return report


class RelayCompatibilityValidator:
    """
    Validates Relay processing components, custom pipelines, and feed structures.
    """

    @staticmethod
    def validate(relay_component: Any) -> Dict[str, Any]:
        """
        Validate that a Relay component (e.g. custom pipeline step or publisher)
        conforms to expected processing APIs (such as implementing 'process' or 'publish').
        """
        report = {"compatible": True, "errors": []}

        has_process = hasattr(relay_component, "process") and callable(getattr(relay_component, "process"))
        has_publish = hasattr(relay_component, "publish") and callable(getattr(relay_component, "publish"))

        if not has_process and not has_publish:
            report["compatible"] = False
            report["errors"].append("Relay component must implement either a 'process' or 'publish' method.")

        compat = getattr(relay_component, "core_version_compat", "*")
        if not is_compatible(compat, VERSION):
            report["compatible"] = False
            report["errors"].append(
                f"Relay component core version constraint '{compat}' is incompatible with core version '{VERSION}'"
            )

        return report


class CLICompatibilityValidator:
    """
    Validates command structures, command definitions, or command-line option maps.
    """

    @staticmethod
    def validate(cli_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that the CLI commands definition and version are compatible with Core.
        """
        report = {"compatible": True, "errors": []}

        if "commands" not in cli_metadata or not isinstance(cli_metadata["commands"], dict):
            report["compatible"] = False
            report["errors"].append("CLI metadata must include a 'commands' dictionary.")

        compat = cli_metadata.get("core_version_compat", "*")
        if not is_compatible(compat, VERSION):
            report["compatible"] = False
            report["errors"].append(
                f"CLI compatibility constraint '{compat}' is incompatible with core version '{VERSION}'"
            )

        return report


class RuntimeCompatibilityChecker:
    """
    Assesses runtime compatibility of active configurations, storage adapters,
    DI container registrations, and service instances.
    """

    def __init__(self, client: Any):
        self.client = client

    def check_runtime_compatibility(self) -> Dict[str, Any]:
        """
        Generate a comprehensive compatibility audit report of the running SDK client.
        """
        report = {
            "compatible": True,
            "core_version": VERSION,
            "checks": {
                "config": {"status": "PASS", "details": []},
                "services": {"status": "PASS", "details": []},
                "storage": {"status": "PASS", "details": []},
                "di": {"status": "PASS", "details": []}
            }
        }

        # 1. Config validation
        try:
            if hasattr(self.client, "config") and self.client.config:
                # E.g., make sure settings is not empty
                settings = getattr(self.client.config, "settings", None)
                if not settings:
                    report["checks"]["config"] = {
                        "status": "WARN",
                        "details": ["Settings dictionary is empty or not initialized."]
                    }
        except Exception as e:
            report["checks"]["config"] = {"status": "FAIL", "details": [f"Config check error: {e}"]}
            report["compatible"] = False

        # 2. Registered services check
        try:
            if hasattr(self.client, "service_registry") and self.client.service_registry:
                registry = self.client.service_registry
                # Check list of registered services and status
                services = registry.list_services() if hasattr(registry, "list_services") else []
                for s in services:
                    status = registry.get_service_status(s) if hasattr(registry, "get_service_status") else {}
                    # If service has an incompatible version tag or is failed
                    if status.get("state") == "FAILED":
                        report["checks"]["services"]["status"] = "WARN"
                        report["checks"]["services"]["details"].append(f"Service '{s}' is in a FAILED state.")
        except Exception as e:
            report["checks"]["services"] = {"status": "FAIL", "details": [f"Service registry check error: {e}"]}
            report["compatible"] = False

        # 3. Storage check
        try:
            if hasattr(self.client, "storage") and self.client.storage:
                storage = self.client.storage
                if not hasattr(storage, "get") or not hasattr(storage, "set"):
                    report["checks"]["storage"] = {
                        "status": "FAIL",
                        "details": ["Active storage provider is missing required 'get' or 'set' APIs."]
                    }
                    report["compatible"] = False
        except Exception as e:
            report["checks"]["storage"] = {"status": "FAIL", "details": [f"Storage check error: {e}"]}
            report["compatible"] = False

        # 4. DI registrations check
        try:
            if hasattr(self.client, "di_container") and self.client.di_container:
                container = self.client.di_container
                # Verify key singletons exist
                required_singletons = ["client", "config", "storage", "event_bus"]
                for item in required_singletons:
                    try:
                        inst = container.resolve(item)
                        if not inst:
                            raise ValueError()
                    except Exception:
                        report["checks"]["di"]["status"] = "WARN"
                        report["checks"]["di"]["details"].append(f"Missing recommended DI registration for alias '{item}'.")
        except Exception as e:
            report["checks"]["di"] = {"status": "FAIL", "details": [f"DI Container check error: {e}"]}
            report["compatible"] = False

        # Aggregate overall report compatible status
        for check in report["checks"].values():
            if check["status"] == "FAIL":
                report["compatible"] = False
                break

        return report

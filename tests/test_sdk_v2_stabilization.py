import pytest
import asyncio
import warnings
from typing import Dict, Any

from yasin_core.sdk import (
    YasinCoreClient,
    AsyncYasinCoreClient,
    BaseAgent,
    Task,
    BaseTool,
    SDKError,
    SDKValidationError,
    SDKAuthenticationError,
    SDKConnectionError,
    SDKExecutionError,
    SDKDeprecationWarning,
    translate_core_errors,
    SDKRequest,
    SDKResponse,
    SDKVersionChecker,
    deprecated,
    SDKMigrationHelper,
)


class MockV2Agent(BaseAgent):
    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        return f"v2-processed: {input_data.get('msg', '')}"


class MockV2Tool(BaseTool):
    def execute(self, *args, **kwargs) -> Any:
        return f"tool-executed: {args}"


def test_sdk_v2_lifecycle_and_context_manager():
    """Test SDK v2 lazy initialization, running hooks, and context manager support."""
    client = YasinCoreClient()
    # Check automated init on construction
    assert client._initialized is True
    assert client.is_active() is False

    # Test as Context Manager
    with YasinCoreClient() as client_ctx:
        assert client_ctx._initialized is True
        assert client_ctx.is_active() is True

    # After exit, it should be stopped
    assert client_ctx.is_active() is False


def test_sdk_v2_api_namespace_organization():
    """Test standard modern v2 namespace grouping on YasinCoreClient."""
    client = YasinCoreClient()
    agent = MockV2Agent(name="v2-agent", description="A modern v2 agent")

    # 1. Agents namespace
    client.v2.agents.register(agent)
    assert "v2-agent" in client.v2.agents.list()
    assert client.v2.agents.get("v2-agent") == agent

    # 2. Tasks namespace
    task = client.v2.tasks.create(id="v2-t-1", name="v2-agent", input_data={"msg": "hello"})
    assert isinstance(task, Task)

    # Executing task via proxy
    res_task = client.v2.tasks.execute(task)
    assert res_task.status == "completed"
    assert res_task.result == "v2-processed: hello"

    # Remove agent via proxy
    client.v2.agents.remove("v2-agent")
    assert "v2-agent" not in client.v2.agents.list()

    # 3. Memory namespace
    client.v2.memory.save("v2-k", "v2-v", category="short-term")
    assert client.v2.memory.get("v2-k", category="short-term") == "v2-v"

    # 4. Context namespace
    ctx = client.v2.context.create({"session": "v2-sess"})
    assert ctx.get("session") == "v2-sess"

    # Verify active context
    from yasin_core.context.manager import active_context
    with active_context(ctx):
        assert client.v2.context.active == ctx

    # 5. Tools namespace
    tool_inst = MockV2Tool(name="v2-tool", description="A modern v2 tool")
    client.v2.tools.register(tool_inst)
    assert "v2-tool" in client.v2.tools.list()
    assert client.v2.tools.get("v2-tool") == tool_inst
    assert client.v2.tools.execute("v2-tool", "arg1") == "tool-executed: ('arg1',)"


def test_sdk_v2_async_api_preparation():
    """Test AsyncYasinCoreClient async execution pathways."""
    async def run_test():
        async_client = AsyncYasinCoreClient()
        await async_client.initialize()

        # Test async memory ops
        await async_client.save_memory("async-k", "async-v")
        val = await async_client.get_memory("async-k")
        assert val == "async-v"

        # Test async health/status
        h = await async_client.health()
        assert isinstance(h, dict)
        s = await async_client.status()
        assert isinstance(s, dict)

    asyncio.run(run_test())


def test_sdk_v2_version_compatibility():
    """Test SDKVersionChecker functionality."""
    # Matches same major versions
    assert SDKVersionChecker.check_compatibility("3.1.0", "3.0.0") is True
    assert SDKVersionChecker.check_compatibility("3.2.1", "3.1.0") is True
    # Different major version fails
    assert SDKVersionChecker.check_compatibility("3.0.0", "2.0.0") is False
    assert SDKVersionChecker.check_compatibility("invalid", "3.1.0") is False


def test_sdk_v2_deprecation_handling():
    """Test @deprecated triggers DeprecationWarning."""
    @deprecated(replaced_by="modern_method")
    def legacy_method():
        return "legacy"

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        res = legacy_method()
        assert res == "legacy"
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "legacy_method is deprecated" in str(w[0].message)
        assert "modern_method" in str(w[0].message)


def test_sdk_v2_migration_helpers():
    """Test SDKMigrationHelper conversions of V1 payloads/schemas to V2."""
    v1_task_payload = {"id": "t-1", "name": "a-1", "input_data": {"q": "hi"}}
    v2_task_payload = SDKMigrationHelper.migrate_task_payload(v1_task_payload)
    assert v2_task_payload["meta"]["version"] == "v2"
    assert v2_task_payload["meta"]["migrated"] is True

    v1_mem_payload = {"key": "k", "value": "v", "metadata": {"old": True}}
    v2_mem_payload = SDKMigrationHelper.migrate_memory_payload(v1_mem_payload)
    assert v2_mem_payload["metadata"]["v2_saved"] is True
    assert v2_mem_payload["metadata"]["migrated"] is True


def test_sdk_v2_error_translation():
    """Test translate_core_errors maps core errors to standardized SDK exceptions."""
    from yasin_core.security import AccessDeniedError

    @translate_core_errors
    def raise_access_denied():
        raise AccessDeniedError("Access Denied!")

    with pytest.raises(SDKAuthenticationError) as exc_info:
        raise_access_denied()
    assert "Security/Authentication failure" in str(exc_info.value)

    @translate_core_errors
    def raise_value_error():
        raise ValueError("Invalid format!")

    with pytest.raises(SDKValidationError) as exc_info:
        raise_value_error()
    assert "Invalid format!" in str(exc_info.value)

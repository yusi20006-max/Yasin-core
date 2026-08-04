import pytest
import time
from typing import Any, Dict

from yasin_core.sdk import (
    YasinCoreClient,
    BaseAgent,
    Task,
    active_context,
    get_current_context,
    AgentRuntime,
    IAgentRuntime,
    AGENT_REGISTERED,
    AGENT_REMOVED,
    AGENT_STARTED,
    AGENT_STOPPED,
    TASK_STARTED,
    TASK_COMPLETED,
    TASK_FAILED,
)
from yasin_core.security import Permission, Role, Subject, AccessDeniedError


class RuntimeTestAgent(BaseAgent):
    def __init__(self, name: str, description: str = "", tools: list = None, capabilities: list = None, permissions: list = None):
        super().__init__(name=name, description=description, tools=tools, capabilities=capabilities, permissions=permissions)
        self.started_calls = 0
        self.stopped_calls = 0

    def start(self) -> None:
        self.running = True
        self.started_calls += 1

    def stop(self) -> None:
        self.running = False
        self.stopped_calls += 1

    def execute(self, input_data: Dict[str, Any]) -> Any:
        ctx = get_current_context()
        prefix = ctx.get("prefix", "Test") if ctx else "Test"
        if input_data.get("fail", False):
            raise ValueError("Intentional execution error")
        return f"{prefix}: {input_data.get('data', 'processed')}"


# 1. Agent Registration & API tests
def test_agent_registration_apis():
    client = YasinCoreClient()
    runtime = client.agent_runtime

    assert isinstance(runtime, IAgentRuntime)

    agent = RuntimeTestAgent(name="reg-agent", capabilities=["math", "text"])
    runtime.register_agent(agent)

    assert "reg-agent" in runtime.list_agents()
    assert runtime.get_agent("reg-agent") == agent

    # Discovery by capability
    math_agents = runtime.discover_agents_by_capability("math")
    assert agent in math_agents

    text_agents = runtime.discover_agents_by_capability("text")
    assert agent in text_agents

    unknown_agents = runtime.discover_agents_by_capability("unknown")
    assert agent not in unknown_agents

    # Removal
    removed = runtime.remove_agent("reg-agent")
    assert removed == agent
    assert "reg-agent" not in runtime.list_agents()


# 2. Agent Lifecycle tests
def test_agent_lifecycle_management():
    client = YasinCoreClient()
    runtime = client.agent_runtime

    agent1 = RuntimeTestAgent(name="agent1")
    agent2 = RuntimeTestAgent(name="agent2")

    runtime.register_agent(agent1)
    runtime.register_agent(agent2)

    assert not agent1.running
    assert not agent2.running

    runtime.start_agents()
    assert agent1.running
    assert agent2.running
    assert agent1.started_calls == 1
    assert agent2.started_calls == 1

    runtime.stop_agents()
    assert not agent1.running
    assert not agent2.running
    assert agent1.stopped_calls == 1
    assert agent2.stopped_calls == 1


# 3. Agent Execution & Context integration tests
def test_agent_execution_and_context():
    client = YasinCoreClient()
    runtime = client.agent_runtime

    agent = RuntimeTestAgent(name="exec-agent")
    runtime.register_agent(agent)

    task = Task(id="t-1", name="exec-agent", input_data={"data": "hello"})

    # Execute without active context (defaults to "Test: hello")
    res_task = runtime.execute_agent_task(task)
    assert res_task.status == "completed"
    assert res_task.result == "Test: hello"

    # Execute with active context
    context = client.create_context({"prefix": "ContextPrefix"})
    with active_context(context):
        task2 = Task(id="t-2", name="exec-agent", input_data={"data": "world"})
        res_task2 = runtime.execute_agent_task(task2)
        assert res_task2.status == "completed"
        assert res_task2.result == "ContextPrefix: world"


# 4. Agent Communication Layer tests
def test_agent_communication_messaging():
    client = YasinCoreClient()
    runtime = client.agent_runtime

    agent_a = RuntimeTestAgent(name="agent-a")
    agent_b = RuntimeTestAgent(name="agent-b")

    runtime.register_agent(agent_a)
    runtime.register_agent(agent_b)

    # Send message from agent-a to agent-b
    runtime.send_agent_message(sender="agent-a", receiver="agent-b", message="Hello Agent B!")

    # Retrieve messages for agent-b
    msgs = runtime.retrieve_agent_messages("agent-b")
    assert len(msgs) == 1
    assert msgs[0]["sender"] == "agent-a"
    assert msgs[0]["message"] == "Hello Agent B!"

    # Inbox should be empty after retrieval
    assert len(runtime.retrieve_agent_messages("agent-b")) == 0


# 5. Agent Permission Validation tests
def test_agent_permission_validation():
    client = YasinCoreClient()
    runtime = client.agent_runtime

    # Configure security manager policies/roles
    security = client.security
    # Create role and permissions
    perm_exec = Permission("execute_restricted_agent")
    role = Role("agent_user", permissions=[perm_exec])
    security.register_role(role)

    # Subject without matching permission
    subject_unauthorized = Subject("user1", subject_type="user", roles=[])

    # Register agent requiring permission
    agent = RuntimeTestAgent(name="restricted-agent", permissions=["execute_restricted_agent"])

    context = client.create_context()
    with active_context(context):
        # Act as unauthorized user (validation fails on registration/execution)
        with patch_security_context(security, subject_unauthorized):
            # Registration or execution should fail when restricted
            with pytest.raises(Exception):
                runtime.register_agent(agent)

        # Subject with matching permission
        subject_authorized = Subject("user2", subject_type="user", roles=[role])
        with patch_security_context(security, subject_authorized):
            # Registration should succeed now
            runtime.register_agent(agent)

            # Test execution security check
            task = Task(id="t-perm", name="restricted-agent", input_data={"data": "secure"})
            res_task = runtime.execute_agent_task(task)
            assert res_task.status == "completed"

        # Act again as unauthorized for execution
        with patch_security_context(security, subject_unauthorized):
            task_fail = Task(id="t-perm-fail", name="restricted-agent", input_data={"data": "secure"})
            res_task_fail = runtime.execute_agent_task(task_fail)
            assert res_task_fail.status == "failed"
            assert "Access denied" in res_task_fail.error or "Permission" in res_task_fail.error or "Not authorized" in res_task_fail.error


# 6. Workflow integration tests (Sequential & Parallel workflows)
def test_agent_workflow_integration():
    client = YasinCoreClient()
    runtime = client.agent_runtime

    agent_x = RuntimeTestAgent(name="agent-x")
    agent_y = RuntimeTestAgent(name="agent-y")
    runtime.register_agent(agent_x)
    runtime.register_agent(agent_y)

    # Workflow pattern: Agent X processes then puts outcome into agent-y inbox
    task_x = Task(id="wx", name="agent-x", input_data={"data": "workflow-init"})
    res_x = runtime.execute_agent_task(task_x)
    assert res_x.status == "completed"

    runtime.send_agent_message(sender="agent-x", receiver="agent-y", message=res_x.result)

    msgs = runtime.retrieve_agent_messages("agent-y")
    assert len(msgs) == 1
    assert msgs[0]["message"] == "Test: workflow-init"


# 7. State Management tests
def test_agent_state_management():
    client = YasinCoreClient()
    runtime = client.agent_runtime

    agent = RuntimeTestAgent(name="state-agent")
    runtime.register_agent(agent)

    agent.state["last_active"] = "2026-08-04"
    agent.state["counter"] = 42

    # Save state
    runtime.save_agent_state("state-agent")

    # Modify state in memory
    agent.state["counter"] = 0

    # Load state
    runtime.load_agent_state("state-agent")
    assert agent.state["counter"] == 42
    assert agent.state["last_active"] == "2026-08-04"


# 8. Runtime Failure & Resiliency tests
def test_agent_runtime_failures_and_errors():
    client = YasinCoreClient()
    runtime = client.agent_runtime

    agent = RuntimeTestAgent(name="faulty-agent")
    runtime.register_agent(agent)

    task = Task(id="tf-1", name="faulty-agent", input_data={"fail": True})
    res_task = runtime.execute_agent_task(task)

    assert res_task.status == "failed"
    assert "Intentional execution error" in res_task.error

    # Nonexistent agent handling
    task_nonexistent = Task(id="tf-2", name="nonexistent-agent")
    res_task_nonexistent = runtime.execute_agent_task(task_nonexistent)
    assert res_task_nonexistent.status == "failed"
    assert "not found" in res_task_nonexistent.error


# 9. SDK Compatibility tests
def test_sdk_client_delegation_compatibility():
    client = YasinCoreClient()
    agent = RuntimeTestAgent(name="sdk-agent")

    client.register_agent(agent)
    assert "sdk-agent" in client.list_agents()
    assert client.get_agent("sdk-agent") == agent

    client.start_agents()
    assert agent.running

    task = client.create_task(id="tsdk", name="sdk-agent", input_data={"data": "sdk-call"})
    res_task = client.execute_task(task)
    assert res_task.status == "completed"
    assert res_task.result == "Test: sdk-call"

    client.stop_agents()
    assert not agent.running


# Context helper for permission testing
class patch_security_context:
    def __init__(self, security_manager, subject):
        self.security = security_manager
        self.subject = subject
        self.old_validate = None

    def __enter__(self):
        self.old_validate = self.security.validate_runtime_check

        def mock_validate(subject, action, resource):
            # Check if our mocked subject has the permission
            # Look up permissions on subject's roles
            sub = subject or self.subject
            permission = f"{action}:{resource}"
            # Check direct permissions or roles
            for p in sub.direct_permissions:
                if p.name == permission or p.name == resource:
                    return True
            for role_name in sub.roles:
                role = self.security.get_role(role_name)
                if role and role.has_permission(permission):
                    return True
                if role and role.has_permission(resource):
                    return True
            from yasin_core.security import AccessDeniedError
            raise AccessDeniedError(f"Access denied: Subject lacks permission {permission}")

        self.security.validate_runtime_check = mock_validate

        # We also need to set the security_subject in the active context
        # to ensure it is resolved by AgentRuntime
        from yasin_core.context.manager import get_current_context
        ctx = get_current_context()
        if ctx:
            ctx.set("security_subject", self.subject)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.security.validate_runtime_check = self.old_validate
        from yasin_core.context.manager import get_current_context
        ctx = get_current_context()
        if ctx:
            ctx.set("security_subject", None)

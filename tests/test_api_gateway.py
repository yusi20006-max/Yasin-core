import pytest
import time
from typing import Dict, Any
from yasin_core.sdk import (
    YasinCoreClient,
    APIRequest,
    APIResponse,
    APIGateway,
    APIKeyAuthenticator,
    APIError,
    APIErrorCode,
    BaseAgent,
    RuntimeState,
)


class DummyAgentForApi(BaseAgent):
    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        return f"Api Processed: {input_data.get('data', '')}"


def test_api_gateway_initialization():
    client = YasinCoreClient()
    assert client.api_gateway is not None
    assert isinstance(client.api_gateway, APIGateway)

    # DI Container checks
    di_gateway = client.di_container.resolve(APIGateway)
    assert di_gateway == client.api_gateway

    # Service Registry checks
    srv_gateway = client.service_registry.get_service("api_gateway")
    assert srv_gateway == client.api_gateway


def test_api_request_response_models():
    # Valid Request
    req = APIRequest(
        method="GET",
        path="/v1/health",
        headers={"Authorization": "Bearer key1"},
        query_params={"debug": "true"},
        body={"some": "payload"},
    )
    req.validate()
    assert req.method == "GET"
    assert req.path == "/v1/health"
    assert req.headers["authorization"] == "Bearer key1"
    assert req.query_params["debug"] == "true"
    assert req.body == {"some": "payload"}

    # Invalid Request Header Validation
    bad_req = APIRequest(method="GET", path="/v1/health", headers="not-a-dict")
    with pytest.raises(ValueError, match="Headers must be a dictionary"):
        bad_req.validate()

    # Response Model checks
    resp = APIResponse(status_code=200, data={"ok": True}, version="v2")
    serialized = resp.to_dict()
    assert serialized["status_code"] == 200
    assert serialized["data"] == {"ok": True}
    assert serialized["errors"] == []
    assert serialized["version"] == "v2"


def test_api_gateway_authentication():
    client = YasinCoreClient()
    # Configure required API Key authenticator
    auth = APIKeyAuthenticator(allowed_keys=["secret_key_123"], required=True)
    gateway = APIGateway(client, authenticator=auth)

    # 1. Missing Token
    req_missing = APIRequest(method="GET", path="/v1/health")
    resp = gateway.handle_request(req_missing)
    assert resp.status_code == 401
    assert resp.errors[0]["code"] == "UNAUTHORIZED"

    # 2. Invalid Token
    req_invalid = APIRequest(
        method="GET",
        path="/v1/health",
        headers={"X-API-Key": "wrong_key"},
    )
    resp = gateway.handle_request(req_invalid)
    assert resp.status_code == 403
    assert resp.errors[0]["code"] == "FORBIDDEN"

    # 3. Valid Token (Header: X-API-Key)
    req_valid_api_key = APIRequest(
        method="GET",
        path="/v1/health",
        headers={"x-api-key": "secret_key_123"},
    )
    resp = gateway.handle_request(req_valid_api_key)
    assert resp.status_code == 200

    # 4. Valid Token (Header: Bearer Authorization)
    req_valid_bearer = APIRequest(
        method="GET",
        path="/v1/health",
        headers={"Authorization": "Bearer secret_key_123"},
    )
    resp = gateway.handle_request(req_valid_bearer)
    assert resp.status_code == 200


def test_api_gateway_health_and_runtime_endpoints():
    client = YasinCoreClient()
    gateway = client.api_gateway

    # Health Checks
    req = APIRequest(method="GET", path="/v1/health")
    resp = gateway.handle_request(req)
    assert resp.status_code == 200
    assert "healthy" in resp.data

    # Runtime Status Checks
    req = APIRequest(method="GET", path="/v1/runtime/status")
    resp = gateway.handle_request(req)
    assert resp.status_code == 200
    assert "state" in resp.data

    # Runtime Lifecycle Control
    assert client.orchestrator.state == RuntimeState.UNINITIALIZED
    req_start = APIRequest(method="POST", path="/v1/runtime/start")
    resp = gateway.handle_request(req_start)
    assert resp.status_code == 200
    assert client.orchestrator.state == RuntimeState.RUNNING

    req_stop = APIRequest(method="POST", path="/v1/runtime/stop")
    resp = gateway.handle_request(req_stop)
    assert resp.status_code == 200
    assert client.orchestrator.state == RuntimeState.STOPPED


def test_api_gateway_task_endpoints_v1_and_v2():
    client = YasinCoreClient()
    agent = DummyAgentForApi(name="api-agent")
    client.register_agent(agent)
    gateway = client.api_gateway

    # Create task
    req_create = APIRequest(
        method="POST",
        path="/v1/tasks/create",
        body={"id": "task-api-1", "name": "api-agent", "input_data": {"data": "hello"}},
    )
    resp_create = gateway.handle_request(req_create)
    assert resp_create.status_code == 201
    assert resp_create.data["id"] == "task-api-1"
    assert resp_create.data["status"] == "pending"

    # Execute task V1
    req_exec_v1 = APIRequest(
        method="POST",
        path="/v1/tasks/execute",
        body={"id": "task-api-1", "name": "api-agent", "input_data": {"data": "hello"}},
    )
    resp_exec_v1 = gateway.handle_request(req_exec_v1)
    assert resp_exec_v1.status_code == 200
    assert resp_exec_v1.data["status"] == "completed"
    assert resp_exec_v1.data["result"] == "Api Processed: hello"
    assert resp_exec_v1.version == "v1"

    # Execute task V2
    req_exec_v2 = APIRequest(
        method="POST",
        path="/v2/tasks/execute",
        body={"id": "task-api-2", "name": "api-agent", "input_data": {"data": "world"}},
    )
    resp_exec_v2 = gateway.handle_request(req_exec_v2)
    assert resp_exec_v2.status_code == 200
    assert resp_exec_v2.data["status"] == "completed"
    assert resp_exec_v2.data["result"] == "Api Processed: world"
    assert "meta" in resp_exec_v2.data
    assert resp_exec_v2.data["meta"]["version"] == "v2"
    assert "duration_seconds" in resp_exec_v2.data["meta"]
    assert resp_exec_v2.version == "v2"


def test_api_gateway_memory_and_context_endpoints():
    client = YasinCoreClient()
    gateway = client.api_gateway

    # Save Memory V1
    req_save = APIRequest(
        method="POST",
        path="/v1/memory/save",
        body={"key": "mem1", "value": "val1", "category": "short-term"},
    )
    resp = gateway.handle_request(req_save)
    assert resp.status_code == 200

    # Retrieve Memory V1
    req_get = APIRequest(
        method="GET",
        path="/v1/memory/get",
        query_params={"key": "mem1", "category": "short-term"},
    )
    resp = gateway.handle_request(req_get)
    assert resp.status_code == 200
    assert resp.data["value"] == "val1"

    # Save Memory V2 (with metadata dictionary validation)
    req_save_v2 = APIRequest(
        method="POST",
        path="/v2/memory/save",
        body={"key": "mem2", "value": "val2", "metadata": {"custom_tag": "test"}},
    )
    resp = gateway.handle_request(req_save_v2)
    assert resp.status_code == 200
    assert resp.version == "v2"

    # Save Memory V2 invalid (metadata is not dictionary)
    req_save_v2_bad = APIRequest(
        method="POST",
        path="/v2/memory/save",
        body={"key": "mem3", "value": "val3", "metadata": "not-a-dict"},
    )
    resp = gateway.handle_request(req_save_v2_bad)
    assert resp.status_code == 400
    assert resp.errors[0]["code"] == "VALIDATION_ERROR"

    # Create Context
    req_ctx = APIRequest(
        method="POST",
        path="/v1/context/create",
        body={"data": {"request_id": "req-xyz"}, "metadata": {"origin": "api"}},
    )
    resp = gateway.handle_request(req_ctx)
    assert resp.status_code == 201
    context_id = resp.data["id"]
    assert context_id is not None

    # Retrieve Active Context
    req_active = APIRequest(method="GET", path="/v1/context/active")
    resp = gateway.handle_request(req_active)
    assert resp.status_code == 200

    # Retrieve Context Memories
    req_memories = APIRequest(
        method="GET",
        path="/v1/context/memories",
        query_params={"context_id": context_id},
    )
    resp = gateway.handle_request(req_memories)
    assert resp.status_code == 200
    assert "short-term" in resp.data
    assert "long-term" in resp.data


def test_api_gateway_plugins_and_events():
    client = YasinCoreClient()
    gateway = client.api_gateway

    # Get Plugin List & Status
    req_list = APIRequest(method="GET", path="/v1/plugins/list")
    resp = gateway.handle_request(req_list)
    assert resp.status_code == 200
    assert isinstance(resp.data["plugins"], list)

    req_status = APIRequest(method="GET", path="/v1/plugins/status")
    resp = gateway.handle_request(req_status)
    assert resp.status_code == 200
    assert "plugin_count" in resp.data or "total_plugins" in resp.data

    # Event Publishing Integration
    event_received = []

    def event_handler(ev):
        event_received.append(ev)

    client.event_bus.subscribe("test_api_event", event_handler)

    req_publish = APIRequest(
        method="POST",
        path="/v1/events/publish",
        body={"event_name": "test_api_event", "payload": {"status": "ok"}},
    )
    resp = gateway.handle_request(req_publish)
    assert resp.status_code == 200

    time.sleep(0.1)
    assert len(event_received) == 1
    assert event_received[0]["status"] == "ok"


def test_api_gateway_wsgi_wrapper():
    import json
    client = YasinCoreClient()
    wsgi_app = client.api_gateway.as_wsgi_app()

    called = []

    def start_response(status, headers):
        called.append((status, headers))

    environ = {
        "PATH_INFO": "/v1/health",
        "REQUEST_METHOD": "GET",
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
    }

    response_iter = wsgi_app(environ, start_response)
    response_body = b"".join(response_iter)

    assert len(called) == 1
    assert called[0][0] == "200 OK"
    data = json.loads(response_body.decode("utf-8"))
    assert data["status_code"] == 200
    assert "healthy" in data["data"]

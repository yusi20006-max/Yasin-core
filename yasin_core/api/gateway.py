import time
import traceback
from typing import Dict, Any, Callable, Tuple, Optional, List
from .models import APIRequest, APIResponse
from .errors import APIError, APIErrorCode
from .auth import BaseAuthenticator, APIKeyAuthenticator


class APIGateway:
    """
    Public API Gateway layer of Yasin-Core.
    Coordinates requests from YasinCLI, Yasin-Agent, YasinHub, and YasinRelay
    and dispatches them to internal Core services.
    """
    def __init__(
        self,
        client,
        authenticator: Optional[BaseAuthenticator] = None,
    ):
        self.client = client
        self.authenticator = authenticator or APIKeyAuthenticator()
        self._routes: Dict[Tuple[str, str], Callable[[APIRequest], APIResponse]] = {}
        self._register_default_routes()

    def register_route(
        self,
        method: str,
        path: str,
        handler: Callable[[APIRequest], APIResponse],
    ) -> None:
        """Register a route handler for a given HTTP method and path."""
        self._routes[(method.upper(), path)] = handler

    def _register_default_routes(self) -> None:
        # Health API
        self.register_route("GET", "/v1/health", self._handle_health)

        # Runtime API
        self.register_route("GET", "/v1/runtime/status", self._handle_runtime_status)
        self.register_route("POST", "/v1/runtime/start", self._handle_runtime_start)
        self.register_route("POST", "/v1/runtime/stop", self._handle_runtime_stop)
        self.register_route("POST", "/v1/runtime/reload", self._handle_runtime_reload)

        # Task API
        self.register_route("POST", "/v1/tasks/create", self._handle_task_create)
        self.register_route("POST", "/v1/tasks/execute", self._handle_task_execute_v1)
        self.register_route("POST", "/v2/tasks/execute", self._handle_task_execute_v2)

        # Memory API
        self.register_route("POST", "/v1/memory/save", self._handle_memory_save_v1)
        self.register_route("POST", "/v2/memory/save", self._handle_memory_save_v2)
        self.register_route("GET", "/v1/memory/get", self._handle_memory_get)

        # Context API
        self.register_route("POST", "/v1/context/create", self._handle_context_create)
        self.register_route("GET", "/v1/context/active", self._handle_context_active)
        self.register_route("GET", "/v1/context/memories", self._handle_context_memories)

        # Plugin API
        self.register_route("GET", "/v1/plugins/list", self._handle_plugin_list)
        self.register_route("GET", "/v1/plugins/status", self._handle_plugin_status)
        self.register_route("POST", "/v1/plugins/load", self._handle_plugin_load)
        self.register_route("POST", "/v1/plugins/unload", self._handle_plugin_unload)
        self.register_route("POST", "/v1/plugins/start", self._handle_plugin_start)
        self.register_route("POST", "/v1/plugins/stop", self._handle_plugin_stop)
        self.register_route("GET", "/v1/plugins/state", self._handle_plugin_state)

        # Event API
        self.register_route("POST", "/v1/events/publish", self._handle_event_publish)

    def handle_request(self, request: APIRequest) -> APIResponse:
        """
        Main request dispatching method. Performs basic request validation,
        runs the configured authenticator, finds the registered handler,
        executes it, and returns a standardized APIResponse.
        """
        # Determine version from path
        version = "v1"
        if request.path.startswith("/v2/"):
            version = "v2"

        try:
            # 1. Basic request validation
            request.validate()

            # 2. Authentication
            self.authenticator.authenticate(request)

            # 3. Route matching
            handler = self._routes.get((request.method, request.path))
            if not handler:
                raise APIError(
                    message=f"Endpoint '{request.method} {request.path}' not found.",
                    code=APIErrorCode.NOT_FOUND,
                    status_code=404,
                )

            # 4. Handler execution
            return handler(request)

        except APIError as e:
            return APIResponse(
                status_code=e.status_code,
                errors=[e.to_dict()],
                version=version,
            )
        except ValueError as e:
            # Catch basic validation/ValueErrors and treat as bad request
            err = APIError(
                message=str(e),
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
            return APIResponse(
                status_code=400,
                errors=[err.to_dict()],
                version=version,
            )
        except Exception as e:
            # Internal Core system error
            err = APIError(
                message=f"An unexpected error occurred: {str(e)}",
                code=APIErrorCode.INTERNAL_SERVER_ERROR,
                status_code=500,
                details={"traceback": traceback.format_exc()},
            )
            return APIResponse(
                status_code=500,
                errors=[err.to_dict()],
                version=version,
            )

    # --- HANDLERS ---

    def _handle_health(self, request: APIRequest) -> APIResponse:
        health_info = self.client.health()
        return APIResponse(status_code=200, data=health_info)

    def _handle_runtime_status(self, request: APIRequest) -> APIResponse:
        status_info = self.client.status()
        return APIResponse(status_code=200, data=status_info)

    def _handle_runtime_start(self, request: APIRequest) -> APIResponse:
        self.client.start()
        return APIResponse(status_code=200, data={"message": "Runtime started successfully."})

    def _handle_runtime_stop(self, request: APIRequest) -> APIResponse:
        self.client.stop()
        return APIResponse(status_code=200, data={"message": "Runtime stopped successfully."})

    def _handle_runtime_reload(self, request: APIRequest) -> APIResponse:
        self.client.reload()
        return APIResponse(status_code=200, data={"message": "Runtime reloaded successfully."})

    def _handle_task_create(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        if "id" not in body or "name" not in body:
            raise APIError(
                message="Missing required fields: 'id' and 'name'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        task = self.client.create_task(
            id=body["id"],
            name=body["name"],
            input_data=body.get("input_data"),
        )
        task_data = {
            "id": task.id,
            "name": task.name,
            "input_data": task.input_data,
            "status": task.status,
            "result": task.result,
            "error": task.error,
        }
        return APIResponse(status_code=201, data=task_data)

    def _handle_task_execute_v1(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        if "id" not in body or "name" not in body:
            raise APIError(
                message="Missing required fields: 'id' and 'name'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        task = self.client.create_task(
            id=body["id"],
            name=body["name"],
            input_data=body.get("input_data"),
        )
        executed = self.client.execute_task(task)
        task_data = {
            "id": executed.id,
            "name": executed.name,
            "status": executed.status,
            "result": executed.result,
            "error": executed.error,
        }
        return APIResponse(status_code=200, data=task_data)

    def _handle_task_execute_v2(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        if "id" not in body or "name" not in body:
            raise APIError(
                message="Missing required fields for v2 execute: 'id' and 'name'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        if not isinstance(body["id"], str) or not isinstance(body["name"], str):
            raise APIError(
                message="'id' and 'name' must be string values.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        task = self.client.create_task(
            id=body["id"],
            name=body["name"],
            input_data=body.get("input_data"),
        )
        start_time = time.time()
        executed = self.client.execute_task(task)
        duration = time.time() - start_time

        task_data = {
            "id": executed.id,
            "name": executed.name,
            "status": executed.status,
            "result": executed.result,
            "error": executed.error,
            "meta": {
                "version": "v2",
                "duration_seconds": duration,
                "input_keys": list(body.get("input_data", {}).keys()) if body.get("input_data") else [],
            }
        }
        return APIResponse(status_code=200, data=task_data, version="v2")

    def _handle_memory_save_v1(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        if "key" not in body or "value" not in body:
            raise APIError(
                message="Missing required fields: 'key' and 'value'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        category = body.get("category", "short-term")
        self.client.save_memory(
            key=body["key"],
            value=body["value"],
            category=category,
            metadata=body.get("metadata"),
            ttl=body.get("ttl"),
        )
        return APIResponse(status_code=200, data={"message": f"Saved key in {category} memory."})

    def _handle_memory_save_v2(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        if "key" not in body or "value" not in body:
            raise APIError(
                message="Missing required fields for v2: 'key' and 'value'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        metadata = body.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise APIError(
                message="'metadata' must be a dictionary in v2.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )

        category = body.get("category", "short-term")
        merged_metadata = dict(metadata) if metadata else {}
        merged_metadata["v2_saved"] = True

        self.client.save_memory(
            key=body["key"],
            value=body["value"],
            category=category,
            metadata=merged_metadata,
            ttl=body.get("ttl"),
        )
        return APIResponse(
            status_code=200,
            data={"message": f"Saved key in {category} memory with v2 metadata tag.", "v2": True},
            version="v2",
        )

    def _handle_memory_get(self, request: APIRequest) -> APIResponse:
        key = request.query_params.get("key")
        if not key:
            raise APIError(
                message="Missing query parameter 'key'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        category = request.query_params.get("category", "short-term")
        val = self.client.get_memory(key=key, category=category)
        return APIResponse(status_code=200, data={"key": key, "value": val, "category": category})

    def _handle_context_create(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        ctx = self.client.context_engine.create_context(
            data=body.get("data"),
            parent_id=body.get("parent_id"),
            metadata=body.get("metadata"),
        )
        return APIResponse(status_code=201, data=ctx.serialize())

    def _handle_context_active(self, request: APIRequest) -> APIResponse:
        from yasin_core.context.manager import get_current_context
        ctx = get_current_context()
        if ctx and hasattr(ctx, "serialize"):
            return APIResponse(status_code=200, data=ctx.serialize())
        elif ctx:
            return APIResponse(status_code=200, data=ctx.to_dict())
        else:
            return APIResponse(status_code=200, data={"message": "No active context found in current thread."})

    def _handle_context_memories(self, request: APIRequest) -> APIResponse:
        context_id = request.query_params.get("context_id")
        if not context_id:
            raise APIError(
                message="Missing query parameter 'context_id'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        memories = self.client.context_engine.retrieve_context_memories(context_id, self.client)
        return APIResponse(status_code=200, data=memories)

    def _handle_plugin_list(self, request: APIRequest) -> APIResponse:
        plugins = self.client.list_plugins()
        return APIResponse(status_code=200, data={"plugins": plugins})

    def _handle_plugin_status(self, request: APIRequest) -> APIResponse:
        status_info = self.client.get_plugin_status()
        return APIResponse(status_code=200, data=status_info)

    def _handle_plugin_load(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        name = body.get("name")
        if not name:
            raise APIError(
                message="Missing required field 'name'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        self.client.load_plugin(name)
        return APIResponse(status_code=200, data={"message": f"Plugin '{name}' loaded successfully."})

    def _handle_plugin_unload(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        name = body.get("name")
        if not name:
            raise APIError(
                message="Missing required field 'name'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        self.client.unload_plugin(name)
        return APIResponse(status_code=200, data={"message": f"Plugin '{name}' unloaded successfully."})

    def _handle_plugin_start(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        name = body.get("name")
        if not name:
            raise APIError(
                message="Missing required field 'name'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        self.client.start_plugin(name)
        return APIResponse(status_code=200, data={"message": f"Plugin '{name}' started successfully."})

    def _handle_plugin_stop(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        name = body.get("name")
        if not name:
            raise APIError(
                message="Missing required field 'name'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        self.client.stop_plugin(name)
        return APIResponse(status_code=200, data={"message": f"Plugin '{name}' stopped successfully."})

    def _handle_plugin_state(self, request: APIRequest) -> APIResponse:
        name = request.query_params.get("name")
        if not name:
            raise APIError(
                message="Missing query parameter 'name'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        state = self.client.get_plugin_state(name)
        return APIResponse(status_code=200, data={"name": name, "state": state})

    def _handle_event_publish(self, request: APIRequest) -> APIResponse:
        body = request.body or {}
        event_name = body.get("event_name")
        payload = body.get("payload")
        if not event_name:
            raise APIError(
                message="Missing required field 'event_name'.",
                code=APIErrorCode.VALIDATION_ERROR,
                status_code=400,
            )
        from yasin_core.events import Event
        event = Event(name=event_name, payload=payload)
        self.client.event_bus.publish(event)
        return APIResponse(status_code=200, data={"message": f"Event '{event_name}' published successfully."})

    def as_wsgi_app(self) -> Callable:
        """
        Exposes the API Gateway as a standard, dependency-free WSGI application callable.
        Perfect for running standard web servers or testing via WebTest.
        """
        import json
        from urllib.parse import parse_qs

        def wsgi_app(environ, start_response):
            path_info = environ.get("PATH_INFO", "/")
            request_method = environ.get("REQUEST_METHOD", "GET")

            # Parse query parameters
            query_string = environ.get("QUERY_STRING", "")
            parsed_query = parse_qs(query_string)
            query_params = {k: v[0] if len(v) == 1 else v for k, v in parsed_query.items()}

            # Parse headers
            headers = {}
            for key, val in environ.items():
                if key.startswith("HTTP_"):
                    header_name = key[5:].replace("_", "-").lower()
                    headers[header_name] = val
                elif key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                    headers[key.replace("_", "-").lower()] = val

            # Parse JSON body if present
            body = None
            try:
                content_length = int(environ.get("CONTENT_LENGTH", 0))
            except ValueError:
                content_length = 0

            if content_length > 0:
                wsgi_input = environ.get("wsgi.input")
                if wsgi_input:
                    body_bytes = wsgi_input.read(content_length)
                    try:
                        body = json.loads(body_bytes.decode("utf-8"))
                    except ValueError:
                        body = None

            # Create APIRequest
            api_request = APIRequest(
                method=request_method,
                path=path_info,
                headers=headers,
                query_params=query_params,
                body=body,
            )

            # Dispatch request
            api_response = self.handle_request(api_request)

            # Format Response
            response_body = json.dumps(api_response.to_dict()).encode("utf-8")
            status_str = f"{api_response.status_code} "
            if api_response.status_code == 200:
                status_str += "OK"
            elif api_response.status_code == 201:
                status_str += "Created"
            elif api_response.status_code == 400:
                status_str += "Bad Request"
            elif api_response.status_code == 401:
                status_str += "Unauthorized"
            elif api_response.status_code == 403:
                status_str += "Forbidden"
            elif api_response.status_code == 404:
                status_str += "Not Found"
            else:
                status_str += "Internal Server Error"

            response_headers = [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(response_body))),
            ]
            start_response(status_str, response_headers)
            return [response_body]

        return wsgi_app

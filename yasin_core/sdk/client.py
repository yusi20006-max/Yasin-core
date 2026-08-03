from typing import Optional, List, Dict, Any
from yasin_core.version import VERSION
from yasin_core.agents import AgentManager, Task, TaskExecutor, BaseAgent
from yasin_core.providers import AIProvider, ProviderManager
from yasin_core.events import EventBus
from yasin_core.plugins import PluginRegistry
from yasin_core.agents.tool import ToolManager, BaseTool
from yasin_core.runtime.registry import RuntimeServiceRegistry
from yasin_core.context.engine import ContextEngine
from yasin_core.context.manager import get_current_context
from yasin_core.di import DIContainer
from yasin_core.config import ConfigurationManager
from yasin_core.storage.base import BaseStorage
from yasin_core.memory import ShortTermMemory, LongTermMemory
from yasin_core.core.orchestrator import RuntimeOrchestrator
from yasin_core.execution import TaskExecutionEngine, Job, ExecutionTask, JobStatus, JobPriority


class YasinCoreClient:

    def __init__(
        self,
        short_term_memory=None,
        long_term_memory=None,
        service_registry=None,
        context_engine=None,
        di_container=None,
        config_manager=None,
        storage=None,
        api_gateway=None,
    ):
        self._version = VERSION
        self._event_bus = EventBus()
        self._agent_manager = AgentManager()
        self._executor = TaskExecutor(agent_manager=self._agent_manager)

        # Link event bus to components
        self._agent_manager.event_bus = self._event_bus
        self._executor.event_bus = self._event_bus

        self._plugin_registry = PluginRegistry(event_bus=self._event_bus)
        self._provider_manager = ProviderManager()
        self._tool_manager = ToolManager()
        self._service_registry = service_registry or RuntimeServiceRegistry()
        self._context_engine = context_engine or ContextEngine()
        self._di_container = di_container or DIContainer()
        self._config_manager = config_manager or ConfigurationManager()
        self._orchestrator = RuntimeOrchestrator(self)
        self._execution = TaskExecutionEngine(self)

        from yasin_core.storage.in_memory import InMemoryStorage
        from yasin_core.memory import (
            InMemoryShortTermMemory,
            InMemoryLongTermMemory,
            StorageBackedLongTermMemory,
        )

        self._storage = storage or InMemoryStorage()
        # Initialize storage
        self._storage.initialize()

        self._short_term_memory = short_term_memory or InMemoryShortTermMemory()
        if long_term_memory is not None:
            self._long_term_memory = long_term_memory
        else:
            if self._storage.metadata.get("persistent", False):
                self._long_term_memory = StorageBackedLongTermMemory(
                    self._storage
                )
            else:
                self._long_term_memory = InMemoryLongTermMemory()

        # Initialize APIGateway
        from yasin_core.api.gateway import APIGateway
        self._api_gateway = api_gateway or APIGateway(self)

        # Register services within the DI Container for clean service composition
        self._di_container.register_instance(YasinCoreClient, self)
        self._di_container.register_instance("client", self)
        self._di_container.register_instance(
            RuntimeServiceRegistry, self._service_registry
        )
        self._di_container.register_instance(
            "service_registry", self._service_registry
        )
        self._di_container.register_instance(
            ContextEngine, self._context_engine
        )
        self._di_container.register_instance(
            "context_engine", self._context_engine
        )
        self._di_container.register_instance("event_bus", self._event_bus)
        self._di_container.register_instance(
            PluginRegistry, self._plugin_registry
        )
        self._di_container.register_instance(
            "plugin_registry", self._plugin_registry
        )
        self._di_container.register_instance(
            ConfigurationManager, self._config_manager
        )
        self._di_container.register_instance("config", self._config_manager)

        # Register new storage instance
        self._di_container.register_instance(BaseStorage, self._storage)
        self._di_container.register_instance("storage", self._storage)

        # Register RuntimeOrchestrator
        self._di_container.register_instance(
            RuntimeOrchestrator, self._orchestrator
        )
        self._di_container.register_instance("orchestrator", self._orchestrator)

        # Register TaskExecutionEngine
        self._di_container.register_instance(
            TaskExecutionEngine, self._execution
        )
        self._di_container.register_instance("execution", self._execution)

        # Register PluginRegistry within RuntimeServiceRegistry
        self._service_registry.register_service(
            name="plugin_registry",
            service=self._plugin_registry,
            version=self._version,
            description="Manages core and third-party plugin lifecycles.",
        )
        self._service_registry.register_service(
            name="execution",
            service=self._execution,
            version=self._version,
            description="Manages unified background task/job execution workflows.",
            dependencies=["config"]
        )
        self._service_registry.register_service(
            name="config",
            service=self._config_manager,
            version=self._version,
            description="Manages ecosystem configuration.",
        )
        self._service_registry.register_service(
            name="storage",
            service=self._storage,
            version=self._version,
            description="Manages ecosystem storage services.",
        )

        # Register Memory services within RuntimeServiceRegistry
        self._service_registry.register_service(
            name="short_term_memory",
            service=self._short_term_memory,
            version=self._version,
            description="Short-term working memory layer."
        )
        self._service_registry.register_service(
            name="long_term_memory",
            service=self._long_term_memory,
            version=self._version,
            description="Long-term semantic/persistent memory layer."
        )

        # Register APIGateway service within RuntimeServiceRegistry
        self._service_registry.register_service(
            name="api_gateway",
            service=self._api_gateway,
            version=self._version,
            description="Unified public API Gateway interface."
        )

    @property
    def di_container(self) -> DIContainer:
        """Access the centralized Dependency Injection Container."""
        return self._di_container

    @property
    def container(self) -> DIContainer:
        """Access the centralized Dependency Injection Container (alias)."""
        return self._di_container

    @property
    def config(self) -> ConfigurationManager:
        """Access the centralized Configuration Manager."""
        return self._config_manager

    @property
    def registry(self) -> RuntimeServiceRegistry:
        """Access the centralized service registry (alias)."""
        return self._service_registry

    @property
    def orchestrator(self) -> RuntimeOrchestrator:
        """Access the Runtime Orchestrator."""
        return self._orchestrator

    @property
    def api_gateway(self):
        """Access the centralized public API Gateway."""
        return self._api_gateway

    def start(self) -> None:
        """Start the orchestrator."""
        self._orchestrator.start()

    def stop(self) -> None:
        """Stop the orchestrator."""
        self._orchestrator.stop()

    def reload(self) -> None:
        """Reload services inside the orchestrator."""
        self._orchestrator.reload()

    def health(self) -> Dict[str, Any]:
        """Check overall health status."""
        return self._orchestrator.health()

    def status(self) -> Dict[str, Any]:
        """Check overall status report."""
        return self._orchestrator.status()

    @property
    def execution(self) -> TaskExecutionEngine:
        """Access the centralized Task Execution Engine."""
        return self._execution

    @property
    def storage(self) -> BaseStorage:
        """Access the centralized Storage provider."""
        return self._storage

    @property
    def version(self) -> str:
        return self._version

    def get_version(self) -> str:
        return self._version

    def info(self) -> dict:
        return self.get_info()

    def get_info(self) -> dict:
        return {"name": "Yasin Core SDK Client", "version": self._version}

    @property
    def event_bus(self) -> EventBus:
        """Access the central event bus."""
        return self._event_bus

    @property
    def service_registry(self) -> RuntimeServiceRegistry:
        """Access the centralized service registry."""
        return self._service_registry

    @property
    def context_engine(self) -> ContextEngine:
        """Access the centralized context engine."""
        return self._context_engine

    @property
    def short_term_memory(self) -> ShortTermMemory:
        """Access short-term memory."""
        return self._short_term_memory

    @property
    def long_term_memory(self) -> LongTermMemory:
        """Access long-term memory."""
        return self._long_term_memory

    # Agent Operations
    def register_agent(self, agent: BaseAgent) -> None:
        """Register a new agent with the internal AgentManager."""
        self._agent_manager.register_agent(agent)

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Retrieve a registered agent by name."""
        return self._agent_manager.get_agent(name)

    def remove_agent(self, name: str) -> Optional[BaseAgent]:
        """Remove a registered agent by name."""
        return self._agent_manager.remove_agent(name)

    def list_agents(self) -> List[str]:
        """List names of all registered agents."""
        return self._agent_manager.list_agents()

    def start_agents(self) -> None:
        """Start all registered agents."""
        self._agent_manager.start_agents()

    def stop_agents(self) -> None:
        """Stop all registered agents."""
        self._agent_manager.stop_agents()

    # Task Operations
    def create_task(
        self, id: str, name: str, input_data: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Create a new Task instance."""
        return Task(id=id, name=name, input_data=input_data)

    def execute_task(self, task: Task) -> Task:
        """Execute the task using the internal TaskExecutor."""
        return self._executor.execute_task(task)

    # Memory Operations
    def save_memory(
        self, key: str, value: Any, category: str = "short-term", metadata: Optional[Dict[str, Any]] = None, ttl: Optional[int] = None
    ) -> None:
        """Save a memory entry into short-term or long-term memory."""
        ctx = get_current_context()
        merged_metadata = dict(metadata) if metadata is not None else {}
        if ctx and hasattr(ctx, "_data"):
            context_id = getattr(ctx, "id", None)
            if context_id:
                merged_metadata["context_id"] = context_id

        if category == "short-term":
            self._short_term_memory.set(key, value, metadata=merged_metadata, ttl=ttl)
        elif category == "long-term":
            self._long_term_memory.set(key, value, metadata=merged_metadata, ttl=ttl)
        else:
            raise ValueError(
                f"Unsupported memory category: {category}. Support: 'short-term' or 'long-term'"
            )

    def get_memory(
        self, key: str, default: Any = None, category: str = "short-term"
    ) -> Any:
        """Retrieve a memory entry from short-term or long-term memory."""
        if category == "short-term":
            return self._short_term_memory.get(key, default)
        elif category == "long-term":
            return self._long_term_memory.get(key, default)
        else:
            raise ValueError(
                f"Unsupported memory category: {category}. Support: 'short-term' or 'long-term'"
            )

    # Context Operations
    def create_context(self, data: Optional[Dict[str, Any]] = None):
        """Create a new execution context."""
        from yasin_core.context import Context

        return Context(data)

    # Provider Operations
    def register_provider(self, provider: AIProvider) -> None:
        """Register a new AI provider."""
        self._provider_manager.register_provider(provider)

    def get_provider(self, name: str) -> Optional[AIProvider]:
        """Retrieve a registered AI provider by name."""
        return self._provider_manager.get_provider(name)

    def list_providers(self) -> List[str]:
        """List names of all registered AI providers."""
        return self._provider_manager.list_providers()

    def generate(self, provider_name: str, prompt: str) -> str:
        """Convenience method to trigger generation on a specific provider."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' is not registered.")
        return provider.generate(prompt)

    # Plugin Operations
    def register_plugin(self, plugin) -> None:
        """Register a plugin instance with the internal PluginRegistry."""
        self._plugin_registry.register(plugin)

    def unregister_plugin(self, name: str) -> None:
        """Unregister a plugin from the internal PluginRegistry."""
        self._plugin_registry.unregister(name)

    def get_plugin(self, name: str):
        """Retrieve a registered plugin by name."""
        return self._plugin_registry.get(name)

    def list_plugins(self) -> List[str]:
        """List names of all registered plugins."""
        return self._plugin_registry.list()

    def discover_plugins(self, plugins_dir: str = "plugins") -> None:
        """Discover and register plugins from the specified directory."""
        self._plugin_registry.discover(plugins_dir)

    def load_plugin(self, name: str) -> None:
        """Load a registered plugin by name."""
        self._plugin_registry.load_plugin(name)

    def unexport_plugin(self, name: str) -> None:
        """Unload a loaded plugin by name."""
        self._plugin_registry.unload_plugin(name)

    def unload_plugin(self, name: str) -> None:
        """Unload a loaded plugin by name."""
        self._plugin_registry.unload_plugin(name)

    def start_plugin(self, name: str) -> None:
        """Start a registered plugin by name."""
        self._plugin_registry.start_plugin(name)

    def stop_plugin(self, name: str) -> None:
        """Stop an active plugin by name."""
        self._plugin_registry.stop_plugin(name)

    def get_plugin_state(self, name: str) -> str:
        """Get the current lifecycle state of a registered plugin."""
        return self._plugin_registry.get_state(name).value

    def get_plugin_status(self) -> Dict[str, Any]:
        """Retrieve status of the plugin registry and registered plugins."""
        return self._plugin_registry.status()

    # Job/Task Execution Operations
    def submit_job(self, job: Job) -> Job:
        """Submit a job to the Task Execution Engine."""
        return self._execution.submit_job(job)

    def create_job(
        self,
        target: Any,
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        name: Optional[str] = None,
        priority: int = 20,
        retries: int = 0,
        timeout: Optional[float] = None,
    ) -> Job:
        """Create and submit a job to the Task Execution Engine."""
        return self._execution.create_job(
            target=target,
            args=args,
            kwargs=kwargs,
            name=name,
            priority=priority,
            retries=retries,
            timeout=timeout,
        )

    def get_job(self, job_id: str) -> Optional[Job]:
        """Retrieve a registered job by ID."""
        return self._execution.get_job(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job."""
        return self._execution.cancel_job(job_id)

    # Tool Operations
    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool instance with the internal ToolManager."""
        self._tool_manager.register_tool(tool)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve a registered tool by name."""
        return self._tool_manager.get_tool(name)

    def remove_tool(self, name: str) -> Optional[BaseTool]:
        """Remove a registered tool by name."""
        return self._tool_manager.remove_tool(name)

    def list_tools(self) -> List[str]:
        """List names of all registered tools."""
        return self._tool_manager.list_tools()

    def execute_tool(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a registered tool by name with arguments."""
        return self._tool_manager.execute_tool(name, *args, **kwargs)

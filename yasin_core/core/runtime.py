from yasin_core.version import VERSION
from yasin_core.utils.logger import get_logger
from yasin_core.runtime.registry import RuntimeServiceRegistry
from yasin_core.context.engine import ContextEngine
from yasin_core.events import EventBus
from yasin_core.di import DIContainer
from yasin_core.config import ConfigurationManager
from yasin_core.core.orchestrator import RuntimeOrchestrator, RuntimeState
from yasin_core.execution import TaskExecutionEngine


class YasinRuntime:

    def __init__(self):

        self.logger = get_logger(
            "CORE"
        )

        self.registry = RuntimeServiceRegistry()
        self.context_engine = ContextEngine()
        self.event_bus = EventBus()
        self.container = DIContainer()
        self.config = ConfigurationManager()
        self.orchestrator = RuntimeOrchestrator(self)
        self.execution = TaskExecutionEngine(self)

        # Register standard runtime components within the DI Container
        self.container.register_instance(DIContainer, self.container)
        self.container.register_instance("container", self.container)
        self.container.register_instance(YasinRuntime, self)
        self.container.register_instance("runtime", self)
        self.container.register_instance(RuntimeServiceRegistry, self.registry)
        self.container.register_instance("registry", self.registry)
        self.container.register_instance(ContextEngine, self.context_engine)
        self.container.register_instance("context_engine", self.context_engine)
        self.container.register_instance(EventBus, self.event_bus)
        self.container.register_instance("event_bus", self.event_bus)
        self.container.register_instance(ConfigurationManager, self.config)
        self.container.register_instance("config", self.config)
        self.container.register_instance(RuntimeOrchestrator, self.orchestrator)
        self.container.register_instance("orchestrator", self.orchestrator)
        self.container.register_instance(TaskExecutionEngine, self.execution)
        self.container.register_instance("execution", self.execution)

        # Register config service in service registry
        self.registry.register_service(
            name="config",
            service=self.config,
            version=VERSION,
            description="Manages core configuration."
        )

        # Register execution service in service registry
        self.registry.register_service(
            name="execution",
            service=self.execution,
            version=VERSION,
            description="Manages unified background task/job execution workflows.",
            dependencies=["config"]
        )


    @property
    def running(self) -> bool:
        return self.orchestrator.state == RuntimeState.RUNNING

    @running.setter
    def running(self, value: bool) -> None:
        pass

    def start(self):

        self.logger.info(
            "Yasin Core Runtime started"
        )

        self.orchestrator.start()


    def stop(self):

        self.logger.info(
            "Yasin Core Runtime stopped"
        )

        self.orchestrator.stop()


    def status(self):

        return {
            "name": "Yasin Core",
            "running": self.running,
            "version": VERSION,
            "registry": self.registry.get_status(),
            "context": self.context_engine.get_status(),
            "di_container": {
                "registered_services": [str(k) for k in self.container._registrations.keys()]
            },
            "orchestrator": self.orchestrator.status()
        }

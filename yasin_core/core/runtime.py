from yasin_core.version import VERSION
from yasin_core.utils.logger import get_logger
from yasin_core.runtime.registry import RuntimeServiceRegistry
from yasin_core.context.engine import ContextEngine
from yasin_core.events import EventBus
from yasin_core.di import DIContainer


class YasinRuntime:

    def __init__(self):

        self.logger = get_logger(
            "CORE"
        )

        self.running = False
        self.registry = RuntimeServiceRegistry()
        self.context_engine = ContextEngine()
        self.event_bus = EventBus()
        self.container = DIContainer()

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


    def start(self):

        self.logger.info(
            "Yasin Core Runtime started"
        )

        self.running = True
        self.registry.initialize_services()


    def stop(self):

        self.logger.info(
            "Yasin Core Runtime stopped"
        )

        self.running = False
        self.registry.shutdown_services()


    def status(self):

        return {
            "name": "Yasin Core",
            "running": self.running,
            "version": VERSION,
            "registry": self.registry.get_status(),
            "context": self.context_engine.get_status(),
            "di_container": {
                "registered_services": [str(k) for k in self.container._registrations.keys()]
            }
        }

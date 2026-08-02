from yasin_core.version import VERSION
from yasin_core.utils.logger import get_logger
from yasin_core.runtime.registry import RuntimeServiceRegistry
from yasin_core.context.engine import ContextEngine


class YasinRuntime:

    def __init__(self):

        self.logger = get_logger(
            "CORE"
        )

        self.running = False
        self.registry = RuntimeServiceRegistry()
        self.context_engine = ContextEngine()


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
            "context": self.context_engine.get_status()
        }

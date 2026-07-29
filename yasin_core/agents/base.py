from abc import ABC, abstractmethod
from yasin_core.agents.task import Task


class BaseAgent(ABC):


    def __init__(self, name: str, description: str = ""):

        self.name = name

        self.description = description

        self.running = False


    def start(self):

        self.running = True


    def stop(self):

        self.running = False


    @abstractmethod
    def execute(self, task: Task):

        pass

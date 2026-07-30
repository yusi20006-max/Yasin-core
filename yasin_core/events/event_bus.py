# Progress: [ ] 75%

AGENT_REGISTERED = "agent_registered"
AGENT_REMOVED = "agent_removed"
AGENT_STARTED = "agent_started"
AGENT_STOPPED = "agent_stopped"
TASK_STARTED = "task_started"
TASK_COMPLETED = "task_completed"
TASK_FAILED = "task_failed"


class EventBus:

    def __init__(self):
        self.listeners = {}

    def subscribe(self, event, callback):
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)

    def publish(self, event, data=None):
        handlers = self.listeners.get(event, [])
        for handler in handlers:
            handler(data)

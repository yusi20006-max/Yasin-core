from typing import Optional, Any
from yasin_core.agents.task import Task
from yasin_core.agents.planner import Planner, SimplePlanner
from yasin_core.agents.manager import AgentManager
from yasin_core.utils.logger import get_logger
from yasin_core.events import (
    AGENT_STARTED,
    TASK_STARTED,
    TASK_COMPLETED,
    TASK_FAILED,
)


class TaskExecutor:
    def __init__(
        self,
        agent_manager: AgentManager,
        planner: Optional[Planner] = None,
        event_bus: Optional[Any] = None
    ):
        self.agent_manager = agent_manager
        self.planner = planner if planner is not None else SimplePlanner()
        self.event_bus = event_bus
        self.logger = get_logger("TASK-EXECUTOR")
        self.event_bus = None

    def execute_task(self, task: Task) -> Task:
        self.logger.info(f"Starting execution of task: {task.id} ({task.name})")
        task.status = "running"
        if self.event_bus:
            from yasin_core.sdk import TASK_STARTED
            self.event_bus.publish(TASK_STARTED, {
                "task_id": task.id,
                "task_name": task.name,
                "task": task.to_dict()
            })
        try:
            # 1. Planner generates execution plan
            plan = self.planner.plan(task)
            agent_name = plan.get("agent_name")
            payload = plan.get("payload", {})

            if not agent_name:
                raise ValueError("Planner could not determine target agent name.")

            # 2. Executor retrieves agent from Manager
            agent = self.agent_manager.get_agent(agent_name)
            if not agent:
                raise ValueError(f"Agent '{agent_name}' not found.")

            # Ensure agent is running/started
            if not agent.running:
                agent.start()
                if self.event_bus:
                    from yasin_core.sdk import AGENT_STARTED
                    self.event_bus.publish(AGENT_STARTED, {"agent_name": agent_name})

            # 3. Agent executes the action
            result = agent.execute(payload)

            # 4. Result update
            task.result = result
            task.status = "completed"
            self.logger.info(f"Task {task.id} completed successfully.")
            if self.event_bus:
                from yasin_core.sdk import TASK_COMPLETED
                self.event_bus.publish(TASK_COMPLETED, {
                    "task_id": task.id,
                    "task_name": task.name,
                    "result": result,
                    "task": task.to_dict()
                })

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self.logger.error(f"Task {task.id} failed: {e}")
            if self.event_bus:
                from yasin_core.sdk import TASK_FAILED
                self.event_bus.publish(TASK_FAILED, {
                    "task_id": task.id,
                    "task_name": task.name,
                    "error": str(e),
                    "task": task.to_dict()
                })

        return task


# Alias for backward/flexible compatibility
Executor = TaskExecutor

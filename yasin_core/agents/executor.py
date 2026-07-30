from typing import Optional
from yasin_core.agents.task import Task
from yasin_core.agents.planner import Planner, SimplePlanner
from yasin_core.agents.manager import AgentManager
from yasin_core.utils.logger import get_logger


class TaskExecutor:
    def __init__(
        self,
        agent_manager: AgentManager,
        planner: Optional[Planner] = None
    ):
        self.agent_manager = agent_manager
        self.planner = planner if planner is not None else SimplePlanner()
        self.logger = get_logger("TASK-EXECUTOR")

    def execute_task(self, task: Task) -> Task:
        self.logger.info(f"Starting execution of task: {task.id} ({task.name})")
        task.status = "running"
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

            # 3. Agent executes the action
            result = agent.execute(payload)

            # 4. Result update
            task.result = result
            task.status = "completed"
            self.logger.info(f"Task {task.id} completed successfully.")

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            self.logger.error(f"Task {task.id} failed: {e}")

        return task


# Alias for backward/flexible compatibility
Executor = TaskExecutor

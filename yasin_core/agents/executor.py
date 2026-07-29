from yasin_core.agents.task import Task
from yasin_core.agents.manager import AgentManager


class TaskExecutor:


    def __init__(self):

        pass


    def execute(self, task: Task, agent_manager: AgentManager) -> Task:

        task.status = "running"

        agent_name = task.input_data.get("agent_name")


        if not agent_name:

            task.status = "failed"

            task.error = "No agent assigned to the task"

            return task


        agent = agent_manager.get_agent(agent_name)


        if not agent:

            task.status = "failed"

            task.error = f"Agent '{agent_name}' not found"

            return task


        if not agent.running:

            task.status = "failed"

            task.error = f"Agent '{agent_name}' is not running"

            return task


        try:

            result = agent.execute(task)

            task.result = result

            task.status = "completed"

        except Exception as e:

            task.status = "failed"

            task.error = str(e)


        return task

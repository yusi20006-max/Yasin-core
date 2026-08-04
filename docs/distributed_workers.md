# Distributed Worker Architecture Foundation

Yasin-Core v2.7 introduces the foundation of a **Distributed Worker Architecture**. This foundation enables central execution management while allowing tasks, workloads, and agent executions to be processed across isolated, dynamic, and potentially remote worker components.

---

## Key Capabilities

1. **Worker Interface Definition**: Provides the abstract base class `BaseDistributedWorker` and metadata model `WorkerNode` for implementing modular, isolated execution nodes.
2. **Worker Lifecycle Management**: Supports structured state transitions: `REGISTERED`, `ACTIVE`, `SUSPENDED`, `OFFLINE`, `FAILED`. Workers can be started, stopped, paused, and resumed.
3. **Centralized Registration & Discovery**: Allows worker nodes to register dynamically with a centralized `DistributedWorkerManager` service, exposing their capabilities.
4. **Heartbeat & Monitoring**: Centralized monitoring detects stale heartbeats, transitioning inactive nodes to `SUSPENDED` and then `OFFLINE`.
5. **Task Assignment & Routing**: Supports direct manual task assignment (`worker_id`) and automated load-balanced capability matching (`assign_job_by_capability`), with seamless fallback to the local thread pool.
6. **Failure Recovery**: Automatically recovers outstanding queued/running jobs of offline workers, re-routing or re-enqueuing them back to the central execution engine.
7. **Ecosystem Integration**: Fully integrated into the **Task Execution Engine**, **Event Bus** (for worker events), and **Observability & Metrics** subsystem.

---

## Architecture Design

```
                     +---------------------------------------+
                     |            YasinCoreClient            |
                     +-------------------+-------------------+
                                         |
            +----------------------------+----------------------------+
            |                                                         |
            v                                                         v
+-----------------------+                                  +--------------------+
|  TaskExecutionEngine  |                                  |   Event Bus &      |
+-----------+-----------+                                  |   Observability    |
            |                                              +---------^----------+
            | (If assigned/capability-constrained)                   |
            v                                                        |
+---------------------------+                                        |
| DistributedWorkerManager  +----------------------------------------+
+-----------+---------------+ (Publishes state / records metrics)
            |
            | (Dispatches/Routes Jobs)
            v
   +-----------------+
   |   WorkerNode    | <-----+ (Heartbeats, Status, & Pulling Jobs)
   +-----------------+       |
                             |
                  +----------+-----------+
                  | BaseDistributedWorker|
                  | (Isolated Runner)    |
                  +----------------------+
```

---

## SDK API Reference

Public classes and enums exported from `yasin_core.sdk`:

### `WorkerState` (Enum)
Defines the lifecycle state of a worker:
- `REGISTERED`: Registered with the manager but not yet active.
- `ACTIVE`: Active and ready to accept/process workloads.
- `SUSPENDED`: Temporarily paused or experiencing stale heartbeats.
- `OFFLINE`: Gracefully shut down or declared dead due to missed heartbeats.
- `FAILED`: Experienced critical execution failure.

### `DistributedWorkerManager` (Service)
Coordinates worker nodes and task delegation:
- `register_worker(worker_id, name, capabilities, health)`: Registers a worker node.
- `unregister_worker(worker_id)`: Gracefully removes a worker node.
- `get_worker(worker_id)`: Retrieves a worker node by its unique ID.
- `list_workers(status)`: Lists registered worker nodes.
- `discover_workers(capability)`: Finds active workers supporting a given capability.
- `send_heartbeat(worker_id, health)`: Submits worker heartbeat.
- `assign_job(job_id, worker_id)`: Explicitly routes a job to a specific worker.
- `assign_job_by_capability(job)`: Automatically matches a job to a suitable healthy worker node using load balancing.
- `report_job_status(worker_id, job_id, status, result, error)`: Updates central job execution progress/completion.

### `BaseDistributedWorker` (Runner)
Base class to run isolated worker nodes:
- `start()`: Initializes and registers the worker. Starts heartbeat and job polling threads.
- `stop()`: Shuts down the worker, unregisters it from the manager, and stops threads.
- `pause()`: Pauses job execution and heartbeats.
- `resume()`: Resumes job execution and heartbeats.
- `send_heartbeat()`: Manually triggers heartbeat emission.

---

## Example Usage

### 1. Initializing and Running an Isolated Worker

```python
from yasin_core.sdk import YasinCoreClient, BaseDistributedWorker

# Initialize Client
client = YasinCoreClient()
client.start()

# Initialize worker matching specialized capabilities
worker = BaseDistributedWorker(
    name="agent-runner-worker",
    manager=client.worker_manager,
    capabilities=["run_agent", "text_generation"],
    heartbeat_interval=1.0
)

# Start worker (registers and starts polling)
worker.start()
```

### 2. Submitting Capability-Constrained Tasks

```python
from yasin_core.sdk import Job

# Create a Job with capability requirements
job = Job(
    target="my_agent_name",
    kwargs={"required_capability": "run_agent"}
)

# Submit Job centrally
client.submit_job(job)

# Under the hood, TaskExecutionEngine detects "run_agent" capability requirement,
# matches it to "agent-runner-worker", and delegates execution to it.
```

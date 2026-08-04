# Scheduler & Background Jobs System

Yasin-Core features a robust, centralized, thread-safe, and modular **Scheduler and Background Jobs System** (`yasin_core.execution.scheduler.Scheduler`) for orchestrating periodic tasks, delayed jobs, and automated workflows across the Yasin AI Ecosystem.

---

## Architecture Overview

The Yasin-Core Scheduler is designed to decouple **scheduling determination** from **job execution**.

1. **Scheduling Logic**: The `Scheduler` monitors registered `ScheduledJob`s on sub-second intervals. It calculates `next_run_time` dynamically based on configured triggers (periodic, delay, or cron-like pattern).
2. **Execution delegation**: When a job becomes due, the `Scheduler` triggers it by submitting/enqueuing it directly to the `TaskExecutionEngine`.
3. **Execution Workers**: The existing thread-pool workers inside the `TaskExecutionEngine` fetch the job, managing its actual runtime, timeouts, cooperative cancellations, and retries.
4. **Persistence**: Active scheduled jobs are serialized and written dynamically to the configured ecosystem `BaseStorage` backend, enabling transparent recovery across system reboots.
5. **Auditing and Events**: Every lifecycle transition (scheduled, triggered, unscheduled) is published as structured events to the central `EventBus`.

```
                    ┌─────────────────────────┐
                    │     YasinCoreClient     │
                    └───────────┬─────────────┘
                                │
                      (SDK calls / API Gateway)
                                │
                                ▼
         ┌───────────────────────────────────────────────┐
         │               Scheduler Service               │
         │  - Tracks activeScheduledJobs                 │
         │  - Background polling thread                  │
         │  - Handles Cron, Interval, and Delay triggers │
         │  - Serializes schedules to BaseStorage        │
         └──────────────────────┬────────────────────────┘
                                │
                  (When job execution is due)
                                │
                                ▼
         ┌───────────────────────────────────────────────┐
         │             TaskExecutionEngine               │
         │  - Thread-pool worker execution               │
         │  - Handles retry, timeout, cancellation       │
         │  - Dispatches EventBus notifications          │
         └───────────────────────────────────────────────┘
```

---

## Core Models

### `ScheduledJob`
Represents a job registered in the Scheduler. Includes fields:
* `id` (`str`): Unique identifier of the job (auto-generated UUID if not specified).
* `name` (`str`): Descriptive name of the job.
* `target` (`Union[Callable, str]`): Target workload to run. Can be a python callable, or a string referencing a registered Agent or Plugin name.
* `interval` (`Optional[float]`): Recurrence period in seconds.
* `delay` (`Optional[float]`): Run-once delay in seconds.
* `cron` (`Optional[str]`): A standard 5-field crontab pattern (`minute hour day month day_of_week`).
* `max_runs` (`Optional[int]`): Maximum number of execution counts before the schedule finishes.
* `run_count` (`int`): Number of times this job has been triggered.
* `last_run_time` (`Optional[float]`): Absolute UNIX timestamp of the last triggered run.
* `next_run_time` (`Optional[float]`): Absolute UNIX timestamp of the next execution run.

---

## Usage Guide

The scheduling capabilities are directly exposed via public properties and methods on `YasinCoreClient`.

### 1. Scheduling a Periodic Job
Runs a function periodically at a set interval:

```python
from yasin_core.sdk import YasinCoreClient

client = YasinCoreClient()
client.start()  # Starts execution engine and scheduler services

def maintenance_task():
    print("Running database cleanup...")

# Runs every 10 minutes (600 seconds)
job = client.schedule_job(
    target=maintenance_task,
    interval=600.0,
    name="db_cleanup"
)

print(f"Scheduled job: {job.id}, Next run: {job.next_run_time}")
```

### 2. Scheduling a Delayed/One-off Job
Runs a function once after a specified delay:

```python
# Runs once after a 30 second delay
client.schedule_job(
    target="agent_name_or_plugin_name",
    delay=30.0,
    name="delayed_alert"
)
```

### 3. Scheduling a Cron-Style Job
Supports standard crontab configurations dynamically parsed in Python:

```python
# Runs at 2:30 AM every day
client.schedule_job(
    target="sample_plugin",
    cron="30 2 * * *",
    name="nightly_backup"
)
```

### 4. Job Cancellation (Unschedule)
Stop and remove a scheduled job from the engine:

```python
# Cancel by ID
client.scheduler.unschedule_job(job.id)
```

---

## Public APIs

### `YasinCoreClient` Helper
* `client.schedule_job(...)`: Schedules a new job and registers it with the centralized scheduler. Returns a `ScheduledJob` instance.

### `Scheduler` Property (`client.scheduler`)
* `schedule_job(...)`: Schedules a job.
* `unschedule_job(job_id: str)`: Unschedules a job. Returns `True` if found and cancelled.
* `get_job(job_id: str)`: Retrieves a `ScheduledJob` by its ID.
* `list_jobs()`: Returns a list of all tracked `ScheduledJob`s.
* `clear_jobs()`: Clears completed or cancelled one-off jobs.
* `health()`: Returns structured service health.
* `status()`: Returns service execution and metrics status.

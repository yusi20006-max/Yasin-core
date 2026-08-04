import time
from datetime import datetime, timedelta
import pytest
from unittest.mock import MagicMock, patch

from yasin_core.sdk import YasinCoreClient, Scheduler, ScheduledJob
from yasin_core.execution.models import JobPriority
from yasin_core.execution.scheduler import (
    parse_cron_field,
    get_next_cron_time,
    serialize_target,
    deserialize_target,
)
from yasin_core.events import Event


# Dummy target functions for test
def dummy_task():
    return "done"


def dummy_task_with_args(a, b):
    return a + b


def test_cron_field_parsing():
    assert parse_cron_field("*", 0, 5) == {0, 1, 2, 3, 4, 5}
    assert parse_cron_field("1-3", 0, 5) == {1, 2, 3}
    assert parse_cron_field("*/2", 0, 6) == {0, 2, 4, 6}
    assert parse_cron_field("1,3,5", 0, 10) == {1, 3, 5}
    assert parse_cron_field("1-5/2", 0, 10) == {1, 3, 5}


def test_next_cron_time_calculation():
    base = datetime(2026, 8, 1, 12, 0, 0)

    # Every minute: next minute
    next_time = get_next_cron_time("* * * * *", base)
    assert next_time == datetime(2026, 8, 1, 12, 1, 0)

    # Specific hour and minute
    next_time = get_next_cron_time("30 14 * * *", base)
    assert next_time == datetime(2026, 8, 1, 14, 30, 0)

    # Step minutes
    next_time = get_next_cron_time("*/15 * * * *", base)
    assert next_time == datetime(2026, 8, 1, 12, 15, 0)


def test_target_serialization_deserialization():
    ser_str = serialize_target("some_agent")
    assert ser_str == {"type": "str", "val": "some_agent"}
    assert deserialize_target(ser_str) == "some_agent"

    ser_call = serialize_target(dummy_task)
    assert ser_call["type"] == "callable"
    assert ser_call["name"] == "dummy_task"
    assert deserialize_target(ser_call) == dummy_task


def test_scheduled_job_initialization():
    # Test periodic job next run calculation
    job = ScheduledJob(target=dummy_task, interval=10.0)
    assert job.next_run_time is not None
    assert job.next_run_time > time.time()
    assert job.interval == 10.0

    # Test delayed job next run calculation
    job_delayed = ScheduledJob(target=dummy_task, delay=5.0)
    assert job_delayed.next_run_time is not None
    assert abs(job_delayed.next_run_time - (time.time() + 5.0)) < 1.0


def test_scheduler_lifecycle():
    client = YasinCoreClient()
    scheduler = client.scheduler

    assert not scheduler.health()["healthy"]

    # Start scheduler (this starts the background thread)
    scheduler.initialize()
    assert scheduler.health()["healthy"]
    assert scheduler.status()["state"] == "active"

    # Shutdown scheduler
    scheduler.shutdown()
    assert not scheduler.health()["healthy"]
    assert scheduler.status()["state"] == "inactive"


def test_scheduler_add_and_remove_jobs():
    client = YasinCoreClient()
    scheduler = client.scheduler

    # Schedule a job
    job = scheduler.schedule_job(
        target=dummy_task,
        interval=60.0,
        name="test-periodic-job",
        priority=JobPriority.HIGH,
    )

    assert job.id in scheduler._jobs
    assert scheduler.get_job(job.id) == job
    assert len(scheduler.list_jobs()) == 1

    # Unschedule the job
    success = scheduler.unschedule_job(job.id)
    assert success
    assert job.id not in scheduler._jobs
    assert len(scheduler.list_jobs()) == 0


def test_scheduler_delayed_and_one_off_execution():
    client = YasinCoreClient()
    scheduler = client.scheduler
    client.start()  # This starts execution engine & scheduler

    # Track triggers on execution engine
    execution_mock = MagicMock()
    client._execution = execution_mock

    # Schedule a one-off job with 0 delay (immediate execution on next tick)
    job = scheduler.schedule_job(target=dummy_task, delay=0.01)

    # Let the scheduler tick run
    time.sleep(0.3)

    # Verify job was submitted to the Task Execution Engine
    assert execution_mock.submit_job.called
    assert job.run_count == 1
    assert job.next_run_time is None  # Delayed job doesn't run again

    client.stop()


def test_scheduler_periodic_execution():
    client = YasinCoreClient()
    scheduler = client.scheduler
    client.start()

    # Track triggers on execution engine
    execution_mock = MagicMock()
    client._execution = execution_mock

    # Schedule a periodic job with very short interval (0.05 seconds)
    job = scheduler.schedule_job(target=dummy_task, interval=0.05)

    # Let scheduler run for some ticks
    time.sleep(0.25)

    # Verify it ran multiple times
    assert execution_mock.submit_job.call_count >= 2
    assert job.run_count >= 2
    assert job.next_run_time is not None

    client.stop()


def test_scheduler_max_runs_constraint():
    client = YasinCoreClient()
    scheduler = client.scheduler
    client.start()

    # Track triggers on execution engine
    execution_mock = MagicMock()
    client._execution = execution_mock

    # Schedule a periodic job with max_runs limit
    job = scheduler.schedule_job(target=dummy_task, interval=0.05, max_runs=2)

    # Let scheduler run
    time.sleep(0.3)

    # Verify it only ran max_runs times and next_run_time is None
    assert execution_mock.submit_job.call_count == 2
    assert job.run_count == 2
    assert job.next_run_time is None

    client.stop()


def test_scheduler_job_cancellation():
    client = YasinCoreClient()
    scheduler = client.scheduler
    client.start()

    execution_mock = MagicMock()
    client._execution = execution_mock

    # Schedule periodic job
    job = scheduler.schedule_job(target=dummy_task, interval=0.05)

    # Cancel immediately
    scheduler.unschedule_job(job.id)

    time.sleep(0.15)

    # Verify it never triggered
    assert execution_mock.submit_job.call_count == 0

    client.stop()


def test_scheduler_persistence():
    client = YasinCoreClient()
    storage = client.storage

    scheduler = client.scheduler

    # Schedule some persistent jobs
    job1 = scheduler.schedule_job(target="some_agent_name", interval=60.0, name="job-1")
    job2 = scheduler.schedule_job(target=dummy_task, cron="* * * * *", name="job-2")

    # Verify state saved in storage
    saved_schedule = storage.get("scheduler:schedule")
    assert saved_schedule is not None
    assert job1.id in saved_schedule
    assert job2.id in saved_schedule

    # Create a new scheduler instance simulating reboot
    new_scheduler = Scheduler(client)
    new_scheduler.initialize()

    # Verify jobs were successfully re-loaded from storage
    loaded_job1 = new_scheduler.get_job(job1.id)
    loaded_job2 = new_scheduler.get_job(job2.id)

    assert loaded_job1 is not None
    assert loaded_job1.name == "job-1"
    assert loaded_job1.target == "some_agent_name"
    assert loaded_job1.interval == 60.0

    assert loaded_job2 is not None
    assert loaded_job2.name == "job-2"
    assert loaded_job2.target == dummy_task
    assert loaded_job2.cron == "* * * * *"

    new_scheduler.shutdown()


def test_scheduler_event_bus_publishing():
    client = YasinCoreClient()
    scheduler = client.scheduler

    events = []

    def on_event(event_name, event):
        events.append((event_name, event))

    client.event_bus.subscribe("job_scheduled", lambda ev: on_event("job_scheduled", ev))
    client.event_bus.subscribe("job_triggered", lambda ev: on_event("job_triggered", ev))
    client.event_bus.subscribe("job_unscheduled", lambda ev: on_event("job_unscheduled", ev))

    client.start()

    # Schedule job
    job = scheduler.schedule_job(target=dummy_task, delay=0.01)

    time.sleep(0.15)

    # Unschedule
    scheduler.unschedule_job(job.id)

    # Verify all event states published correctly
    published_names = [name for name, _ in events]
    assert "job_scheduled" in published_names
    assert "job_triggered" in published_names
    assert "job_unscheduled" in published_names

    client.stop()

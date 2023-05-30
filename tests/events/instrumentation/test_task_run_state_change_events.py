from prefect import flow, task
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker


async def test_task_state_change_happy_path(
    asserting_events_worker: EventsWorker,
    reset_worker_events,
    prefect_client,
):
    @task
    def happy_little_tree():
        return "🌳"

    @flow
    def happy_path():
        return happy_little_tree._run()

    flow_state = happy_path._run()

    task_state = await flow_state.result()
    task_run_id = task_state.state_details.task_run_id
    task_run = await prefect_client.read_task_run(task_run_id)
    task_run_states = await prefect_client.read_task_run_states(task_run_id)

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(task_run_states) == len(asserting_events_worker._client.events) == 3

    last_state = None
    for i, task_run_state in enumerate(task_run_states):
        event = asserting_events_worker._client.events[i]

        assert event.id == task_run_state.id
        assert event.occurred == task_run_state.timestamp
        assert event.event == f"prefect.task-run.{task_run_state.name}"
        assert event.payload == {
            "intended": {
                "from": str(last_state.type.value) if last_state else None,
                "to": str(task_run_state.type.value) if task_run_state else None,
            },
            "initial_state": (
                {
                    "type": last_state.type.value,
                    "name": last_state.name,
                    "message": last_state.message or "",
                }
                if last_state
                else None
            ),
            "validated_state": {
                "type": task_run_state.type.value,
                "name": task_run_state.name,
                "message": task_run_state.message or "",
            },
        }
        assert event.follows == (last_state.id if last_state else None)
        assert dict(event.resource.items()) == {
            "prefect.resource.id": f"prefect.task-run.{task_run.id}",
            "prefect.resource.name": task_run.name,
            "prefect.state-message": task_run_state.message or "",
            "prefect.state-name": task_run_state.name,
            "prefect.state-timestamp": task_run_state.timestamp.isoformat(),
            "prefect.state-type": str(task_run_state.type.value),
        }

        last_state = task_run_state


async def test_task_state_change_task_failure(
    asserting_events_worker: EventsWorker,
    reset_worker_events,
    prefect_client,
):
    @task
    def happy_little_tree():
        raise ValueError("Here's a happy little accident.")

    @flow
    def happy_path():
        return happy_little_tree._run()

    flow_state = happy_path._run()

    task_state = await flow_state.result(raise_on_failure=False)
    task_run_id = task_state.state_details.task_run_id
    task_run = await prefect_client.read_task_run(task_run_id)
    task_run_states = await prefect_client.read_task_run_states(task_run_id)

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(task_run_states) == len(asserting_events_worker._client.events) == 3

    last_state = None
    for i, task_run_state in enumerate(task_run_states):
        event = asserting_events_worker._client.events[i]

        assert event.id == task_run_state.id
        assert event.occurred == task_run_state.timestamp
        assert event.event == f"prefect.task-run.{task_run_state.name}"
        assert event.payload == {
            "intended": {
                "from": str(last_state.type.value) if last_state else None,
                "to": str(task_run_state.type.value) if task_run_state else None,
            },
            "initial_state": (
                {
                    "type": last_state.type.value,
                    "name": last_state.name,
                    "message": last_state.message or "",
                }
                if last_state
                else None
            ),
            "validated_state": {
                "type": task_run_state.type.value,
                "name": task_run_state.name,
                "message": task_run_state.message or "",
            },
        }
        assert event.follows == (last_state.id if last_state else None)
        assert dict(event.resource.items()) == {
            "prefect.resource.id": f"prefect.task-run.{task_run.id}",
            "prefect.resource.name": task_run.name,
            "prefect.state-message": task_run_state.message or "",
            "prefect.state-name": task_run_state.name,
            "prefect.state-timestamp": task_run_state.timestamp.isoformat(),
            "prefect.state-type": str(task_run_state.type.value),
        }

        last_state = task_run_state

"""
Tests for `FlowRunView`
"""
import pendulum
import pytest
import logging
from datetime import timedelta
from unittest.mock import MagicMock

from prefect.backend import FlowRunView, TaskRunView
from prefect.backend.flow_run import (
    FlowRunLog,
    check_for_compatible_agents,
    watch_flow_run,
)
from prefect.engine.state import Scheduled, Success, Running, Submitted
from prefect.run_configs import UniversalRun


FLOW_RUN_DATA_1 = {
    "id": "id-1",
    "name": "name-1",
    "flow_id": "flow_id-1",
    "serialized_state": Success(message="state-1").serialize(),
    "states": [
        {
            "timestamp": pendulum.now().subtract(seconds=10).isoformat(),
            "serialized_state": Running(message="past-state").serialize(),
        },
        {
            "timestamp": pendulum.now().subtract(seconds=20).isoformat(),
            "serialized_state": Submitted(message="past-state").serialize(),
        },
    ],
    "parameters": {"param": "value"},
    "context": {"foo": "bar"},
    "labels": ["label"],
    "updated": pendulum.now().isoformat(),
    "run_config": UniversalRun().serialize(),
}
FLOW_RUN_DATA_2 = {
    "id": "id-2",
    "name": "name-2",
    "flow_id": "flow_id-2",
    "serialized_state": Success(message="state-2").serialize(),
    "states": [
        {
            "timestamp": pendulum.now().subtract(seconds=10).isoformat(),
            "serialized_state": Running(message="past-state").serialize(),
        },
        {
            "timestamp": pendulum.now().subtract(seconds=20).isoformat(),
            "serialized_state": Submitted(message="past-state").serialize(),
        },
    ],
    "parameters": {"param": "value2"},
    "context": {"bar": "foo"},
    "labels": ["label2"],
    "updated": pendulum.now().isoformat(),
    "run_config": UniversalRun().serialize(),
}
FLOW_RUN_DATA_NULL_STATE = {
    "id": "id-null",
    "name": "name-null",
    "flow_id": "flow_id-null",
    "serialized_state": None,
    "parameters": {},
    "context": {},
    "labels": [],
    "updated": pendulum.now().isoformat(),
    "run_config": UniversalRun().serialize(),
}

TASK_RUN_DATA_FINISHED = {
    "id": "task-run-id-1",
    "name": "name-1",
    "task": {"id": "task-id-1", "slug": "task-slug-1"},
    "map_index": "map_index-1",
    "serialized_state": Success(message="state-1").serialize(),
    "flow_run_id": "flow_run_id-1",
}
TASK_RUN_DATA_RUNNING = {
    "id": "task-run-id-2",
    "name": "name-2",
    "task": {"id": "task-id-2", "slug": "task-slug-2"},
    "map_index": "map_index-2",
    "serialized_state": Running(message="state-2").serialize(),
    "flow_run_id": "flow_run_id-2",
}
TASK_RUN_DATA_RUNNING_NOW_FINISHED = {
    "id": "task-run-id-2",
    "name": "name-2",
    "task": {"id": "task-id-2", "slug": "task-slug-2"},
    "map_index": "map_index-2",
    "serialized_state": Success(message="state-1").serialize(),
    "flow_run_id": "flow_run_id-2",
}


def test_flow_run_view_query_for_flow_run_raises_bad_responses(patch_post):
    patch_post({})

    with pytest.raises(ValueError, match="bad result while querying for flow runs"):
        FlowRunView._query_for_flow_run(where={})


def test_flow_run_view_query_for_flow_run_raises_when_not_found(patch_post):
    patch_post({"data": {"flow_run": []}})

    with pytest.raises(ValueError, match="No flow runs found"):
        FlowRunView._query_for_flow_run(where={})


def test_flow_run_view_query_for_flow_run_errors_on_multiple_flow_runs(patch_post):
    patch_post({"data": {"flow_run": [1, 2]}})

    with pytest.raises(ValueError, match=r"multiple \(2\) flow runs"):
        FlowRunView._query_for_flow_run(where={})


def test_flow_run_view_query_for_flow_run_unpacks_result_singleton(patch_post):
    patch_post({"data": {"flow_run": [1]}})

    assert FlowRunView._query_for_flow_run(where={}) == 1


def test_flow_run_view_query_for_flow_run_uses_where_in_query(monkeypatch):
    post = MagicMock(return_value={"data": {"flow_run": [FLOW_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    FlowRunView._query_for_flow_run(where={"foo": {"_eq": "bar"}})

    assert (
        'flow_run(where: { foo: { _eq: "bar" } })'
        in post.call_args[1]["params"]["query"]
    )


def test_flow_run_view_query_for_flow_run_includes_all_required_data(monkeypatch):
    graphql = MagicMock(return_value={"data": {"flow_run": [FLOW_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.graphql", graphql)

    FlowRunView._query_for_flow_run(where={})

    query_dict = graphql.call_args[0][0]
    selection_set = query_dict["query"]["flow_run(where: {})"]
    assert selection_set == {
        "id": True,
        "name": True,
        "serialized_state": True,
        "states": {"serialized_state", "timestamp"},
        "flow_id": True,
        "context": True,
        "parameters": True,
        "labels": True,
        "updated": True,
        "run_config": True,
    }


@pytest.mark.parametrize("from_method", ["flow_run_id", "flow_run_data"])
def test_flow_run_view_from_returns_instance(patch_post, from_method):
    patch_post({"data": {"flow_run": [FLOW_RUN_DATA_1]}})

    if from_method == "flow_run_id":
        flow_run = FlowRunView.from_flow_run_id("id-1", load_static_tasks=False)
    elif from_method == "flow_run_data":
        # Note the post patch will not be used since there is no query here
        flow_run = FlowRunView._from_flow_run_data(FLOW_RUN_DATA_1)

    assert flow_run.flow_run_id == "id-1"
    assert flow_run.name == "name-1"
    assert flow_run.flow_id == "flow_id-1"
    assert flow_run.parameters == {"param": "value"}
    assert flow_run.context == {"foo": "bar"}
    assert flow_run.labels == ["label"]
    assert isinstance(flow_run.run_config, UniversalRun)
    assert isinstance(flow_run.updated_at, pendulum.DateTime)
    # This state is deserialized at initialization
    assert flow_run.state == Success(message="state-1")
    # Assert that past states are in timestamp sorted order and deserialized
    assert flow_run.states[0].is_submitted()
    assert flow_run.states[1].is_running()
    for state in flow_run.states:
        assert isinstance(state.timestamp, pendulum.DateTime)
        assert state.message == "past-state"
    # There are no cached tasks
    assert flow_run._cached_task_runs == {}


def test_flow_run_view_from_flow_run_data_fills_empty_state_with_pending():
    flow_run = FlowRunView._from_flow_run_data(FLOW_RUN_DATA_NULL_STATE)
    assert flow_run.state.is_pending()


def test_flow_run_view_from_returns_instance_with_loaded_static_tasks(
    patch_posts,
):
    patch_posts(
        [
            {"data": {"flow_run": [FLOW_RUN_DATA_1]}},
            {"data": {"task_run": [TASK_RUN_DATA_FINISHED, TASK_RUN_DATA_RUNNING]}},
        ]
    )

    flow_run = FlowRunView.from_flow_run_id("id-1", load_static_tasks=True)

    assert flow_run.flow_run_id == "id-1"
    assert flow_run.name == "name-1"
    assert flow_run.flow_id == "flow_id-1"
    # This state is deserialized at initialization
    assert flow_run.state == Success(message="state-1")

    # Only the finished task is cached
    assert len(flow_run._cached_task_runs) == 1
    assert flow_run._cached_task_runs[
        "task-run-id-1"
    ] == TaskRunView._from_task_run_data(TASK_RUN_DATA_FINISHED)


def test_flow_run_view_get_all_task_runs(patch_post, patch_posts):
    patch_posts(
        [
            {"data": {"flow_run": [FLOW_RUN_DATA_1]}},
            {"data": {"task_run": [TASK_RUN_DATA_FINISHED]}},
        ]
    )
    flow_run = FlowRunView.from_flow_run_id("fake-id")

    patch_post({"data": {"task_run": [TASK_RUN_DATA_FINISHED, TASK_RUN_DATA_RUNNING]}})
    tr = flow_run.get_all_task_runs()
    assert len(flow_run._cached_task_runs) == 1
    assert len(tr) == 2

    patch_post({"data": {"task_run": [TASK_RUN_DATA_RUNNING_NOW_FINISHED]}})
    tr = flow_run.get_all_task_runs()
    assert len(flow_run._cached_task_runs) == 2
    assert len(tr) == 2


def test_flow_run_view_get_latest_returns_new_instance(patch_post, patch_posts):
    patch_posts(
        [
            {"data": {"flow_run": [FLOW_RUN_DATA_1]}},
            {"data": {"task_run": [TASK_RUN_DATA_FINISHED, TASK_RUN_DATA_RUNNING]}},
        ]
    )

    flow_run = FlowRunView.from_flow_run_id("fake-id", load_static_tasks=True)

    patch_post({"data": {"flow_run": [FLOW_RUN_DATA_2]}})

    flow_run_2 = flow_run.get_latest()

    # Assert we have not mutated the original flow run object
    assert flow_run.flow_run_id == "id-1"
    assert flow_run.name == "name-1"
    assert flow_run.flow_id == "flow_id-1"
    assert flow_run.state == Success(message="state-1")
    assert flow_run.parameters == {"param": "value"}
    assert flow_run.context == {"foo": "bar"}
    assert flow_run.labels == ["label"]
    assert isinstance(flow_run.updated_at, pendulum.DateTime)
    assert len(flow_run._cached_task_runs) == 1
    assert flow_run._cached_task_runs[
        "task-run-id-1"
    ] == TaskRunView._from_task_run_data(TASK_RUN_DATA_FINISHED)

    # Assert the new object has the data returned by the query
    # In reality, the flow run ids and such would match because that's how the lookup
    # is done
    assert flow_run_2.flow_run_id == "id-2"
    assert flow_run_2.name == "name-2"
    assert flow_run_2.flow_id == "flow_id-2"
    assert flow_run_2.state == Success(message="state-2")
    assert flow_run_2.parameters == {"param": "value2"}
    assert flow_run_2.context == {"bar": "foo"}
    assert flow_run_2.labels == ["label2"]

    # Cached task runs are transferred
    assert len(flow_run._cached_task_runs) == 1
    assert flow_run._cached_task_runs[
        "task-run-id-1"
    ] == TaskRunView._from_task_run_data(TASK_RUN_DATA_FINISHED)


def test_flow_run_view_from_flow_run_id_where_clause(monkeypatch):
    post = MagicMock(return_value={"data": {"flow_run": [FLOW_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    FlowRunView.from_flow_run_id(flow_run_id="id-1", load_static_tasks=False)

    assert (
        'flow_run(where: { id: { _eq: "id-1" } })'
        in post.call_args[1]["params"]["query"]
    )


def test_check_for_compatible_agents_no_agents_returned(patch_post):
    patch_post(
        {"data": {"agent": []}},
    )

    result = check_for_compatible_agents([])
    assert "no healthy agents" in result


def test_flow_run_view_get_logs(monkeypatch):
    post = MagicMock(return_value={"data": {"flow_run": [FLOW_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    flow_run_view = FlowRunView._from_flow_run_data(FLOW_RUN_DATA_1)

    flow_run_view.get_logs()

    query = post.call_args[1]["params"]["query"]

    assert (
        'flow_run(where: { id: { _eq: "id-1" } })' in query
    ), "Queries for the correct flow run"

    assert (
        "logs(order_by: { timestamp: asc }" in query
    ), "Retrieves logs, orders ascending"
    assert (
        'where: { _and: [{ timestamp: { _lte: "%s" } }, {}] }'
        % flow_run_view.updated_at.isoformat()
        in query
    ), ("Where is less than the last time the flow run was updated\n" + query)


def test_flow_run_view_get_logs_start_and_end_times(monkeypatch):
    post = MagicMock(return_value={"data": {"flow_run": [FLOW_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    flow_run_view = FlowRunView._from_flow_run_data(FLOW_RUN_DATA_1)

    start = pendulum.now()
    end = pendulum.now()

    flow_run_view.get_logs(start_time=start, end_time=end)

    query = post.call_args[1]["params"]["query"]

    assert 'flow_run(where: { id: { _eq: "id-1" } })' in query
    assert "logs(order_by: { timestamp: asc }" in query

    #
    assert (
        'where: { _and: [{ timestamp: { _lte: "%s" } }, { timestamp: { _gt: "%s" } }]'
        % (end.isoformat(), start.isoformat())
        in query
    ), ("Where includes start and end time bounds\n" + query)


def test_check_for_compatible_agents_healthy_without_matching_labels(patch_post):
    patch_post(
        {
            "data": {
                "agent": [
                    {
                        "id": "id-1",
                        "name": "name-1",
                        "labels": ["label-1", "label-2"],
                        "last_queried": pendulum.now().isoformat(),
                    }
                ]
            }
        },
    )

    result = check_for_compatible_agents([])
    assert "1 healthy agent" in result
    assert "do not have an agent with empty labels" in result


def test_check_for_compatible_agents_no_healthy_no_matching_unhealthy(patch_post):
    patch_post(
        {
            "data": {
                "agent": [
                    {
                        "id": "id-1",
                        "name": "name-1",
                        "labels": [],
                        "last_queried": pendulum.now().subtract(minutes=5).isoformat(),
                    }
                ]
            }
        },
    )

    result = check_for_compatible_agents(["x"])
    assert "no healthy agents in your tenant" in result
    assert "Start an agent with labels {'x'}" in result


def test_check_for_compatible_agents_matching_labels_in_single_unhealthy(patch_post):
    patch_post(
        {
            "data": {
                "agent": [
                    {
                        "id": "id-1",
                        "name": "name-1",
                        "labels": [],
                        "last_queried": pendulum.now().subtract(minutes=5).isoformat(),
                    }
                ]
            }
        },
    )

    result = check_for_compatible_agents([])
    assert (
        "Agent id-1 (name-1) has matching labels and last queried 5 minutes ago"
        in result
    )


def test_check_for_compatible_agents_matching_labels_in_multiple_unhealthy(patch_post):
    patch_post(
        {
            "data": {
                "agent": [
                    {
                        "id": "id-1",
                        "name": "name-1",
                        "labels": ["x"],
                        "last_queried": pendulum.now().subtract(minutes=5).isoformat(),
                    },
                    {
                        "id": "id-2",
                        "name": "name-2",
                        "labels": ["x"],
                        "last_queried": pendulum.now().subtract(minutes=5).isoformat(),
                    },
                ]
            }
        },
    )

    result = check_for_compatible_agents(["x"])
    assert "2 agents with matching labels but they have not queried recently" in result
    assert "start a new agent with labels {'x'}" in result


def test_check_for_compatible_agents_matching_labels_in_single_healthy(patch_post):
    patch_post(
        {
            "data": {
                "agent": [
                    {
                        "id": "id-1",
                        "name": "name-1",
                        "labels": ["x"],
                        "last_queried": pendulum.now().subtract(seconds=20).isoformat(),
                    }
                ]
            }
        },
    )

    result = check_for_compatible_agents(["x"])
    assert (
        "Agent id-1 (name-1) has matching labels and last queried 20 seconds ago. "
        "It should deploy your flow run."
    ) in result


def test_check_for_compatible_agents_matching_labels_in_multiple_unhealthy(patch_post):
    patch_post(
        {
            "data": {
                "agent": [
                    {
                        "id": "id-1",
                        "name": "name-1",
                        "labels": ["x"],
                        "last_queried": pendulum.now().isoformat(),
                    },
                    {
                        "id": "id-2",
                        "name": "name-2",
                        "labels": ["x"],
                        "last_queried": pendulum.now().isoformat(),
                    },
                ]
            }
        },
    )

    result = check_for_compatible_agents(["x"])
    assert (
        "Found 2 healthy agents with matching labels. One of them should pick up your flow"
        in result
    )


def test_watch_flow_run_already_finished(patch_post):
    data = FLOW_RUN_DATA_1.copy()
    # Change the updated timestamp for the "ago" message
    data["updated"] = pendulum.now().subtract(minutes=5).isoformat()
    patch_post({"data": {"flow_run": [data]}})

    logs = [log for log in watch_flow_run("id")]
    assert len(logs) == 1
    log = logs[0]
    assert log.message == "Your flow run finished 5 minutes ago"
    assert log.level == logging.INFO


def test_watch_flow_run(monkeypatch):
    flow_run = FlowRunView._from_flow_run_data(FLOW_RUN_DATA_1)
    flow_run.state = Scheduled()  # Not running
    flow_run.states = []
    flow_run.get_latest = MagicMock(return_value=flow_run)
    flow_run.get_logs = MagicMock()

    MockView = MagicMock()
    MockView.from_flow_run_id.return_value = flow_run

    monkeypatch.setattr("prefect.backend.flow_run.FlowRunView", MockView)
    monkeypatch.setattr(
        "prefect.backend.flow_run.check_for_compatible_agents",
        MagicMock(return_value="Helpful agent message."),
    )

    # Mock sleep so that we do not have a slow test
    monkeypatch.setattr("prefect.backend.flow_run.time.sleep", MagicMock())

    for i, log in enumerate(watch_flow_run("id")):
        # Assert that we get the agent warning a couple times then update the state
        if i == 0:
            assert log.message == (
                "It has been 15 seconds and your flow run has not been submitted by an agent. "
                "Helpful agent message."
            )
            assert log.level == logging.WARNING

        elif i == 1:
            assert log.message == (
                "It has been 50 seconds and your flow run has not been submitted by an agent. "
                "Helpful agent message."
            )

            # Mark the flow run as finished and give it a few past states to log
            # If this test times out, we did not reach this log
            flow_run.state = Success()
            scheduled = Scheduled("My message")
            scheduled.timestamp = pendulum.now()
            running = Running("Another message")
            running.timestamp = pendulum.now().add(seconds=10)

            # Given intentionally out of order states to prove sorting
            flow_run.states = [running, scheduled]

            # Add a log between the states and a log at the end
            flow_run.get_logs = MagicMock(
                return_value=[
                    FlowRunLog(
                        timestamp=pendulum.now().add(seconds=5),
                        message="Foo",
                        level=logging.DEBUG,
                    ),
                    FlowRunLog(
                        timestamp=pendulum.now().add(seconds=15),
                        message="Bar",
                        level=logging.ERROR,
                    ),
                ]
            )

        elif i == 2:
            assert log.message == "Entered state <Scheduled>: My message"
            assert log.level == logging.INFO
        elif i == 3:
            assert log.message == "Foo"
            assert log.level == logging.DEBUG
        elif i == 4:
            assert log.message == "Entered state <Running>: Another message"
            assert log.level == logging.INFO
        elif i == 5:
            assert log.message == "Bar"
            assert log.level == logging.ERROR

    assert i == 5  # Assert we saw all of the expected logs


def test_watch_flow_run_default_timeout(monkeypatch):
    flow_run = FlowRunView._from_flow_run_data(FLOW_RUN_DATA_1)
    flow_run.state = Running()  # Not finished
    flow_run.get_latest = MagicMock(return_value=flow_run)
    flow_run.get_logs = MagicMock()

    MockView = MagicMock()
    MockView.from_flow_run_id.return_value = flow_run

    monkeypatch.setattr("prefect.backend.flow_run.FlowRunView", MockView)

    # Mock sleep so that we do not have a slow test
    monkeypatch.setattr("prefect.backend.flow_run.time.sleep", MagicMock())

    with pytest.raises(RuntimeError, match="timed out after 12.0 hours of waiting"):
        for log in watch_flow_run("id"):
            pass


def test_watch_flow_run_timeout(monkeypatch):
    flow_run = FlowRunView._from_flow_run_data(FLOW_RUN_DATA_1)
    flow_run.state = Running()  # Not finished
    flow_run.get_latest = MagicMock(return_value=flow_run)
    flow_run.get_logs = MagicMock()

    MockView = MagicMock()
    MockView.from_flow_run_id.return_value = flow_run

    monkeypatch.setattr("prefect.backend.flow_run.FlowRunView", MockView)

    # Mock sleep so that we do not have a slow test
    monkeypatch.setattr("prefect.backend.flow_run.time.sleep", MagicMock())

    with pytest.raises(RuntimeError, match="timed out after 36.5 hours of waiting"):
        for log in watch_flow_run(
            "id", max_duration=timedelta(days=1, hours=12.5, seconds=1)
        ):
            pass


def test_flow_run_view_handles_null_run_config():
    flow_run_data = FLOW_RUN_DATA_1.copy()
    flow_run_data["run_config"] = None
    flow_run_view = FlowRunView._from_flow_run_data(flow_run_data)
    assert flow_run_view.run_config is None

"""
Tests for `TaskRunView`
"""
import pytest

from prefect.backend.task_run import NotLoaded
from prefect.backend import TaskRunView
from unittest.mock import MagicMock
from prefect.utilities.graphql import EnumValue
from prefect.engine.state import Success
from prefect.engine.results import LocalResult


TASK_RUN_DATA_1 = {
    "id": "id-1",
    "name": "name-1",
    "task": {"id": "task-id-1", "slug": "task-slug-1"},
    "map_index": "map_index-1",
    "serialized_state": Success(message="state-1").serialize(),
    "flow_run_id": "flow_run_id-1",
}
TASK_RUN_DATA_2 = {
    "id": "id-2",
    "name": "name-2",
    "task": {"id": "task-id-2", "slug": "task-slug-2"},
    "map_index": "map_index-2",
    "serialized_state": Success(message="state-2").serialize(),
    "flow_run_id": "flow_run_id-2",
}


def test_task_run_view_query_for_task_runs_raises_bad_responses(patch_post):
    patch_post({})

    with pytest.raises(ValueError, match="bad result while querying for task runs"):
        TaskRunView.query_for_task_runs(where={})


def test_task_run_view_query_for_task_runs_raises_when_not_found(patch_post):
    patch_post({"data": {"task_run": []}})

    with pytest.raises(ValueError, match="No task runs found"):
        TaskRunView.query_for_task_runs(where={})


def test_task_run_view_query_for_task_runs_allows_return_when_not_found(patch_post):
    patch_post({"data": {"task_run": []}})

    assert TaskRunView.query_for_task_runs(where={}, error_on_empty=False) == []


def test_task_run_view_query_for_task_runs_allows_returns_all_task_run_data(patch_post):
    patch_post({"data": {"task_run": [1, 2]}})

    assert TaskRunView.query_for_task_runs(where={}) == [1, 2]


def test_task_run_view_query_for_task_runs_uses_where_in_query(monkeypatch):
    post = MagicMock(return_value={"data": {"task_run": [TASK_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    TaskRunView.query_for_task_runs(where={"foo": {"_eq": "bar"}})

    assert (
        'task_run(where: { foo: { _eq: "bar" } })'
        in post.call_args[1]["params"]["query"]
    )


def test_task_run_view_query_for_task_runs_uses_order_by_in_query(monkeypatch):
    post = MagicMock(return_value={"data": {"task_run": [TASK_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    TaskRunView.query_for_task_runs(where={}, order_by={"foo": EnumValue("asc")})

    assert (
        "task_run(where: {}, order_by: { foo: asc })"
        in post.call_args[1]["params"]["query"]
    )


def test_task_run_view_query_for_task_runs_includes_all_required_data(monkeypatch):
    graphql = MagicMock(return_value={"data": {"task_run": [TASK_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.graphql", graphql)

    TaskRunView.query_for_task_runs(where={})

    query_dict = graphql.call_args[0][0]
    selection_set = query_dict["query"]["task_run(where: {})"]
    assert selection_set == {
        "id": True,
        "name": True,
        "task": {"id": True, "slug": True},
        "map_index": True,
        "serialized_state": True,
        "flow_run_id": True,
    }


def test_task_run_view_query_for_task_run_errors_on_multiple_task_runs(patch_post):
    patch_post({"data": {"task_run": [1, 2]}})

    with pytest.raises(ValueError, match=r"multiple \(2\) task runs"):
        TaskRunView.query_for_task_run(where={})


def test_task_run_view_query_for_task_run_unpacks_singleton_result(patch_post):
    patch_post({"data": {"task_run": [1]}})

    assert TaskRunView.query_for_task_run(where={}) == 1


@pytest.mark.parametrize("from_method", ["task_run_id", "task_slug", "task_data"])
def test_task_run_view_from_returns_instance(patch_post, from_method):
    patch_post({"data": {"task_run": [TASK_RUN_DATA_1]}})

    if from_method == "task_slug":
        task_run = TaskRunView.from_task_slug("fake-slug", "fake-flow-run-id")
    elif from_method == "task_run_id":
        task_run = TaskRunView.from_task_run_id("fake-id")
    elif from_method == "task_data":
        # Note the post patch will not be used since there is no query here
        task_run = TaskRunView.from_task_run_data(TASK_RUN_DATA_1)

    assert task_run.task_run_id == "id-1"
    assert task_run.name == "name-1"
    assert task_run.task_id == "task-id-1"
    assert task_run.task_slug == "task-slug-1"
    assert task_run.map_index == "map_index-1"
    # This state is deserialized at initialization
    assert task_run.state == Success(message="state-1")


def test_task_run_view_get_latest_returns_new_instance(patch_post):

    task_run = TaskRunView.from_task_run_data(TASK_RUN_DATA_1)

    patch_post({"data": {"task_run": [TASK_RUN_DATA_2]}})

    task_run_2 = task_run.get_latest()

    # Assert we have not mutated the original task run object
    assert task_run.task_run_id == "id-1"
    assert task_run.name == "name-1"
    assert task_run.task_id == "task-id-1"
    assert task_run.task_slug == "task-slug-1"
    assert task_run.map_index == "map_index-1"
    assert task_run.state == Success(message="state-1")

    # Assert the new object has the data returned by the query
    # In reality, the task run ids and such would match because that's how the lookup
    # is done
    assert task_run_2.task_run_id == "id-2"
    assert task_run_2.name == "name-2"
    assert task_run_2.task_id == "task-id-2"
    assert task_run_2.task_slug == "task-slug-2"
    assert task_run_2.map_index == "map_index-2"
    assert task_run_2.state == Success(message="state-2")


def test_task_run_view_from_task_run_id_where_clause(monkeypatch):
    post = MagicMock(return_value={"data": {"task_run": [TASK_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    TaskRunView.from_task_run_id(task_run_id="id-1")

    assert (
        'task_run(where: { id: { _eq: "id-1" } })'
        in post.call_args[1]["params"]["query"]
    )


def test_task_run_view_from_task_slug_where_clause(monkeypatch):
    post = MagicMock(return_value={"data": {"task_run": [TASK_RUN_DATA_1]}})
    monkeypatch.setattr("prefect.client.client.Client.post", post)

    TaskRunView.from_task_slug(task_slug="task-slug-1", flow_run_id="flow-run-id-1")

    assert (
        "task_run(where: { "
        'task: { slug: { _eq: "task-slug-1" } }, '
        'flow_run_id: { _eq: "flow-run-id-1" }, '
        "map_index: { _eq: -1 } "
        "})"
    ) in post.call_args[1]["params"]["query"]


@pytest.mark.parametrize("result_value", [None, "hello-world"])
def test_task_run_view_result_loads_result_data(tmpdir, result_value):
    result = LocalResult(dir=tmpdir).write(result_value)

    # Instantiate a very minimal task run view
    task_run = TaskRunView(
        task_run_id=None,
        task_id=None,
        task_slug=None,
        name=None,
        state=Success(result=result),
        map_index=-1,
        flow_run_id=None,
    )

    # Result is not loaded yet
    assert task_run._result is NotLoaded
    assert "result=<not loaded>" in repr(task_run)

    # The result is loaded
    assert task_run.result == result_value

    # Future calls are cached
    assert task_run._result == result_value
    assert task_run.result is task_run.result

    # Displays in the repr now
    assert f"result={result_value!r}" in repr(task_run)

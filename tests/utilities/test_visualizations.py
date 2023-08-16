import pytest
from unittest.mock import MagicMock
from prefect import task, flow


@task(viz_return_value=-10)
def sync_task_a():
    return "Sync Result A"


@task
def sync_task_b(input_data):
    return f"Sync Result B from {input_data}"


@task
async def async_task_a():
    return "Async Result A"


@task
async def async_task_b(input_data):
    return f"Async Result B from {input_data}"


@task(viz_return_value=5)
def untrackable_task_result():
    return "Untrackable Task Result"


@flow
def simple_sync_flow():
    a = sync_task_a()
    sync_task_b(a)


@flow
async def flow_with_mixed_tasks():
    a = sync_task_a()
    await async_task_b(a)
    a = sync_task_a()


@flow
async def simple_async_flow_with_async_tasks():
    a = await async_task_a()
    await async_task_b(a)


@flow
async def simple_async_flow_with_sync_tasks():
    a = sync_task_a()
    sync_task_b(a)


@flow
async def async_flow_with_subflow():
    await async_task_a()
    await simple_async_flow_with_sync_tasks()


@flow
def flow_with_task_interaction():
    a = sync_task_a()
    b = a + 1
    sync_task_b(b)


@flow
def flow_with_flow_params(x=1):
    a = sync_task_a()
    b = a + x
    sync_task_b(b)


@flow
def flow_with_untrackable_task_result():
    res = untrackable_task_result()
    sync_task_b(res)


@pytest.mark.parametrize(
    "test_flow",
    [
        simple_sync_flow,
        simple_async_flow_with_async_tasks,
        simple_async_flow_with_sync_tasks,
        async_flow_with_subflow,
        flow_with_task_interaction,
        flow_with_mixed_tasks,
        flow_with_untrackable_task_result,
        flow_with_flow_params,
    ],
)
def test_visualize_does_not_raise(test_flow, monkeypatch):
    monkeypatch.setattr(
        "prefect.flows.visualize_task_dependencies", MagicMock(return_value=None)
    )

    test_flow.visualize()


@pytest.mark.parametrize(
    "test_flow, expected_nodes",
    [
        (
            simple_sync_flow,
            {
                '\t"sync_task_b-0"\n',
                '\t"sync_task_a-0"\n',
                '\t"sync_task_a-0" -> "sync_task_b-0"\n',
            },
        ),
    ],
)
def test_visualize_graph_contents(test_flow, expected_nodes, monkeypatch):
    mock_visualize = MagicMock(return_value=None)
    monkeypatch.setattr("prefect.flows.visualize_task_dependencies", mock_visualize)

    test_flow.visualize()
    graph = mock_visualize.call_args[0][0]

    actual_nodes = set(graph.body)

    assert (
        actual_nodes == expected_nodes
    ), f"Expected nodes {expected_nodes} but found {actual_nodes}"

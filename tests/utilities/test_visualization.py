from unittest.mock import MagicMock, Mock

import pytest

from prefect import flow, task
from prefect.utilities.visualization import (
    TaskVizTracker,
    VisualizationUnsupportedError,
    VizTask,
    _track_viz_task,
    get_task_viz_tracker,
)


class TestTaskVizTracker:
    async def test_get_task_run_tracker(self):
        with TaskVizTracker() as tracker:
            tracker_in_ctx = get_task_viz_tracker()
            assert tracker_in_ctx
            assert id(tracker) == id(tracker_in_ctx)

    async def test_get_task_run_tracker_outside_ctx(self):
        tracker_outside_ctx = get_task_viz_tracker()
        assert not tracker_outside_ctx

        with TaskVizTracker() as _:
            pass

        tracker_outside_ctx = get_task_viz_tracker()
        assert not tracker_outside_ctx

    async def test_add_task(self):
        with TaskVizTracker() as tracker:
            assert len(tracker.tasks) == 0

            tracker.add_task(VizTask("my_task"))
            assert len(tracker.tasks) == 1
            assert tracker.tasks[0].name == "my_task-0"

            tracker.add_task(VizTask("my_task"))
            assert len(tracker.tasks) == 2
            assert tracker.tasks[1].name == "my_task-1"

            tracker.add_task(VizTask("my_other_task"))
            assert len(tracker.tasks) == 3
            assert tracker.tasks[2].name == "my_other_task-0"

    @pytest.mark.parametrize(
        "trackable",
        [
            ("my_return_value", True),
            ([1, 2, 3], True),
            (500, True),
            (None, False),
            (1, False),
        ],
    )
    async def test_link_viz_return_value_to_viz_task(self, trackable):
        value, is_trackable = trackable
        with TaskVizTracker() as tracker:
            trackable_task = VizTask("my_task")
            tracker.link_viz_return_value_to_viz_task(value, trackable_task)
            if is_trackable:
                assert tracker.object_id_to_task[id(value)] == trackable_task
            else:
                assert id(value) not in tracker.object_id_to_task


class TestTrackTaskRun:
    async def test_track_task_run_outside_ctx(self, monkeypatch):
        mock = Mock()
        monkeypatch.setattr(
            "prefect.utilities.visualization.TaskVizTracker.add_task", mock
        )
        _track_viz_task(
            "my_task",
            {"a": 1},
        )
        assert mock.call_count == 0

    async def test_track_task_run_in_ctx(self, monkeypatch):
        mock = Mock()
        monkeypatch.setattr(
            "prefect.utilities.visualization.TaskVizTracker.add_task", mock
        )
        with TaskVizTracker():
            _track_viz_task(
                "my_task",
                {"a": 1},
            )
            assert mock.call_count == 1

    async def test_track_task_run(self):
        with TaskVizTracker() as tracker:
            res = _track_viz_task("my_task", {"a": 1})
            assert isinstance(res, VizTask)
            assert res.name == "my_task-0"
            assert res.upstream_tasks == []

            assert len(tracker.tasks) == 1
            assert res == tracker.tasks[0]

    async def test_track_task_run_with_upstream_task(self):
        with TaskVizTracker() as tracker:
            upstream_task = VizTask("upstream_task")
            _track_viz_task("my_task", {"a": upstream_task})

            assert len(tracker.tasks) == 1
            tracked_task = tracker.tasks[0]
            assert tracked_task.name == "my_task-0"
            assert len(tracked_task.upstream_tasks) == 1
            assert upstream_task in tracked_task.upstream_tasks

    async def test_track_task_run_returns_viz_return_value(self):
        s = "my_return_value"

        with TaskVizTracker():
            res = _track_viz_task(
                "upstream_task_with_value", {"a": 1}, viz_return_value=s
            )
            assert res == s
            assert id(res) == id(s)

    async def test_track_task_run_links_upstream_obj(self):
        s = "my_return_value"

        with TaskVizTracker() as tracker:
            _track_viz_task("upstream_task_with_value", {"a": 1}, viz_return_value=s)

            assert len(tracker.tasks) == 1
            assert len(tracker.object_id_to_task) == 1
            assert tracker.tasks[0].name == "upstream_task_with_value-0"
            assert tracker.tasks[0].upstream_tasks == []

            _track_viz_task("my_task", {"a": s})

            assert len(tracker.tasks) == 2
            assert len(tracker.object_id_to_task) == 1
            assert tracker.tasks[1].name == "my_task-0"
            assert tracker.tasks[1].upstream_tasks == [tracker.tasks[0]]


async def test_flow_visualize_doesnt_support_task_map():
    @task
    def add_one(n):
        return n + 1

    @flow
    def add_flow():
        add_one.map([1, 2, 3])

    with pytest.raises(VisualizationUnsupportedError, match="task.map()"):
        await add_flow.visualize()


async def test_flow_visualize_doesnt_support_task_apply_async():
    @task
    def add_one(n):
        return n + 1

    @flow
    def add_flow():
        add_one.apply_async(1)

    with pytest.raises(VisualizationUnsupportedError, match="task.apply_async()"):
        await add_flow.visualize()


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
    a = sync_task_a()
    await simple_async_flow_with_sync_tasks()
    sync_task_b(a)


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


class TestFlowVisualise:
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
    def test_visualize_does_not_raise(self, test_flow, monkeypatch):
        monkeypatch.setattr(
            "prefect.utilities.visualization.visualize_task_dependencies",
            MagicMock(return_value=None),
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
            (
                simple_async_flow_with_async_tasks,
                {
                    '\t"async_task_a-0"\n',
                    '\t"async_task_b-0"\n',
                    '\t"async_task_a-0" -> "async_task_b-0"\n',
                },
            ),
            (
                simple_async_flow_with_sync_tasks,
                {
                    '\t"sync_task_a-0"\n',
                    '\t"sync_task_b-0"\n',
                    '\t"sync_task_a-0" -> "sync_task_b-0"\n',
                },
            ),
            (
                async_flow_with_subflow,
                {
                    '\t"sync_task_a-0" -> "sync_task_b-0"\n',
                    '\t"sync_task_b-0"\n',
                    '\t"simple-async-flow-with-sync-tasks-0"\n',
                    '\t"sync_task_a-0"\n',
                },
            ),
            (
                flow_with_task_interaction,
                {
                    '\t"sync_task_a-0"\n',
                    '\t"sync_task_b-0"\n',
                },
            ),
            (
                flow_with_mixed_tasks,
                {
                    '\t"sync_task_a-0"\n',
                    '\t"async_task_b-0"\n',
                    '\t"sync_task_a-1"\n',
                    '\t"sync_task_a-0" -> "async_task_b-0"\n',
                },
            ),
            (
                flow_with_untrackable_task_result,
                {
                    '\t"untrackable_task_result-0"\n',
                    '\t"sync_task_b-0"\n',
                },
            ),
            (
                flow_with_flow_params,
                {
                    '\t"sync_task_a-0"\n',
                    '\t"sync_task_b-0"\n',
                },
            ),
        ],
    )
    async def test_visualize_graph_contents(
        self, test_flow, expected_nodes, monkeypatch
    ):
        mock_visualize = MagicMock(return_value=None)
        monkeypatch.setattr(
            "prefect.utilities.visualization.visualize_task_dependencies",
            mock_visualize,
        )

        await test_flow.visualize()
        graph = mock_visualize.call_args[0][0]

        actual_nodes = set(graph.body)

        assert actual_nodes == expected_nodes, (
            f"Expected nodes {expected_nodes} but found {actual_nodes}"
        )

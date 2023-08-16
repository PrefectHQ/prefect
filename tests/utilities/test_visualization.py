import pytest
from unittest.mock import Mock
from prefect.utilities.visualization import (
    TaskRunTracker,
    TrackableTask,
    track_task_run,
    get_task_run_tracker,
)


class TestTaskRunTracker:
    async def test_get_task_run_tracker(self):
        with TaskRunTracker() as tracker:
            tracker_in_ctx = get_task_run_tracker()
            assert tracker_in_ctx
            assert id(tracker) == id(tracker_in_ctx)

    async def test_get_task_run_tracker_outside_ctx(self):
        tracker_outside_ctx = get_task_run_tracker()
        assert not tracker_outside_ctx

        with TaskRunTracker() as _:
            pass

        tracker_outside_ctx = get_task_run_tracker()
        assert not tracker_outside_ctx

    async def test_add_trackable_task(self):
        with TaskRunTracker() as tracker:
            assert len(tracker.tasks) == 0

            tracker.add_trackable_task(TrackableTask("my_task"))
            assert len(tracker.tasks) == 1
            assert tracker.tasks[0].name == "my_task-0"

            tracker.add_trackable_task(TrackableTask("my_task"))
            assert len(tracker.tasks) == 2
            assert tracker.tasks[1].name == "my_task-1"

            tracker.add_trackable_task(TrackableTask("my_other_task"))
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
    async def test_link_viz_return_value_to_trackable_task(self, trackable):
        value, is_trackable = trackable
        with TaskRunTracker() as tracker:
            trackable_task = TrackableTask("my_task")
            tracker.link_viz_return_value_to_trackable_task(value, trackable_task)
            if is_trackable:
                assert tracker.object_id_to_task[id(value)] == trackable_task
            else:
                assert id(value) not in tracker.object_id_to_task


class TestTrackTaskRun:
    async def test_track_task_run_outside_ctx(self, monkeypatch):
        mock = Mock()
        monkeypatch.setattr(
            "prefect.utilities.visualization.TaskRunTracker.add_trackable_task", mock
        )
        track_task_run(
            "my_task",
            {"a": 1},
        )
        assert mock.call_count == 0

    async def test_track_task_run_in_ctx(self, monkeypatch):
        mock = Mock()
        monkeypatch.setattr(
            "prefect.utilities.visualization.TaskRunTracker.add_trackable_task", mock
        )
        with TaskRunTracker():
            track_task_run(
                "my_task",
                {"a": 1},
            )
            assert mock.call_count == 1

    async def test_track_task_run(self):
        with TaskRunTracker() as tracker:
            res = track_task_run("my_task", {"a": 1})
            assert isinstance(res, TrackableTask)
            assert res.name == "my_task-0"
            assert res.upstream_tasks == []

            assert len(tracker.tasks) == 1
            assert res == tracker.tasks[0]

    async def test_track_task_run_with_upstream_task(self):
        with TaskRunTracker() as tracker:
            upstream_task = TrackableTask("upstream_task")
            track_task_run("my_task", {"a": upstream_task})

            assert len(tracker.tasks) == 1
            tracked_task = tracker.tasks[0]
            assert tracked_task.name == "my_task-0"
            assert len(tracked_task.upstream_tasks) == 1
            assert upstream_task in tracked_task.upstream_tasks

    async def test_track_task_run_returns_viz_return_value(self):
        s = "my_return_value"

        with TaskRunTracker():
            res = track_task_run(
                "upstream_task_with_value", {"a": 1}, viz_return_value=s
            )
            assert res == s
            assert id(res) == id(s)

    async def test_track_task_run_links_upstream_obj(self):
        s = "my_return_value"

        with TaskRunTracker() as tracker:
            track_task_run("upstream_task_with_value", {"a": 1}, viz_return_value=s)

            assert len(tracker.tasks) == 1
            assert len(tracker.object_id_to_task) == 1
            assert tracker.tasks[0].name == "upstream_task_with_value-0"
            assert tracker.tasks[0].upstream_tasks == []

            track_task_run("my_task", {"a": s})

            assert len(tracker.tasks) == 2
            assert len(tracker.object_id_to_task) == 1
            assert tracker.tasks[1].name == "my_task-0"
            assert tracker.tasks[1].upstream_tasks == [tracker.tasks[0]]

import datetime
import sys
import uuid
from collections import Counter, namedtuple
from unittest.mock import MagicMock

import pendulum
import pytest

import prefect
from prefect.client.client import Client, FlowRunInfoResult, TaskRunInfoResult
from prefect.engine.cloud import CloudFlowRunner, CloudTaskRunner
from prefect.engine.executors import LocalExecutor
from prefect.engine.result_handlers import JSONResultHandler, ResultHandler
from prefect.engine.state import (
    Failed,
    Finished,
    Pending,
    Retrying,
    Running,
    Skipped,
    Success,
    TimedOut,
    TriggerFailed,
)
from prefect.utilities.configuration import set_temporary_config

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")


class FlowRun:
    flow_id = str(uuid.uuid4())

    def __init__(self, id, state=None, version=None):
        self.id = id
        self.name = "flow run name"
        self.state = state or Pending()
        self.version = version or 0


class TaskRun:
    def __init__(
        self, id, flow_run_id, task_slug, state=None, version=None, map_index=None
    ):
        self.id = id
        self.flow_run_id = flow_run_id
        self.task_id = task_slug
        self.task_slug = task_slug
        self.state = state or Pending()
        self.version = version or 0
        self.map_index = map_index if map_index is not None else -1


@prefect.task
def whats_the_time():
    return prefect.context.get("scheduled_start_time")


@prefect.task
def plus_one(x):
    return x + 1


@prefect.task
def invert_fail_once(x):
    try:
        return 1 / x
    except:
        if prefect.context.get("task_run_count", 0) < 2:
            raise
        else:
            return 100


@pytest.fixture(autouse=True)
def cloud_settings():
    with set_temporary_config(
        {
            "cloud.graphql": "http://my-cloud.foo",
            "cloud.auth_token": "token",
            "engine.flow_runner.default_class": "prefect.engine.cloud.CloudFlowRunner",
            "engine.task_runner.default_class": "prefect.engine.cloud.CloudTaskRunner",
            "logging.level": "DEBUG",
        }
    ):
        yield


class MockedCloudClient(MagicMock):
    def __init__(self, flow_runs, task_runs, monkeypatch):
        super().__init__()
        self.flow_runs = {fr.id: fr for fr in flow_runs}
        self.task_runs = {tr.id: tr for tr in task_runs}
        self.call_count = Counter()

        monkeypatch.setattr(
            "prefect.engine.cloud.task_runner.Client", MagicMock(return_value=self)
        )
        monkeypatch.setattr(
            "prefect.engine.cloud.flow_runner.Client", MagicMock(return_value=self)
        )

    def get_flow_run_info(self, flow_run_id, *args, **kwargs):
        self.call_count["get_flow_run_info"] += 1

        flow_run = self.flow_runs[flow_run_id]
        task_runs = [t for t in self.task_runs.values() if t.flow_run_id == flow_run_id]

        return FlowRunInfoResult(
            id=flow_run.id,
            flow_id=flow_run.flow_id,
            name=flow_run.name,
            parameters={},
            context=None,
            version=flow_run.version,
            scheduled_start_time=pendulum.parse("2019-01-25T19:15:58.632412+00:00"),
            state=flow_run.state,
            task_runs=[
                TaskRunInfoResult(
                    id=tr.id,
                    task_id=tr.task_slug,
                    task_slug=tr.task_slug,
                    version=tr.version,
                    state=tr.state,
                )
                for tr in task_runs
            ],
        )

    def get_task_run_info(self, flow_run_id, task_id, map_index, *args, **kwargs):
        """
        Return task run if found, otherwise create it
        """
        self.call_count["get_task_run_info"] += 1

        task_run = next(
            (
                t
                for t in self.task_runs.values()
                if t.flow_run_id == flow_run_id
                and t.task_id == task_id
                and t.map_index == map_index
            ),
            None,
        )

        if not task_run:
            task_run = TaskRun(
                id=str(uuid.uuid4()),
                task_slug=task_id,
                flow_run_id=flow_run_id,
                map_index=map_index,
            )
            self.task_runs[task_run.id] = task_run

        return TaskRunInfoResult(
            id=task_run.id,
            task_id=task_id,
            task_slug=task_id,
            version=task_run.version,
            state=task_run.state,
        )

    def set_flow_run_state(self, flow_run_id, version, state, **kwargs):
        self.call_count["set_flow_run_state"] += 1
        self.call_count[flow_run_id] += 1

        fr = self.flow_runs[flow_run_id]
        if fr.version == version:
            fr.state = state
            fr.version += 1
        else:
            raise ValueError("Invalid flow run update")

    def set_task_run_state(self, task_run_id, version, state, **kwargs):
        self.call_count["set_task_run_state"] += 1
        self.call_count[task_run_id] += 1

        tr = self.task_runs[task_run_id]
        if tr.version == version:
            tr.state = state
            tr.version += 1
        else:
            raise ValueError("Invalid task run update")
        return state


@pytest.mark.parametrize("executor", ["local", "sync"], indirect=True)
def test_simple_two_task_flow(monkeypatch, executor):
    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())
    task_run_id_2 = str(uuid.uuid4())

    with prefect.Flow(name="test") as flow:
        t1 = prefect.Task()
        t2 = prefect.Task()
        t2.set_upstream(t1)

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(id=task_run_id_1, task_slug=t1.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_2, task_slug=t2.slug, flow_run_id=flow_run_id),
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        state = CloudFlowRunner(flow=flow).run(
            return_tasks=flow.tasks, executor=executor
        )

    assert state.is_successful()
    assert client.flow_runs[flow_run_id].state.is_successful()
    assert client.task_runs[task_run_id_1].state.is_successful()
    assert client.task_runs[task_run_id_1].version == 2
    assert client.task_runs[task_run_id_2].state.is_successful()


@pytest.mark.parametrize("executor", ["local", "sync"], indirect=True)
def test_scheduled_start_time_is_in_context(monkeypatch, executor):
    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())

    flow = prefect.Flow(
        name="test", tasks=[whats_the_time], result_handler=ResultHandler()
    )

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(
                id=task_run_id_1, task_slug=whats_the_time.slug, flow_run_id=flow_run_id
            )
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        state = CloudFlowRunner(flow=flow).run(
            return_tasks=flow.tasks, executor=executor
        )

    assert state.is_successful()
    assert client.flow_runs[flow_run_id].state.is_successful()
    assert client.task_runs[task_run_id_1].state.is_successful()
    assert isinstance(state.result[whats_the_time].result, datetime.datetime)


@pytest.mark.parametrize("executor", ["local", "sync"], indirect=True)
def test_simple_two_task_flow_with_final_task_set_to_fail(monkeypatch, executor):

    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())
    task_run_id_2 = str(uuid.uuid4())

    with prefect.Flow(name="test") as flow:
        t1 = prefect.Task()
        t2 = prefect.Task()
        t2.set_upstream(t1)

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(id=task_run_id_1, task_slug=t1.slug, flow_run_id=flow_run_id),
            TaskRun(
                id=task_run_id_2,
                task_slug=t2.slug,
                flow_run_id=flow_run_id,
                state=Failed(),
            ),
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        state = CloudFlowRunner(flow=flow).run(
            return_tasks=flow.tasks, executor=executor
        )

    assert state.is_failed()
    assert client.flow_runs[flow_run_id].state.is_failed()
    assert client.task_runs[task_run_id_1].state.is_successful()
    assert client.task_runs[task_run_id_1].version == 2
    assert client.task_runs[task_run_id_2].state.is_failed()
    assert client.task_runs[task_run_id_2].version == 0


@pytest.mark.parametrize("executor", ["local", "sync"], indirect=True)
def test_simple_two_task_flow_with_final_task_already_running(monkeypatch, executor):

    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())
    task_run_id_2 = str(uuid.uuid4())

    with prefect.Flow(name="test") as flow:
        t1 = prefect.Task()
        t2 = prefect.Task()
        t2.set_upstream(t1)

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(id=task_run_id_1, task_slug=t1.slug, flow_run_id=flow_run_id),
            TaskRun(
                id=task_run_id_2,
                task_slug=t2.slug,
                version=1,
                flow_run_id=flow_run_id,
                state=Running(),
            ),
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        state = CloudFlowRunner(flow=flow).run(
            return_tasks=flow.tasks, executor=executor
        )

    assert state.is_running()
    assert client.flow_runs[flow_run_id].state.is_running()
    assert client.task_runs[task_run_id_1].state.is_successful()
    assert client.task_runs[task_run_id_1].version == 2
    assert client.task_runs[task_run_id_2].state.is_running()
    assert client.task_runs[task_run_id_2].version == 1


@pytest.mark.parametrize("executor", ["local", "sync"], indirect=True)
def test_simple_three_task_flow_with_one_failing_task(monkeypatch, executor):
    @prefect.task
    def error():
        1 / 0

    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())
    task_run_id_2 = str(uuid.uuid4())
    task_run_id_3 = str(uuid.uuid4())

    with prefect.Flow(name="test") as flow:
        t1 = prefect.Task()
        t2 = prefect.Task()
        t3 = error()
        t2.set_upstream(t1)
        t3.set_upstream(t2)

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(id=task_run_id_1, task_slug=t1.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_2, task_slug=t2.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_3, task_slug=t3.slug, flow_run_id=flow_run_id),
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        state = CloudFlowRunner(flow=flow).run(
            return_tasks=flow.tasks, executor=executor
        )

    assert state.is_failed()
    assert client.flow_runs[flow_run_id].state.is_failed()
    assert client.task_runs[task_run_id_1].state.is_successful()
    assert client.task_runs[task_run_id_1].version == 2
    assert client.task_runs[task_run_id_2].state.is_successful()
    assert client.task_runs[task_run_id_2].version == 2
    assert client.task_runs[task_run_id_3].state.is_failed()
    assert client.task_runs[task_run_id_2].version == 2


@pytest.mark.parametrize("executor", ["local", "sync"], indirect=True)
def test_simple_three_task_flow_with_first_task_retrying(monkeypatch, executor):
    """
    If the first task retries, then the next two tasks shouldn't even make calls to Cloud
    because they won't pass their upstream checks
    """

    @prefect.task(max_retries=1, retry_delay=datetime.timedelta(minutes=20))
    def error():
        1 / 0

    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())
    task_run_id_2 = str(uuid.uuid4())
    task_run_id_3 = str(uuid.uuid4())

    with prefect.Flow(name="test") as flow:
        t1 = error()
        t2 = prefect.Task()
        t3 = prefect.Task()
        t2.set_upstream(t1)
        t3.set_upstream(t2)

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(id=task_run_id_1, task_slug=t1.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_2, task_slug=t2.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_3, task_slug=t3.slug, flow_run_id=flow_run_id),
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        state = CloudFlowRunner(flow=flow).run(
            return_tasks=flow.tasks, executor=executor
        )

    assert state.is_running()
    assert client.flow_runs[flow_run_id].state.is_running()
    assert isinstance(client.task_runs[task_run_id_1].state, Retrying)
    assert client.task_runs[task_run_id_1].version == 3
    assert client.task_runs[task_run_id_2].state.is_pending()
    assert client.task_runs[task_run_id_2].version == 0
    assert client.task_runs[task_run_id_3].state.is_pending()
    assert client.task_runs[task_run_id_2].version == 0
    assert client.call_count["set_task_run_state"] == 3


@pytest.mark.parametrize("executor", ["local", "sync"], indirect=True)
def test_simple_map(monkeypatch, executor):

    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())

    with prefect.Flow(name="test", result_handler=JSONResultHandler()) as flow:
        t1 = plus_one.map([0, 1, 2])

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(id=task_run_id_1, task_slug=t1.slug, flow_run_id=flow_run_id)
        ]
        + [
            TaskRun(id=str(uuid.uuid4()), task_slug=t.slug, flow_run_id=flow_run_id)
            for t in flow.tasks
            if t is not t1
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        state = CloudFlowRunner(flow=flow).run(
            return_tasks=flow.tasks, executor=executor
        )

    assert state.is_successful()
    assert client.flow_runs[flow_run_id].state.is_successful()
    assert client.task_runs[task_run_id_1].state.is_mapped()
    # there should be a total of 4 task runs corresponding to the mapped task
    assert len([tr for tr in client.task_runs.values() if tr.task_slug == t1.slug]) == 4


@pytest.mark.parametrize("executor", ["local", "sync"], indirect=True)
def test_deep_map(monkeypatch, executor):

    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())
    task_run_id_2 = str(uuid.uuid4())
    task_run_id_3 = str(uuid.uuid4())

    with prefect.Flow(name="test", result_handler=JSONResultHandler()) as flow:
        t1 = plus_one.map([0, 1, 2])
        t2 = plus_one.map(t1)
        t3 = plus_one.map(t2)

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(id=task_run_id_1, task_slug=t1.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_2, task_slug=t2.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_3, task_slug=t3.slug, flow_run_id=flow_run_id),
        ]
        + [
            TaskRun(id=str(uuid.uuid4()), task_slug=t.slug, flow_run_id=flow_run_id)
            for t in flow.tasks
            if t not in [t1, t2, t3]
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        state = CloudFlowRunner(flow=flow).run(
            return_tasks=flow.tasks, executor=executor
        )

    assert state.is_successful()
    assert client.flow_runs[flow_run_id].state.is_successful()
    assert client.task_runs[task_run_id_1].state.is_mapped()
    assert client.task_runs[task_run_id_2].state.is_mapped()
    assert client.task_runs[task_run_id_3].state.is_mapped()

    # there should be a total of 4 task runs corresponding to each mapped task
    for t in [t1, t2, t3]:
        assert (
            len([tr for tr in client.task_runs.values() if tr.task_slug == t.slug]) == 4
        )


@pytest.mark.parametrize("executor", ["local", "sync"], indirect=True)
def test_deep_map_with_a_failure(monkeypatch, executor):

    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())
    task_run_id_2 = str(uuid.uuid4())
    task_run_id_3 = str(uuid.uuid4())

    with prefect.Flow(name="test", result_handler=JSONResultHandler()) as flow:
        t1 = plus_one.map([-1, 0, 1])
        t2 = invert_fail_once.map(t1)
        t3 = plus_one.map(t2)

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(id=task_run_id_1, task_slug=t1.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_2, task_slug=t2.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_3, task_slug=t3.slug, flow_run_id=flow_run_id),
        ]
        + [
            TaskRun(id=str(uuid.uuid4()), task_slug=t.slug, flow_run_id=flow_run_id)
            for t in flow.tasks
            if t not in [t1, t2, t3]
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        state = CloudFlowRunner(flow=flow).run(return_tasks=flow.tasks)

    assert state.is_failed()
    assert client.flow_runs[flow_run_id].state.is_failed()
    assert client.task_runs[task_run_id_1].state.is_mapped()
    assert client.task_runs[task_run_id_2].state.is_mapped()
    assert client.task_runs[task_run_id_3].state.is_mapped()

    # there should be a total of 4 task runs corresponding to each mapped task
    for t in [t1, t2, t3]:
        assert (
            len([tr for tr in client.task_runs.values() if tr.task_slug == t.slug]) == 4
        )

    # t2's first child task should have failed
    t2_0 = next(
        tr
        for tr in client.task_runs.values()
        if tr.task_slug == t2.slug and tr.map_index == 0
    )
    assert t2_0.state.is_failed()

    # t3's first child task should have failed
    t3_0 = next(
        tr
        for tr in client.task_runs.values()
        if tr.task_slug == t3.slug and tr.map_index == 0
    )
    assert t3_0.state.is_failed()


def test_deep_map_with_a_retry(monkeypatch):
    """
    Creates a situation in which a deeply-mapped Flow encounters a one-time error in one
    of the middle layers. Running the flow a second time should resolve the error.

    DOES NOT WORK WITH DASK EXECUTORS because of the need for shared state on second run
    """

    flow_run_id = str(uuid.uuid4())
    task_run_id_1 = str(uuid.uuid4())
    task_run_id_2 = str(uuid.uuid4())
    task_run_id_3 = str(uuid.uuid4())

    with prefect.Flow(name="test", result_handler=JSONResultHandler()) as flow:
        t1 = plus_one.map([-1, 0, 1])
        t2 = invert_fail_once.map(t1)
        t3 = plus_one.map(t2)

    t2.max_retries = 1
    t2.retry_delay = datetime.timedelta(minutes=100)

    monkeypatch.setattr("requests.Session", MagicMock())
    monkeypatch.setattr("requests.post", MagicMock())

    client = MockedCloudClient(
        flow_runs=[FlowRun(id=flow_run_id)],
        task_runs=[
            TaskRun(id=task_run_id_1, task_slug=t1.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_2, task_slug=t2.slug, flow_run_id=flow_run_id),
            TaskRun(id=task_run_id_3, task_slug=t3.slug, flow_run_id=flow_run_id),
        ]
        + [
            TaskRun(id=str(uuid.uuid4()), task_slug=t.slug, flow_run_id=flow_run_id)
            for t in flow.tasks
            if t not in [t1, t2, t3]
        ],
        monkeypatch=monkeypatch,
    )

    with prefect.context(flow_run_id=flow_run_id):
        CloudFlowRunner(flow=flow).run(executor=LocalExecutor())

    assert client.flow_runs[flow_run_id].state.is_running()
    assert client.task_runs[task_run_id_1].state.is_mapped()
    assert client.task_runs[task_run_id_2].state.is_mapped()
    assert client.task_runs[task_run_id_3].state.is_mapped()

    # there should be a total of 4 task runs corresponding to each mapped task
    for t in [t1, t2, t3]:
        assert (
            len([tr for tr in client.task_runs.values() if tr.task_slug == t.slug]) == 4
        )

    # t2's first child task should be retrying
    t2_0 = next(
        tr
        for tr in client.task_runs.values()
        if tr.task_slug == t2.slug and tr.map_index == 0
    )
    assert isinstance(t2_0.state, Retrying)

    # t3's first child task should be pending
    t3_0 = next(
        tr
        for tr in client.task_runs.values()
        if tr.task_slug == t3.slug and tr.map_index == 0
    )
    assert t3_0.state.is_pending()

    # RUN A SECOND TIME with an artificially updated start time
    failed_id = [
        t_id
        for t_id, tr in client.task_runs.items()
        if tr.task_slug == t2.slug and tr.map_index == 0
    ].pop()
    client.task_runs[failed_id].state.start_time = pendulum.now("UTC")

    with prefect.context(flow_run_id=flow_run_id):
        CloudFlowRunner(flow=flow).run(executor=LocalExecutor())

    # t2's first child task should be successful
    t2_0 = next(
        tr
        for tr in client.task_runs.values()
        if tr.task_slug == t2.slug and tr.map_index == 0
    )
    assert t2_0.state.is_successful()

    # t3's first child task should be successful
    t3_0 = next(
        tr
        for tr in client.task_runs.values()
        if tr.task_slug == t3.slug and tr.map_index == 0
    )
    assert t3_0.state.is_successful()

import concurrent.futures
import uuid

import pytest

from prefect.blocks.system import DateTime
from prefect.futures import PrefectConcurrentFuture, PrefectDistributedFuture
from prefect.server.schemas.core import FlowRun, TaskRun
from prefect.server.schemas.states import State
from prefect.settings import PREFECT_API_URL, PREFECT_UI_URL, temporary_settings
from prefect.utilities.urls import url_for
from prefect.variables import Variable

MOCK_PREFECT_UI_URL = "https://ui.prefect.io"
MOCK_PREFECT_API_URL = "https://api.prefect.io"


@pytest.fixture
async def variable():
    return Variable(name="my_variable", value="my-value", tags=["123", "456"])


@pytest.fixture
def flow_run(flow):
    return FlowRun(
        flow_id=flow.id,
        state=State(
            id=uuid.uuid4(), type="RUNNING", name="My Running State", state_details={}
        ),
    )


@pytest.fixture
def task_run():
    return TaskRun(
        id="123e4567-e89b-12d3-a456-426614174000",
        task_key="my-task",
        dynamic_key="my-dynamic-key",
    )


@pytest.fixture
def prefect_concurrent_future(task_run):
    return PrefectConcurrentFuture(
        task_run_id=task_run.id,
        wrapped_future=concurrent.futures.Future(),
    )


@pytest.fixture
def prefect_distributed_future(task_run):
    return PrefectDistributedFuture(task_run_id=task_run.id)


@pytest.fixture
def block():
    block = DateTime(value="2022-01-01T00:00:00Z")
    block.save("my-date-block")
    return block


def test_url_for_flow_run_schema_ui(flow_run):
    expected_url = f"{MOCK_PREFECT_UI_URL}/runs/flow-run/{flow_run.id}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=flow_run, url_type="ui") == expected_url


def test_url_for_flow_run_ui(flow_run):
    expected_url = f"{MOCK_PREFECT_UI_URL}/runs/flow-run/{flow_run.id}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=flow_run, url_type="ui") == expected_url


def test_url_for_task_run_ui(task_run):
    expected_url = f"{MOCK_PREFECT_UI_URL}/runs/task-run/{task_run.id}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=task_run, url_type="ui") == expected_url


@pytest.mark.parametrize(
    "prefect_future_fixture",
    ["prefect_concurrent_future", "prefect_distributed_future"],
)
def test_url_for_prefect_future_ui(prefect_future_fixture, request, task_run):
    prefect_future = request.getfixturevalue(prefect_future_fixture)
    expected_url = f"{MOCK_PREFECT_UI_URL}/runs/task-run/{task_run.id}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=prefect_future, url_type="ui") == expected_url


def test_url_for_flow_run_with_id_ui(flow_run):
    expected_url = f"{MOCK_PREFECT_UI_URL}/runs/flow-run/{flow_run.id}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert (
            url_for(
                obj="flow-run",
                obj_id=flow_run.id,
                url_type="ui",
            )
            == expected_url
        )


def test_url_for_task_run_with_id_ui(task_run):
    expected_url = f"{MOCK_PREFECT_UI_URL}/runs/task-run/{task_run.id}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert (
            url_for(
                obj="task-run",
                obj_id=task_run.id,
                url_type="ui",
            )
            == expected_url
        )


def test_url_for_flow_run_api(flow_run):
    expected_url = f"{MOCK_PREFECT_API_URL}/runs/flow-run/{flow_run.id}"
    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert url_for(obj=flow_run, url_type="api") == expected_url


def test_url_for_task_run_api(task_run):
    expected_url = f"{MOCK_PREFECT_API_URL}/runs/task-run/{task_run.id}"
    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert url_for(obj=task_run, url_type="api") == expected_url


@pytest.mark.parametrize(
    "prefect_future_fixture",
    ["prefect_concurrent_future", "prefect_distributed_future"],
)
def test_url_for_prefect_future_api(prefect_future_fixture, request, task_run):
    prefect_future = request.getfixturevalue(prefect_future_fixture)
    expected_url = f"{MOCK_PREFECT_API_URL}/runs/task-run/{task_run.id}"
    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert url_for(obj=prefect_future, url_type="api") == expected_url


def test_url_for_flow_run_with_id_api(flow_run):
    expected_url = f"{MOCK_PREFECT_API_URL}/runs/flow-run/{flow_run.id}"
    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert (
            url_for(
                obj="flow-run",
                obj_id=flow_run.id,
                url_type="api",
            )
            == expected_url
        )


def test_url_for_task_run_with_id_api(task_run):
    expected_url = f"{MOCK_PREFECT_API_URL}/runs/task-run/{task_run.id}"
    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert (
            url_for(
                obj="task-run",
                obj_id=task_run.id,
                url_type="api",
            )
            == expected_url
        )


def test_url_for_missing_url(flow_run):
    with temporary_settings({PREFECT_UI_URL: None, PREFECT_API_URL: None}):
        assert (
            url_for(
                obj="flow-run",
                obj_id=flow_run.id,
                url_type="ui",
                default_base_path=None,
            )
            == ""
        )


def test_url_for_with_default_base_path(flow_run):
    default_base_path = "https://default.prefect.io"
    expected_url = f"{default_base_path}/runs/flow-run/{flow_run.id}"
    assert (
        url_for(
            obj="flow-run",
            obj_id=flow_run.id,
            default_base_path=default_base_path,
        )
        == expected_url
    )


def test_url_for_invalid_obj():
    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert (
            url_for(
                obj="some-obj",  # type: ignore
            )
            == ""
        )


def test_url_for_unsupported_obj_type():
    class UnsupportedType:
        pass

    unsupported_obj = UnsupportedType()

    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert url_for(obj=unsupported_obj) == ""  # type: ignore


def test_url_block(block):
    expected_url = f"{MOCK_PREFECT_UI_URL}/blocks/block/{block._block_document_id}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=block, url_type="ui") == expected_url


def test_url_for_work_pool(work_pool):
    expected_url = f"{MOCK_PREFECT_UI_URL}/work-pools/work-pool/{work_pool.name}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=work_pool, url_type="ui") == expected_url


def test_api_url_for_variable(variable):
    expected_url = f"{MOCK_PREFECT_API_URL}/variables/name/{variable.name}"
    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert url_for(obj=variable, url_type="api") == expected_url


def test_no_ui_url_for_variable(variable):
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=variable, url_type="ui") == ""

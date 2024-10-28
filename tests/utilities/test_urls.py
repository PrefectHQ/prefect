import concurrent.futures
import uuid
from datetime import timedelta
from typing import Literal

import pendulum
import pytest

from prefect.blocks.webhook import Webhook
from prefect.events.schemas.automations import Automation, EventTrigger, Posture
from prefect.events.schemas.events import ReceivedEvent, Resource
from prefect.futures import PrefectConcurrentFuture, PrefectDistributedFuture
from prefect.server.schemas.core import FlowRun, TaskRun
from prefect.server.schemas.states import State
from prefect.settings import PREFECT_API_URL, PREFECT_UI_URL, temporary_settings
from prefect.utilities.urls import url_for, validate_restricted_url
from prefect.variables import Variable

MOCK_PREFECT_UI_URL = "https://ui.prefect.io"
MOCK_PREFECT_API_URL = "https://api.prefect.io"

RESTRICTED_URLS = [
    ("", ""),
    (" ", ""),
    ("[]", ""),
    ("not a url", ""),
    ("http://", ""),
    ("https://", ""),
    ("http://[]/foo/bar", ""),
    ("ftp://example.com", "HTTP and HTTPS"),
    ("gopher://example.com", "HTTP and HTTPS"),
    ("https://localhost", "private address"),
    ("https://127.0.0.1", "private address"),
    ("https://[::1]", "private address"),
    ("https://[fc00:1234:5678:9abc::10]", "private address"),
    ("https://[fd12:3456:789a:1::1]", "private address"),
    ("https://[fe80::1234:5678:9abc]", "private address"),
    ("https://10.0.0.1", "private address"),
    ("https://10.255.255.255", "private address"),
    ("https://172.16.0.1", "private address"),
    ("https://172.31.255.255", "private address"),
    ("https://192.168.1.1", "private address"),
    ("https://192.168.1.255", "private address"),
    ("https://169.254.0.1", "private address"),
    ("https://169.254.169.254", "private address"),
    ("https://169.254.254.255", "private address"),
    # These will resolve to a private address in production, but not in tests,
    # so we'll use "resolve" as the reason to catch both cases
    ("https://metadata.google.internal", "resolve"),
    ("https://anything.privatecloud", "resolve"),
    ("https://anything.privatecloud.svc", "resolve"),
    ("https://anything.privatecloud.svc.cluster.local", "resolve"),
    ("https://cluster-internal", "resolve"),
    ("https://network-internal.cloud.svc", "resolve"),
    ("https://private-internal.cloud.svc.cluster.local", "resolve"),
]


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
    block = Webhook(url="https://example.com")
    block.save("my-webhook-block", overwrite=True)
    return block


@pytest.fixture
async def automation() -> Automation:
    return Automation(
        id=uuid.uuid4(),
        name="If my lilies get nibbled, tell me about it",
        description="Send an email notification whenever the lilies are nibbled",
        enabled=True,
        trigger=EventTrigger(
            expect={"animal.ingested"},
            match_related={
                "prefect.resource.role": "meal",
                "genus": "Hemerocallis",
                "species": "fulva",
            },
            posture=Posture.Reactive,
            threshold=0,
            within=timedelta(seconds=30),
        ),
        actions=[{"type": "do-nothing"}],
    )


@pytest.fixture
def received_event():
    return ReceivedEvent(
        occurred=pendulum.now("UTC"),
        received=pendulum.now("UTC"),
        event="was.tubular",
        resource=Resource.model_validate(
            {"prefect.resource.id": f"prefect.flow-run.{uuid.uuid4()}"}
        ),
        payload={"goodbye": "yellow brick road"},
        id=uuid.uuid4(),
    )


@pytest.fixture
def resource():
    return Resource({"prefect.resource.id": f"prefect.flow-run.{uuid.uuid4()}"})


@pytest.mark.parametrize("value, reason", RESTRICTED_URLS)
def test_validate_restricted_url_validates(value: str, reason: str):
    with pytest.raises(ValueError, match=f"is not a valid URL.*{reason}"):
        validate_restricted_url(url=value)


@pytest.mark.parametrize("url_type", ["ui", "api"])
def test_url_for_flow_run(flow_run, url_type: Literal["ui", "api"]):
    expected_url = (
        f"{MOCK_PREFECT_UI_URL}/runs/flow-run/{flow_run.id}"
        if url_type == "ui"
        else f"{MOCK_PREFECT_API_URL}/flow_runs/{flow_run.id}"
    )
    with temporary_settings(
        {PREFECT_UI_URL: MOCK_PREFECT_UI_URL, PREFECT_API_URL: MOCK_PREFECT_API_URL}
    ):
        assert url_for(obj=flow_run, url_type=url_type) == expected_url


@pytest.mark.parametrize("url_type", ["ui", "api"])
def test_url_for_task_run(task_run, url_type: Literal["ui", "api"]):
    expected_url = (
        f"{MOCK_PREFECT_UI_URL}/runs/task-run/{task_run.id}"
        if url_type == "ui"
        else f"{MOCK_PREFECT_API_URL}/task_runs/{task_run.id}"
    )
    with temporary_settings(
        {PREFECT_UI_URL: MOCK_PREFECT_UI_URL, PREFECT_API_URL: MOCK_PREFECT_API_URL}
    ):
        assert url_for(obj=task_run, url_type=url_type) == expected_url


@pytest.mark.parametrize(
    "prefect_future_fixture",
    ["prefect_concurrent_future", "prefect_distributed_future"],
)
@pytest.mark.parametrize("url_type", ["ui", "api"])
def test_url_for_prefect_future(
    prefect_future_fixture, url_type: Literal["ui", "api"], request, task_run
):
    prefect_future = request.getfixturevalue(prefect_future_fixture)
    expected_url = (
        f"{MOCK_PREFECT_UI_URL}/runs/task-run/{task_run.id}"
        if url_type == "ui"
        else f"{MOCK_PREFECT_API_URL}/task_runs/{task_run.id}"
    )
    with temporary_settings(
        {PREFECT_UI_URL: MOCK_PREFECT_UI_URL, PREFECT_API_URL: MOCK_PREFECT_API_URL}
    ):
        assert url_for(obj=prefect_future, url_type=url_type) == expected_url


@pytest.mark.parametrize("url_type", ["ui", "api"])
def test_url_for_block(block, url_type: Literal["ui", "api"]):
    expected_url = (
        f"{MOCK_PREFECT_UI_URL}/blocks/block/{block._block_document_id}"
        if url_type == "ui"
        else f"{MOCK_PREFECT_API_URL}/blocks/{block._block_document_id}"
    )
    with temporary_settings(
        {PREFECT_UI_URL: MOCK_PREFECT_UI_URL, PREFECT_API_URL: MOCK_PREFECT_API_URL}
    ):
        assert url_for(obj=block, url_type=url_type) == expected_url


@pytest.mark.parametrize("url_type", ["ui", "api"])
def test_url_for_work_pool(work_pool, url_type: Literal["ui", "api"]):
    expected_url = (
        f"{MOCK_PREFECT_UI_URL}/work-pools/work-pool/{work_pool.name}"
        if url_type == "ui"
        else f"{MOCK_PREFECT_API_URL}/work_pools/{work_pool.name}"
    )
    with temporary_settings(
        {PREFECT_UI_URL: MOCK_PREFECT_UI_URL, PREFECT_API_URL: MOCK_PREFECT_API_URL}
    ):
        assert url_for(obj=work_pool, url_type=url_type) == expected_url


def test_api_url_for_variable(variable):
    expected_url = f"{MOCK_PREFECT_API_URL}/variables/name/{variable.name}"
    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert url_for(obj=variable, url_type="api") == expected_url


def test_no_ui_url_for_variable(variable):
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=variable, url_type="ui") is None


@pytest.mark.parametrize("url_type", ["ui", "api"])
def test_url_for_automation(automation, url_type: Literal["ui", "api"]):
    expected_url = (
        f"{MOCK_PREFECT_UI_URL}/automations/automation/{automation.id}"
        if url_type == "ui"
        else f"{MOCK_PREFECT_API_URL}/automations/{automation.id}"
    )
    with temporary_settings(
        {PREFECT_UI_URL: MOCK_PREFECT_UI_URL, PREFECT_API_URL: MOCK_PREFECT_API_URL}
    ):
        assert url_for(obj=automation, url_type=url_type) == expected_url


def test_url_for_received_event_ui(received_event):
    expected_url = f"{MOCK_PREFECT_UI_URL}/events/event/{received_event.occurred.strftime('%Y-%m-%d')}/{received_event.id}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=received_event, url_type="ui") == expected_url


def test_url_for_resource_ui(resource):
    resource_id_part = resource.id.rpartition(".")[2]
    expected_url = f"{MOCK_PREFECT_UI_URL}/runs/flow-run/{resource_id_part}"
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=resource, url_type="ui") == expected_url


@pytest.mark.parametrize("url_type", ["ui", "api"])
def test_url_for_flow_run_with_id(flow_run, url_type: Literal["ui", "api"]):
    expected_url = (
        f"{MOCK_PREFECT_UI_URL}/runs/flow-run/{flow_run.id}"
        if url_type == "ui"
        else f"{MOCK_PREFECT_API_URL}/flow_runs/{flow_run.id}"
    )
    with temporary_settings(
        {PREFECT_UI_URL: MOCK_PREFECT_UI_URL, PREFECT_API_URL: MOCK_PREFECT_API_URL}
    ):
        assert (
            url_for(
                obj="flow-run",
                obj_id=flow_run.id,
                url_type=url_type,
            )
            == expected_url
        )


@pytest.mark.parametrize("url_type", ["ui", "api"])
def test_url_for_task_run_with_id(task_run, url_type: Literal["ui", "api"]):
    expected_url = (
        f"{MOCK_PREFECT_UI_URL}/runs/task-run/{task_run.id}"
        if url_type == "ui"
        else f"{MOCK_PREFECT_API_URL}/task_runs/{task_run.id}"
    )
    with temporary_settings(
        {PREFECT_UI_URL: MOCK_PREFECT_UI_URL, PREFECT_API_URL: MOCK_PREFECT_API_URL}
    ):
        assert (
            url_for(
                obj="task-run",
                obj_id=task_run.id,
                url_type=url_type,
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
                default_base_url=None,
            )
            is None
        )


def test_url_for_with_default_base_url(flow_run, enable_ephemeral_server):
    default_base_url = "https://default.prefect.io"
    expected_url = f"{default_base_url}/runs/flow-run/{flow_run.id}"
    assert (
        url_for(
            obj="flow-run",
            obj_id=flow_run.id,
            default_base_url=default_base_url,
        )
        == expected_url
    )


def test_url_for_with_default_base_url_with_path_fragment(
    flow_run, enable_ephemeral_server
):
    default_base_url = "https://default.prefect.io/api"
    expected_url = f"{default_base_url}/runs/flow-run/{flow_run.id}"
    assert (
        url_for(
            obj="flow-run",
            obj_id=flow_run.id,
            default_base_url=default_base_url,
        )
        == expected_url
    )


def test_url_for_with_default_base_url_with_path_fragment_and_slash(
    flow_run, enable_ephemeral_server
):
    default_base_url = "https://default.prefect.io/api/"
    expected_url = f"{default_base_url}runs/flow-run/{flow_run.id}"
    assert (
        url_for(
            obj="flow-run",
            obj_id=flow_run.id,
            default_base_url=default_base_url,
        )
        == expected_url
    )


def test_url_for_invalid_obj_name_api():
    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert (
            url_for(
                obj="some-obj",
            )
            is None
        )


def test_url_for_invalid_obj_name_ui():
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert (
            url_for(
                obj="some-obj",
            )
            is None
        )


def test_url_for_unsupported_obj_type_api():
    class UnsupportedType:
        pass

    unsupported_obj = UnsupportedType()

    with temporary_settings({PREFECT_API_URL: MOCK_PREFECT_API_URL}):
        assert url_for(obj=unsupported_obj) is None  # type: ignore


def test_url_for_unsupported_obj_type_ui():
    class UnsupportedType:
        pass

    unsupported_obj = UnsupportedType()

    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        assert url_for(obj=unsupported_obj) is None  # type: ignore

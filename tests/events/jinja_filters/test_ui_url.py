from datetime import timedelta
from uuid import uuid4

import jinja2
import pytest

from prefect.events.schemas.events import ReceivedEvent, Resource
from prefect.server.events.jinja_filters import ui_url
from prefect.server.events.schemas.automations import Automation, EventTrigger, Posture
from prefect.server.schemas.core import (
    Deployment,
    Flow,
    FlowRun,
    TaskRun,
    WorkPool,
    WorkQueue,
)
from prefect.server.schemas.responses import FlowRunResponse
from prefect.settings import PREFECT_UI_URL, temporary_settings
from prefect.types._datetime import DateTime

template_environment = jinja2.Environment()
template_environment.filters["ui_url"] = ui_url

MOCK_PREFECT_UI_URL = "http://localhost:3000"


@pytest.fixture(autouse=True)
def mock_prefect_ui_url():
    with temporary_settings({PREFECT_UI_URL: MOCK_PREFECT_UI_URL}):
        yield


@pytest.fixture
async def chonk_party() -> Automation:
    return Automation(
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
def woodchonk_walked(start_of_test: DateTime) -> ReceivedEvent:
    return ReceivedEvent(
        occurred=start_of_test + timedelta(microseconds=2),
        received=start_of_test + timedelta(microseconds=2),
        event="animal.walked",
        resource={
            "kingdom": "Animalia",
            "phylum": "Chordata",
            "class": "Mammalia",
            "order": "Rodentia",
            "family": "Sciuridae",
            "genus": "Marmota",
            "species": "monax",
            "prefect.resource.id": "woodchonk",
        },
        id=uuid4(),
    )


def test_automation_url(chonk_party: Automation):
    template = template_environment.from_string("{{ automation|ui_url }}")
    rendered = template.render({"automation": chonk_party})

    assert rendered == (
        f"http://localhost:3000/automations/automation/{chonk_party.id}"
    )


def test_deployment_resource_url(chonk_party: Automation):
    deployment_id = uuid4()

    template = template_environment.from_string("{{ deployment_resource|ui_url}}")
    rendered = template.render(
        {
            "automation": chonk_party,
            "deployment_resource": Resource.model_validate(
                {"prefect.resource.id": f"prefect.deployment.{deployment_id}"}
            ),
        }
    )

    assert rendered == (f"http://localhost:3000/deployments/deployment/{deployment_id}")


def test_flow_resource_url(chonk_party: Automation):
    flow_id = uuid4()

    template = template_environment.from_string("{{ flow_resource|ui_url }}")
    rendered = template.render(
        {
            "automation": chonk_party,
            "flow_resource": Resource.model_validate(
                {"prefect.resource.id": f"prefect.flow.{flow_id}"}
            ),
        }
    )

    assert rendered == (f"http://localhost:3000/flows/flow/{flow_id}")


def test_flow_run_resource_url(chonk_party: Automation):
    flow_run_id = uuid4()

    template = template_environment.from_string("{{ flow_run_resource|ui_url }}")
    rendered = template.render(
        {
            "automation": chonk_party,
            "flow_run_resource": Resource.model_validate(
                {"prefect.resource.id": f"prefect.flow-run.{flow_run_id}"}
            ),
        }
    )

    assert rendered == f"http://localhost:3000/runs/flow-run/{flow_run_id}"


def test_task_run_resource_url(chonk_party: Automation):
    task_run_id = uuid4()

    template = template_environment.from_string("{{ task_run_resource|ui_url }}")
    rendered = template.render(
        {
            "automation": chonk_party,
            "task_run_resource": Resource.model_validate(
                {"prefect.resource.id": f"prefect.task-run.{task_run_id}"}
            ),
        }
    )

    assert rendered == f"http://localhost:3000/runs/task-run/{task_run_id}"


def test_work_queue_resource_url(chonk_party: Automation):
    work_queue_id = uuid4()

    template = template_environment.from_string("{{ work_queue_resource|ui_url }}")
    rendered = template.render(
        {
            "automation": chonk_party,
            "work_queue_resource": Resource.model_validate(
                {"prefect.resource.id": f"prefect.work-queue.{work_queue_id}"}
            ),
        }
    )

    assert rendered == f"http://localhost:3000/work-queues/work-queue/{work_queue_id}"


def test_work_pool_resource_url(chonk_party: Automation):
    template = template_environment.from_string("{{ work_pool_resource|ui_url }}")
    rendered = template.render(
        {
            "automation": chonk_party,
            "work_pool_resource": Resource.model_validate(
                {
                    "prefect.resource.id": f"prefect.work-pool.{uuid4()}",
                    "prefect.resource.name": "hi-there",
                }
            ),
        }
    )

    assert rendered == "http://localhost:3000/work-pools/work-pool/hi-there"


def test_deployment_model(chonk_party: Automation):
    deployment = Deployment(id=uuid4(), name="the-deployment", flow_id=uuid4())
    template = template_environment.from_string("{{ deployment|ui_url }}")
    rendered = template.render({"automation": chonk_party, "deployment": deployment})

    assert rendered == f"http://localhost:3000/deployments/deployment/{deployment.id}"


def test_flow_model(chonk_party: Automation):
    flow = Flow(id=uuid4(), name="the-flow")
    template = template_environment.from_string("{{ flow|ui_url }}")
    rendered = template.render({"automation": chonk_party, "flow": flow})

    assert rendered == f"http://localhost:3000/flows/flow/{flow.id}"


def test_flow_run_model(chonk_party: Automation):
    flow_run = FlowRun(id=uuid4(), name="the-flow-run", flow_id=uuid4())
    template = template_environment.from_string("{{ flow_run|ui_url }}")
    rendered = template.render({"automation": chonk_party, "flow_run": flow_run})

    assert rendered == f"http://localhost:3000/runs/flow-run/{flow_run.id}"


def test_task_run_model(chonk_party: Automation):
    task_run = TaskRun(
        id=uuid4(),
        flow_run_id=uuid4(),
        name="the-task-run",
        task_key="key123",
        dynamic_key="a",
    )
    template = template_environment.from_string("{{ task_run|ui_url }}")
    rendered = template.render({"automation": chonk_party, "task_run": task_run})

    assert rendered == f"http://localhost:3000/runs/task-run/{task_run.id}"


def test_work_queue_model(chonk_party: Automation):
    work_queue = WorkQueue(
        id=uuid4(), name="the-work-queue", work_pool_id=uuid4(), priority=1
    )
    template = template_environment.from_string("{{ work_queue|ui_url }}")
    rendered = template.render({"automation": chonk_party, "work_queue": work_queue})

    assert rendered == f"http://localhost:3000/work-queues/work-queue/{work_queue.id}"


async def test_work_pool_model(chonk_party: Automation):
    work_pool = WorkPool(
        id=uuid4(), name="the-work-pool", type="chonk", default_queue_id=uuid4()
    )
    template = template_environment.from_string("{{ work_pool|ui_url }}")
    rendered = template.render({"automation": chonk_party, "work_pool": work_pool})

    assert rendered == f"http://localhost:3000/work-pools/work-pool/{work_pool.name}"


def test_flow_run_response_model(chonk_party: Automation):
    flow_run_response = FlowRunResponse(
        id=uuid4(), name="the-flow-run", flow_id=uuid4()
    )
    template = template_environment.from_string("{{ flow_run|ui_url }}")
    rendered = template.render(
        {"automation": chonk_party, "flow_run": flow_run_response}
    )

    assert rendered == f"http://localhost:3000/runs/flow-run/{flow_run_response.id}"

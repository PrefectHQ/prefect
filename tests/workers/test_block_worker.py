from copy import copy
from unittest.mock import MagicMock

import pendulum
import pytest

from prefect import flow
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.blocks.core import Block
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.infrastructure.base import Infrastructure
from prefect.server import models, schemas
from prefect.states import Cancelled, Cancelling, Completed, Pending, Running, Scheduled
from prefect.utilities.callables import parameter_schema
from prefect.workers.block import (
    BlockWorker,
    BlockWorkerJobConfiguration,
)

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field


class MockInfrastructure(Infrastructure):
    type: str = "mock"
    _block_type_slug: str = "mock-infrastructure"
    field: str = Field(
        default="default", description="A field that can be overridden by the user."
    )

    _run = MagicMock()
    _kill = MagicMock()

    async def run(self, task_status=None):
        if task_status:
            task_status.started()
        self._run(**self.dict(exclude={"block_type_slug"}))

    async def kill(self, infrastructure_pid: str, grace_seconds: int = 30):
        self._kill(infrastructure_pid=infrastructure_pid, grace_seconds=grace_seconds)

    def preview(self):
        return self.json()

    class Config:
        arbitrary_types_allowed = True


@pytest.fixture
def block_worker(block_work_pool):
    return BlockWorker(work_pool_name=block_work_pool.name)


@pytest.fixture
async def mock_infra_block_doc_id():
    block_doc_id = await MockInfrastructure().save("this-is-a-test")
    yield block_doc_id
    await MockInfrastructure.delete("this-is-a-test")


@pytest.fixture
async def block_work_pool(prefect_client, mock_infra_block_doc_id):
    block_schema = MockInfrastructure.schema()
    return await prefect_client.create_work_pool(
        WorkPoolCreate(
            name="test",
            type="block",
            base_job_template={
                "job_configuration": {"block": "{{ block }}"},
                "variables": {
                    "type": "object",
                    "properties": {
                        "block": {
                            "title": "Block",
                            "description": (
                                "The infrastructure block to use for job creation."
                            ),
                            "allOf": [
                                {"$ref": f"#/definitions/{MockInfrastructure.__name__}"}
                            ],
                            "default": {
                                "$ref": {
                                    "block_document_id": str(mock_infra_block_doc_id)
                                }
                            },
                        }
                    },
                    "required": ["block"],
                    "definitions": {MockInfrastructure.__name__: block_schema},
                },
            },
        )
    )


@pytest.fixture
async def block_worker_deployment(session, flow, block_work_pool):
    def hello(name: str):
        pass

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment 1",
            tags=["test"],
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=pendulum.duration(days=1).as_timedelta(),
                anchor_date=pendulum.datetime(2020, 1, 1),
            ),
            path="./subdir",
            entrypoint="/file.py:flow",
            parameter_openapi_schema=parameter_schema(hello),
            work_queue_id=block_work_pool.default_queue_id,
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def block_worker_deployment_with_infra_overrides(session, flow, block_work_pool):
    def hello(name: str):
        pass

    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Deployment 1",
            tags=["test"],
            flow_id=flow.id,
            schedule=schemas.schedules.IntervalSchedule(
                interval=pendulum.duration(days=1).as_timedelta(),
                anchor_date=pendulum.datetime(2020, 1, 1),
            ),
            path="./subdir",
            entrypoint="/file.py:flow",
            parameter_openapi_schema=parameter_schema(hello),
            infra_overrides={"field": "you've changed man", "env.test_value": "bloop"},
            work_queue_id=block_work_pool.default_queue_id,
        ),
    )
    await session.commit()
    return deployment


async def test_base_job_configuration_from_template_and_overrides():
    """Test that the job configuration is correctly built from the template and overrides"""
    block_schema = MockInfrastructure.schema()
    block = MockInfrastructure()
    block_document_id = await block.save("test")
    config = await BlockWorkerJobConfiguration.from_template_and_values(
        base_job_template={
            "job_configuration": {"block": "{{ block }}"},
            "variables": {
                "type": "object",
                "properties": {
                    "block": {
                        "title": "Block",
                        "description": (
                            "The infrastructure block to use for job creation."
                        ),
                        "allOf": [
                            {"$ref": f"#/definitions/{MockInfrastructure.__name__}"}
                        ],
                        "default": {
                            "$ref": {"block_document_id": str(block_document_id)}
                        },
                    }
                },
                "required": ["block"],
                "definitions": {MockInfrastructure.__name__: block_schema},
            },
        },
        values={},
    )
    assert config.dict() == {"block": block.dict()}


async def test_block_worker_run(
    block_worker,
    block_worker_deployment,
    block_work_pool,
    prefect_client,
    monkeypatch,
):
    @flow
    def test_flow():
        pass

    def create_run_with_deployment(state):
        return prefect_client.create_flow_run_from_deployment(
            block_worker_deployment.id, state=state
        )

    flow_runs = [
        await create_run_with_deployment(Pending()),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=5))
        ),
        await create_run_with_deployment(
            Scheduled(scheduled_time=pendulum.now("utc").add(seconds=20))
        ),
        await create_run_with_deployment(Running()),
        await create_run_with_deployment(Completed()),
        await prefect_client.create_flow_run(test_flow, state=Scheduled()),
    ]

    test_block = MockInfrastructure()
    await test_block.save("test-block-worker-run")
    monkeypatch.setattr(
        "prefect.workers.block.Block._from_block_document",
        lambda *args, **kwargs: test_block,
    )

    async with block_worker as worker:
        worker._work_pool = block_work_pool
        await worker.get_and_submit_flow_runs()

    assert MockInfrastructure._run.call_count == 3
    assert {
        call.kwargs["env"]["PREFECT__FLOW_RUN_ID"]
        for call in MockInfrastructure._run.call_args_list
    } == {str(fr.id) for fr in flow_runs[1:4]}


async def test_block_worker_run_infra_overrides(
    block_worker,
    block_worker_deployment_with_infra_overrides,
    block_work_pool,
    prefect_client,
    monkeypatch,
):
    @flow
    def test_flow():
        pass

    def create_run_with_deployment(state):
        return prefect_client.create_flow_run_from_deployment(
            block_worker_deployment_with_infra_overrides.id, state=state
        )

    await create_run_with_deployment(
        Scheduled(scheduled_time=pendulum.now("utc").subtract(days=1))
    )

    block = None
    original_from_block_document = copy(Block._from_block_document)

    def capture_block(block_doc):
        nonlocal block
        block = original_from_block_document(block_doc)
        return block

    monkeypatch.setattr(
        "prefect.workers.block.Block._from_block_document", capture_block
    )

    async with block_worker as worker:
        worker._work_pool = block_work_pool
        await worker.get_and_submit_flow_runs()

    assert block is not None, "Failed to capture block"
    assert block._run.call_args.kwargs["field"] == "you've changed man"
    assert block._run.call_args.kwargs["env"]["test_value"] == "bloop"


def legacy_named_cancelling_state(**kwargs):
    return Cancelled(name="Cancelling", **kwargs)


@pytest.mark.parametrize(
    "cancelling_constructor", [legacy_named_cancelling_state, Cancelling]
)
async def test_block_worker_cancellation(
    block_worker,
    prefect_client,
    block_worker_deployment,
    cancelling_constructor,
    monkeypatch,
    disable_enhanced_cancellation,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        block_worker_deployment.id,
        state=cancelling_constructor(),
    )
    await prefect_client.update_flow_run(
        flow_run_id=flow_run.id, infrastructure_pid="bloop"
    )

    block = None
    original_from_block_document = copy(Block._from_block_document)

    def capture_block(block_doc):
        nonlocal block
        block = original_from_block_document(block_doc)
        return block

    monkeypatch.setattr(
        "prefect.workers.block.Block._from_block_document", capture_block
    )

    async with block_worker as worker:
        await worker.sync_with_backend()
        await worker.check_for_cancelled_flow_runs()

    assert block is not None, "Failed to capture block"
    assert block._kill.call_args.kwargs["infrastructure_pid"] == "bloop"

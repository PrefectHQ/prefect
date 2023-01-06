import pydantic
import pytest

from prefect import get_client
from prefect.experimental.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
)
from prefect.orion import models
from prefect.orion.schemas.core import WorkerPool
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_WORKERS,
    PREFECT_EXPERIMENTAL_WARN_WORKERS,
    temporary_settings,
)

BASE_JOB_TEMPLATE = {
    "job_configuration": {"command": "{{ command }}"},
    "variables": {
        "command": {"type": "array", "title": "Command", "items": {"type": "string"}}
    },
    "required": [],
}


async def test_base_worker_gets_job_configuration_on_heartbeat(session, client):
    POOL_NAME = "test-pool"
    with temporary_settings(
        {PREFECT_EXPERIMENTAL_ENABLE_WORKERS: 1, PREFECT_EXPERIMENTAL_WARN_WORKERS: 0}
    ):

        # Create a worker pool with an empty job template
        response = await client.post(
            "/experimental/worker_pools/", json=dict(name=POOL_NAME, type="test-type")
        )
        result = pydantic.parse_obj_as(WorkerPool, response.json())
        model = await models.workers.read_worker_pool(
            session=session, worker_pool_id=result.id
        )
        assert model.name == POOL_NAME
        assert model.base_job_template == {}

        # Create a worker with the pool and heartbeat it to get the job configuration
        BaseWorker.__abstractmethods__ = set()
        BaseWorker.type = "test-type"
        worker = BaseWorker(
            name="test",
            worker_pool_name=POOL_NAME,
        )
        async with get_client() as client:
            worker._client = client
            worker.job_configuration = BaseJobConfiguration
            worker.job_configuration_variables = BaseVariables
            await worker.heartbeat_worker()

        assert worker.worker_pool.base_job_template == BASE_JOB_TEMPLATE


@pytest.mark.parametrize(
    "template,overrides,expected",
    [
        (
            {  # Base template with no overrides
                "job_configuration": {
                    "command": "{{ command }}",
                },
                "variables": {
                    "command": {
                        "type": "array",
                        "title": "Command",
                        "items": {"type": "string"},
                        "default": ["echo", "hello"],
                    }
                },
                "required": [],
            },
            {},  # No overrides
            {  # Expected result
                "command": ["echo", "hello"],
            },
        ),
    ],
)
def test_base_job_configuration_from_template_and_overrides(
    template, overrides, expected
):
    """Test that the job configuration is correctly built from the template and overrides"""
    config = BaseJobConfiguration.from_template_and_overrides(
        base_job_template=template, deployment_overrides=overrides
    )
    assert config.dict() == expected

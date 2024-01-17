import uuid
from functools import partial
from unittest.mock import MagicMock

import pendulum
import pytest
from packaging.version import Version

import prefect
from prefect import engine
from prefect.blocks.core import BlockNotSavedError
from prefect.infrastructure import (
    DockerContainer,
    Infrastructure,
    KubernetesJob,
    Process,
)
from prefect.infrastructure.base import MIN_COMPAT_PREFECT_VERSION
from prefect.server.schemas.core import Deployment
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_ENHANCED_CANCELLATION,
    PREFECT_EXPERIMENTAL_WARN_ENHANCED_CANCELLATION,
    temporary_settings,
)
from prefect.utilities.dockerutils import get_prefect_image_name


@pytest.fixture
def enable_enhanced_cancellation():
    with temporary_settings(
        updates={
            PREFECT_EXPERIMENTAL_ENABLE_ENHANCED_CANCELLATION: True,
            PREFECT_EXPERIMENTAL_WARN_ENHANCED_CANCELLATION: False,
        }
    ):
        yield


@pytest.fixture
async def patch_manifest_load(monkeypatch):
    async def patch_manifest(f):
        async def anon(*args, **kwargs):
            return f

        monkeypatch.setattr(
            engine,
            "load_flow_from_flow_run",
            anon,
        )
        return f

    return patch_manifest


@pytest.fixture(autouse=True)
def reset_mock_infrastructure():
    MockInfrastructure._run.reset_mock()
    yield


class MockInfrastructure(Infrastructure):
    type: str = "mock"

    _run = MagicMock()

    async def run(self, task_status=None):
        if task_status:
            task_status.started()
        self._run(self.dict(exclude={"block_type_slug"}))

    def preview(self):
        return self.json()

    class Config:
        arbitrary_types_allowed = True


@pytest.mark.skip(reason="Unclear failure.")
@pytest.mark.usefixtures("use_hosted_api_server")
@pytest.mark.parametrize(
    "infrastructure_type",
    [
        pytest.param(
            # This allows testing of against Kubernetes running in Docker Desktop
            partial(KubernetesJob, _api_dns_name="host.docker.internal"),
            marks=pytest.mark.service("kubernetes"),
            id="kubernetes-job",
        ),
        pytest.param(
            DockerContainer,
            marks=pytest.mark.service("docker"),
            id="docker-container",
        ),
        pytest.param(Process, id="process"),
    ],
)
async def test_flow_run_by_infrastructure_type(
    flow,
    deployment,
    infrastructure_type,
    prefect_client,
    patch_manifest_load,
):
    await patch_manifest_load(flow)
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    infrastructure = infrastructure_type().prepare_for_flow_run(flow_run)
    result = await infrastructure.run()

    flow_run = await prefect_client.read_flow_run(flow_run.id)
    assert flow_run.state.is_completed(), flow_run.state.message

    assert result.status_code == 0


async def test_submission_adds_flow_run_metadata(
    deployment,
    prefect_client,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    infrastructure = MockInfrastructure().prepare_for_flow_run(flow_run)
    await infrastructure.run()
    MockInfrastructure._run.assert_called_once_with(
        {
            "type": "mock",
            "env": {"PREFECT__FLOW_RUN_ID": str(flow_run.id)},
            "labels": {
                "prefect.io/flow-run-id": str(flow_run.id),
                "prefect.io/flow-run-name": flow_run.name,
                "prefect.io/version": prefect.__version__,
            },
            "name": flow_run.name,
            "command": ["prefect", "flow-run", "execute"],
        }
    )


@pytest.mark.parametrize(
    "deployment_fields,expected_labels",
    [
        (
            {"name": "test", "updated": pendulum.from_timestamp(1668099059.5)},
            {
                "prefect.io/deployment-name": "test",
                "prefect.io/deployment-updated": "2022-11-10T16:50:59.500000Z",
            },
        ),
        ({"name": "test", "updated": None}, {"prefect.io/deployment-name": "test"}),
    ],
)
async def test_submission_adds_deployment_metadata(
    deployment,
    prefect_client,
    deployment_fields,
    expected_labels,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    infrastructure = MockInfrastructure().prepare_for_flow_run(
        flow_run, deployment=Deployment(flow_id=deployment.flow_id, **deployment_fields)
    )
    await infrastructure.run()

    MockInfrastructure._run.assert_called_once_with(
        {
            "type": "mock",
            "env": {"PREFECT__FLOW_RUN_ID": str(flow_run.id)},
            "labels": {
                **{
                    "prefect.io/flow-run-id": str(flow_run.id),
                    "prefect.io/flow-run-name": flow_run.name,
                    "prefect.io/version": prefect.__version__,
                },
                **expected_labels,
            },
            "name": flow_run.name,
            "command": ["prefect", "flow-run", "execute"],
        }
    )


async def test_submission_adds_flow_metadata(
    deployment,
    prefect_client,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    flow = await prefect_client.read_flow(deployment.flow_id)
    infrastructure = MockInfrastructure().prepare_for_flow_run(flow_run, flow=flow)
    await infrastructure.run()
    MockInfrastructure._run.assert_called_once_with(
        {
            "type": "mock",
            "env": {"PREFECT__FLOW_RUN_ID": str(flow_run.id)},
            "labels": {
                "prefect.io/flow-run-id": str(flow_run.id),
                "prefect.io/flow-run-name": flow_run.name,
                "prefect.io/version": prefect.__version__,
                "prefect.io/flow-name": flow.name,
            },
            "name": flow_run.name,
            "command": ["prefect", "flow-run", "execute"],
        }
    )


async def test_submission_does_not_mutate_original_object(
    deployment,
    prefect_client,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    obj = MockInfrastructure()
    prepared = obj.prepare_for_flow_run(flow_run)
    await prepared.run()
    assert obj.env == {}
    assert obj.command is None
    assert obj.labels == {}
    assert obj.name is None


async def test_submission_does_not_override_existing_command(
    deployment,
    prefect_client,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    infrastructure = MockInfrastructure(command=["test"]).prepare_for_flow_run(flow_run)
    await infrastructure.run()
    MockInfrastructure._run.call_args[0][0]["command"] == ["test"]


async def test_submission_does_not_override_existing_env(
    deployment,
    prefect_client,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    infrastructure = MockInfrastructure(env={"foo": "bar"}).prepare_for_flow_run(
        flow_run
    )
    await infrastructure.run()
    MockInfrastructure._run.call_args[0][0]["env"] == {
        **Infrastructure._base_flow_run_environment(flow_run),
        "foo": "bar",
    }


async def test_submission_does_not_override_existing_labels(
    deployment,
    prefect_client,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    infrastructure = MockInfrastructure(labels={"foo": "bar"}).prepare_for_flow_run(
        flow_run
    )
    await infrastructure.run()
    MockInfrastructure._run.call_args[0][0]["labels"] == {
        **Infrastructure._base_flow_run_labels(flow_run),
        "foo": "bar",
    }


async def test_submission_does_not_override_existing_name(
    deployment,
    prefect_client,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    infrastructure = MockInfrastructure(name="test").prepare_for_flow_run(flow_run)
    await infrastructure.run()
    MockInfrastructure._run.call_args[0][0]["name"] == "test"


@pytest.mark.skip("Flaky test that needs investigation")
@pytest.mark.service("docker")
@pytest.mark.usefixtures("use_hosted_api_server")
@pytest.mark.skipif(
    (Version(MIN_COMPAT_PREFECT_VERSION) > Version(prefect.__version__.split("+")[0])),
    reason=f"Expected breaking change in next version: {MIN_COMPAT_PREFECT_VERSION}",
)
async def test_execution_is_compatible_with_old_prefect_container_version(
    flow_run,
    prefect_client,
    deployment,
):
    """
    This test confirms that submission can properly start a flow run in a container
    running an old version of Prefect. This tests for regression in the path of
    "starting a flow run" as well as basic API communication.

    When making a breaking change to the API, it's likely that no compatible image
    will exist. If so, bump MIN_COMPAT_PREFECT_VERSION past the current prefect
    version and this test will be skipped until a compatible image can be found.
    """
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment.id
    )

    infrastructure = DockerContainer(
        image=get_prefect_image_name(MIN_COMPAT_PREFECT_VERSION)
    ).prepare_for_flow_run(flow_run)

    result = await infrastructure.run()
    assert result.status_code == 0
    flow_run = await prefect_client.read_flow_run(flow_run.id)
    assert flow_run.state.is_completed()


async def test_enabling_enhanced_cancellation_changes_default_command(
    deployment, prefect_client, enable_enhanced_cancellation
):
    flow_run = await prefect_client.create_flow_run_from_deployment(deployment.id)
    infrastructure = MockInfrastructure(name="test").prepare_for_flow_run(flow_run)
    assert infrastructure.command == ["prefect", "flow-run", "execute"]


async def test_generate_work_pool_base_job_template():
    block = MockInfrastructure()
    block._block_document_id = uuid.uuid4()

    expected_template = {
        "job_configuration": {"block": "{{ block }}"},
        "variables": {
            "type": "object",
            "properties": {
                "block": {
                    "title": "Block",
                    "description": "The infrastructure block to use for job creation.",
                    "allOf": [{"$ref": "#/definitions/MockInfrastructure"}],
                    "default": {
                        "$ref": {"block_document_id": str(block._block_document_id)}
                    },
                }
            },
            "required": ["block"],
            "definitions": {"MockInfrastructure": block.schema()},
        },
    }

    template = await block.generate_work_pool_base_job_template()

    assert template == expected_template


@pytest.mark.parametrize(
    "work_pool_name",
    [
        "my_work_pool",
        (None),
    ],
)
async def test_publish_as_work_pool(
    work_pool_name, monkeypatch, capsys, prefect_client
):
    block = MockInfrastructure()
    block._block_document_id = uuid.uuid4()
    block._block_document_name = "my_block"

    expected_template = {
        "job_configuration": {"block": "{{ block }}"},
        "variables": {
            "type": "object",
            "properties": {
                "block": {
                    "title": "Block",
                    "description": "The infrastructure block to use for job creation.",
                    "allOf": [{"$ref": "#/definitions/MockInfrastructure"}],
                    "default": {
                        "$ref": {"block_document_id": str(block._block_document_id)}
                    },
                }
            },
            "required": ["block"],
            "definitions": {"MockInfrastructure": block.schema()},
        },
    }

    await block.publish_as_work_pool(work_pool_name)

    if work_pool_name is None:
        assert (
            f"Work pool {block._block_document_name} created!"
            in capsys.readouterr().out
        )
    else:
        assert f"Work pool {work_pool_name} created!" in capsys.readouterr().out

    work_pool = await prefect_client.read_work_pool(
        work_pool_name=work_pool_name or block._block_document_name
    )

    assert work_pool.name == work_pool_name or block._block_document_name

    assert work_pool.type == "block"

    assert work_pool.base_job_template == expected_template


async def test_publish_as_work_pool_raises_if_block_not_saved():
    block = MockInfrastructure()

    with pytest.raises(
        BlockNotSavedError,
        match="Cannot publish as work pool, block has not been saved",
    ):
        await block.publish_as_work_pool("my_work_pool")

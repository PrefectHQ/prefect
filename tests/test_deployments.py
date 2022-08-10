from pathlib import Path

import pytest
from pydantic.error_wrappers import ValidationError

from prefect import Flow
from prefect.blocks.core import Block
from prefect.deployments import Deployment, load_flow_from_flow_run
from prefect.infrastructure import Process
from prefect.orion import models, schemas

WORKING_DIR = (Path(__file__).parent / "test-projects" / "nested-project").absolute()


@pytest.fixture
async def old_deployment(session, flow):
    manifest_path = WORKING_DIR / "foobar-manifest.json"
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Nested Project",
            tags=["test"],
            flow_id=flow.id,
            manifest_path=str(manifest_path),
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def old_flow_run(orion_client, old_deployment):
    return await orion_client.create_flow_run_from_deployment(old_deployment.id)


@pytest.fixture
async def stored_deployment(session, flow):
    path = WORKING_DIR
    deployment = await models.deployments.create_deployment(
        session=session,
        deployment=schemas.core.Deployment(
            name="My Nested Project",
            tags=["test"],
            flow_id=flow.id,
            path=str(path),
            entrypoint="implicit_relative.py:foobar",
        ),
    )
    await session.commit()
    return deployment


@pytest.fixture
async def stored_flow_run(orion_client, stored_deployment):
    return await orion_client.create_flow_run_from_deployment(stored_deployment.id)


class TestLoadFlow:
    async def test_flow_load_from_oldstyle_manifest(self, old_flow_run):
        flow = await load_flow_from_flow_run(old_flow_run, ignore_storage=True)
        assert isinstance(flow, Flow)
        assert flow.name == "foobar"

    async def test_flow_load_from_new_path(self, stored_flow_run):
        flow = await load_flow_from_flow_run(stored_flow_run, ignore_storage=True)
        assert isinstance(flow, Flow)
        assert flow.name == "foobar"


class TestDeploymentBasicInterface:
    async def test_that_name_is_required(self):
        with pytest.raises(ValidationError, match="field required"):
            Deployment()

    async def test_that_infrastructure_defaults_to_process(self):
        d = Deployment(name="foo")
        assert isinstance(d.infrastructure, Process)


class TestDeploymentLoad:
    async def test_deployment_load_hydrates_with_server_settings(
        self, orion_client, flow, storage_document_id, infrastructure_document_id
    ):
        response = await orion_client.create_deployment(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            infrastructure_document_id=infrastructure_document_id,
            infra_overrides={"limits.cpu": 24},
            storage_document_id=storage_document_id,
        )

        d = Deployment(name="My Deployment", flow_name=flow.name)

        # sanity check that no load occurred yet
        assert d.version is None
        assert d.tags == []
        assert d.parameters == {}

        assert await d.load()

        assert d.name == "My Deployment"
        assert d.flow_name == flow.name
        assert d.version == "mint"
        assert d.path == "/"
        assert d.entrypoint == "/file.py:flow"
        assert d.tags == ["foo"]
        assert d.parameters == {"foo": "bar"}
        assert d.infra_overrides == {"limits.cpu": 24}

        infra_document = await orion_client.read_block_document(
            infrastructure_document_id
        )
        infrastructure_block = Block._from_block_document(infra_document)
        assert d.infrastructure == infrastructure_block

        storage_document = await orion_client.read_block_document(storage_document_id)
        storage_block = Block._from_block_document(storage_document)
        assert d.storage == storage_block

    async def test_deployment_load_gracefully_errors_when_no_deployment_found(self):
        d = Deployment(name="Abba", flow_name="Dancing Queen")
        assert not await d.load()

        # sanity check that no load occurred yet
        assert d.version is None
        assert d.tags == []
        assert d.parameters == {}

    async def test_raises_informatively_if_cant_pull(self):
        d = Deployment(name="test")
        with pytest.raises(ValueError, match="flow name must be provided"):
            await d.load()


class TestDeploymentUpload:
    async def test_uploading_with_no_storage_sets_path(self):
        d = Deployment(name="foo", flow_name="bar")
        assert d.path is None
        await d.upload_to_storage()
        assert d.path


class TestDeploymentBuild:
    async def test_build_from_flow_sets_flow_name(self, flow_function):
        d = Deployment(name="foo")
        assert d.flow_name is None

        await d.build_from_flow(flow_function)
        assert d.flow_name == flow_function.name

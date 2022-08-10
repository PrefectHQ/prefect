import pytest
from pydantic.error_wrappers import ValidationError

from prefect.blocks.core import Block
from prefect.deployments import Deployment
from prefect.infrastructure import Process


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

    async def test_deployment_load_doesnt_overwrite_set_fields(
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

        d = Deployment(
            name="My Deployment", flow_name=flow.name, version="ABC", storage=None
        )
        assert await d.load()

        assert d.name == "My Deployment"
        assert d.flow_name == flow.name
        assert d.version == "ABC"
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
        assert d.storage is None

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

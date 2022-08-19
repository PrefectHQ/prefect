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

    async def test_default_work_queue_name(self):
        d = Deployment(name="foo")
        assert d.work_queue_name == "default"


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
    async def test_build_from_flow_requires_name(self, flow_function):
        with pytest.raises(TypeError, match="required positional argument: 'name'"):
            d = await Deployment.build_from_flow(flow=flow_function)

        with pytest.raises(ValueError, match="name must be provided"):
            d = await Deployment.build_from_flow(flow=flow_function, name=None)

    async def test_build_from_flow_sets_flow_name(self, flow_function):
        d = await Deployment.build_from_flow(flow=flow_function, name="foo")
        assert d.flow_name == flow_function.name
        assert d.name == "foo"

    async def test_build_from_flow_sets_description_and_version_if_not_set(
        self, flow_function
    ):
        d = await Deployment.build_from_flow(
            flow=flow_function, name="foo", description="a", version="b"
        )
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.description == "a"
        assert d.version == "b"

        d = await Deployment.build_from_flow(flow=flow_function, name="foo")
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.description == flow_function.description
        assert d.version == flow_function.version

    async def test_build_from_flow_sets_provided_attrs(self, flow_function):
        d = await Deployment.build_from_flow(
            flow_function,
            name="foo",
            tags=["A", "B"],
            description="foobar",
            version="12",
        )
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.description == "foobar"
        assert d.tags == ["A", "B"]
        assert d.version == "12"


class TestYAML:
    def test_yaml_comment_for_work_queue(self, tmp_path):
        d = Deployment(name="yaml", flow_name="test")
        yaml_path = str(tmp_path / "dep.yaml")
        d.to_yaml(yaml_path)
        with open(yaml_path, "r") as f:
            contents = f.readlines()

        comment_index = contents.index(
            "# The work queue that will handle this deployment's runs\n"
        )
        assert contents[comment_index + 1] == "work_queue_name: default\n"

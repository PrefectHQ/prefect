import pytest
import yaml
from pydantic.error_wrappers import ValidationError

from prefect.blocks.core import Block
from prefect.deployments import Deployment
from prefect.exceptions import BlockMissingCapabilities
from prefect.filesystems import S3, GitHub, LocalFileSystem
from prefect.infrastructure import DockerContainer, Infrastructure, Process


class TestDeploymentBasicInterface:
    async def test_that_name_is_required(self):
        with pytest.raises(ValidationError, match="field required"):
            Deployment()

    async def test_that_infra_block_capabilities_are_validated(self):
        bad_infra = LocalFileSystem(basepath=".")

        with pytest.raises(ValueError, match="'run-infrastructure' capabilities"):
            Deployment(name="foo", infrastructure=bad_infra)

    async def test_that_storage_block_capabilities_are_validated(self):
        bad_storage = Process()

        with pytest.raises(ValueError, match="'get-directory' capabilities"):
            Deployment(name="foo", storage=bad_storage)

    async def test_that_infrastructure_defaults_to_process(self):
        d = Deployment(name="foo")
        assert isinstance(d.infrastructure, Process)

    async def test_infrastructure_accepts_arbitrary_infra_types(self):
        class CustomInfra(Infrastructure):
            type = "CustomInfra"

            def run(self):
                return 42

            def preview(self):
                return "woof!"

        d = Deployment(name="foo", infrastructure=CustomInfra())
        assert isinstance(d.infrastructure, CustomInfra)

    async def test_infrastructure_accepts_arbitrary_infra_types_as_dicts(self):
        class CustomInfra(Infrastructure):
            type = "CustomInfra"

            def run(self):
                return 42

            def preview(self):
                return "woof!"

        d = Deployment(name="foo", infrastructure=CustomInfra().dict())
        assert isinstance(d.infrastructure, CustomInfra)

    async def test_default_work_queue_name(self):
        d = Deployment(name="foo")
        assert d.work_queue_name == "default"

    async def test_location(self):
        storage = S3(bucket_path="test-bucket")

        d = Deployment(name="foo", storage=storage)
        assert d.location == "s3://test-bucket/"

        d = Deployment(name="foo", storage=storage, path="subdir")
        assert d.location == "s3://test-bucket/subdir"

        d = Deployment(name="foo", path="/full/path/to/flow/")
        assert d.location == "/full/path/to/flow/"


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
    async def test_uploading_with_unsaved_storage_creates_anon_block(self, tmp_path):
        fs = LocalFileSystem(basepath=str(tmp_path))

        async def do_nothing(**kwargs):
            pass

        fs.put_directory = do_nothing

        d = Deployment(name="foo", flow_name="bar", storage=fs)

        assert d.storage._is_anonymous is None
        assert d.storage._block_document_id is None

        await d.upload_to_storage(ignore_file=None)

        assert d.storage._is_anonymous is True
        assert d.storage._block_document_id

    async def test_uploading_with_saved_storage_does_not_copy(self, tmp_path):
        fs = LocalFileSystem(basepath=str(tmp_path))
        await fs.save(name="save-test")

        async def do_nothing(**kwargs):
            pass

        fs.put_directory = do_nothing

        d = Deployment(name="foo", flow_name="bar", storage=fs)

        assert d.storage._is_anonymous is False
        old_id = d.storage._block_document_id

        await d.upload_to_storage(ignore_file=None)

        assert d.storage._is_anonymous is False
        assert d.storage._block_document_id == old_id

    async def test_uploading_with_readonly_storage_raises(self, tmp_path):
        storage = GitHub(repository="prefect")

        d = Deployment(name="foo", flow_name="bar", storage=storage)

        with pytest.raises(
            BlockMissingCapabilities, match="'put-directory' capability"
        ):
            await d.upload_to_storage(ignore_file=None)

        d = Deployment(name="foo", flow_name="bar")
        await storage.save(name="readonly")

        with pytest.raises(
            BlockMissingCapabilities, match="'put-directory' capability"
        ):
            await d.upload_to_storage(storage_block="github/readonly", ignore_file=None)


class TestDeploymentBuild:
    async def test_build_from_flow_requires_name(self, flow_function):
        with pytest.raises(TypeError, match="required positional argument: 'name'"):
            d = await Deployment.build_from_flow(flow=flow_function)

        with pytest.raises(ValueError, match="name must be provided"):
            d = await Deployment.build_from_flow(flow=flow_function, name=None)

    async def test_build_from_flow_raises_on_bad_inputs(self, flow_function):
        with pytest.raises(ValidationError, match="extra fields not permitted"):
            d = await Deployment.build_from_flow(
                flow=flow_function, name="foo", typo_attr="bar"
            )

    async def test_build_from_flow_sets_flow_name(self, flow_function):
        d = await Deployment.build_from_flow(flow=flow_function, name="foo")
        assert d.flow_name == flow_function.name
        assert d.name == "foo"

    @pytest.mark.parametrize("skip_upload", [True, False])
    async def test_build_from_flow_sets_path(self, flow_function, skip_upload):
        d = await Deployment.build_from_flow(
            flow=flow_function, name="foo", skip_upload=skip_upload
        )
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.path is not None

    async def test_build_from_flow_doesnt_overwrite_path(self, flow_function):
        d = await Deployment.build_from_flow(
            flow=flow_function, name="foo", path="/my/custom/path"
        )
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.path == "/my/custom/path"

    async def test_build_from_flow_gracefully_handles_readonly_storage(
        self, flow_function
    ):
        storage = GitHub(repository="prefect")
        d = await Deployment.build_from_flow(
            flow=flow_function, name="foo", storage=storage
        )
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.path is None

    async def test_build_from_flow_manages_docker_specific_path(self, flow_function):
        # default, local within-container storage assumption
        d = await Deployment.build_from_flow(
            flow=flow_function, name="foo", infrastructure=DockerContainer()
        )
        assert d.path == "/opt/prefect/flows"

        # can be overriden
        d = await Deployment.build_from_flow(
            flow=flow_function,
            name="foo",
            infrastructure=DockerContainer(),
            path="/my/path/of/choice",
        )
        assert d.path == "/my/path/of/choice"

        # remote storage, path is unimportant
        for path in [None, "subdir"]:
            d = await Deployment.build_from_flow(
                flow=flow_function,
                name="foo",
                infrastructure=DockerContainer(),
                storage=S3(bucket_path="unreal"),
                skip_upload=True,
                path=path,
            )
            assert d.path == path

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

    async def test_build_from_flow_sets_correct_entrypoint(self, flow_function):
        """
        Entrypoints are *always* relative to {storage.basepath / path}
        """
        d = await Deployment.build_from_flow(
            flow=flow_function, name="foo", description="a", version="b"
        )
        d.entrypoint == "tests/fixtures/client.py:client_test_flow"

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
    def test_deployment_yaml_roundtrip(self, tmp_path):
        storage = LocalFileSystem(basepath=".")
        infrastructure = Process()

        d = Deployment(
            name="yaml",
            flow_name="test",
            storage=storage,
            infrastructure=infrastructure,
            tags=["A", "B"],
        )
        yaml_path = str(tmp_path / "dep.yaml")
        d.to_yaml(yaml_path)

        new_d = Deployment.load_from_yaml(yaml_path)
        assert new_d.name == "yaml"
        assert new_d.tags == ["A", "B"]
        assert new_d.flow_name == "test"
        assert new_d.storage == storage
        assert new_d.infrastructure == infrastructure

    async def test_deployment_yaml_roundtrip_handles_secret_values(self, tmp_path):
        storage = S3(
            bucket_path="unreal",
            aws_access_key_id="fake",
            aws_secret_access_key="faker",
        )

        # save so that secret values are persisted somewhere
        await storage.save("test-me-with-secrets")
        infrastructure = Process()

        d = Deployment(
            name="yaml",
            flow_name="test",
            storage=storage,
            infrastructure=infrastructure,
            tags=["A", "B"],
        )
        yaml_path = str(tmp_path / "dep.yaml")
        await d.to_yaml(yaml_path)

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        # ensure secret values are hidden
        assert set(data["storage"]["aws_access_key_id"]) == {"*"}
        assert set(data["storage"]["aws_secret_access_key"]) == {"*"}

        # ensure secret values are re-hydrated
        new_d = await Deployment.load_from_yaml(yaml_path)
        assert new_d.storage.aws_access_key_id.get_secret_value() == "fake"
        assert new_d.storage.aws_secret_access_key.get_secret_value() == "faker"

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

import re
from uuid import uuid4

import pendulum
import pytest
import respx
import yaml
from httpx import Response
from pydantic.error_wrappers import ValidationError

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect import flow, task
from prefect.blocks.core import Block
from prefect.blocks.fields import SecretDict
from prefect.client.orchestration import PrefectClient
from prefect.deployments import Deployment, run_deployment
from prefect.exceptions import BlockMissingCapabilities
from prefect.filesystems import S3, GitHub, LocalFileSystem
from prefect.infrastructure import DockerContainer, Infrastructure, Process
from prefect.server.schemas import states
from prefect.server.schemas.core import TaskRunResult
from prefect.settings import PREFECT_API_URL
from prefect.utilities.slugify import slugify


@pytest.fixture(autouse=True)
async def ensure_default_agent_pool_exists(session):
    # The default agent work pool is created by a migration, but is cleared on
    # consecutive test runs. This fixture ensures that the default agent work
    # pool exists before each test.
    default_work_pool = await models.workers.read_work_pool_by_name(
        session=session, work_pool_name=models.workers.DEFAULT_AGENT_WORK_POOL_NAME
    )
    if default_work_pool is None:
        await models.workers.create_work_pool(
            session=session,
            work_pool=schemas.actions.WorkPoolCreate(
                name=models.workers.DEFAULT_AGENT_WORK_POOL_NAME, type="prefect-agent"
            ),
        )
        await session.commit()


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

    async def test_build_from_flow_sets_description(self, flow_function):
        description = "test description"
        d = await Deployment.build_from_flow(
            flow=flow_function, description=description, name="foo"
        )
        assert d.description == description

    async def test_description_defaults_to_flow_description(self, flow_function):
        d = await Deployment.build_from_flow(flow=flow_function, name="foo")
        assert d.description == flow_function.description

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
            is_schedule_active=False,
        )
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.description == "foobar"
        assert d.tags == ["A", "B"]
        assert d.version == "12"
        assert d.is_schedule_active == False

    async def test_build_from_flow_doesnt_load_existing(self, flow_function):
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

        d = await Deployment.build_from_flow(
            flow_function,
            name="foo",
            version="12",
            load_existing=False,
        )
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.description != "foobar"
        assert d.tags != ["A", "B"]
        assert d.version == "12"

    @pytest.mark.parametrize(
        "is_active",
        [True, False, None],
    )
    async def test_deployment_schedule_active_behaviors(self, flow_function, is_active):
        d = await Deployment.build_from_flow(
            flow_function,
            name="foo",
            tags=["A", "B"],
            description="foobar",
            version="12",
            is_schedule_active=is_active,
        )
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.is_schedule_active == is_active


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
        assert new_d.name == d.name
        assert new_d.name == "yaml"
        assert new_d.tags == ["A", "B"]
        assert new_d.flow_name == "test"
        assert new_d.storage == storage
        assert new_d.infrastructure == infrastructure

    @pytest.mark.parametrize(
        "is_schedule_active",
        [True, False, None],
    )
    def test_deployment_yaml_roundtrip_for_schedule_active(
        self, tmp_path, is_schedule_active
    ):
        storage = LocalFileSystem(basepath=".")
        infrastructure = Process()

        d = Deployment(
            name="yaml",
            flow_name="test",
            storage=storage,
            infrastructure=infrastructure,
            tags=["A", "B"],
            is_schedule_active=is_schedule_active,
        )
        yaml_path = str(tmp_path / "dep.yaml")
        d.to_yaml(yaml_path)

        new_d = Deployment.load_from_yaml(yaml_path)
        assert new_d.name == d.name
        assert new_d.name == "yaml"
        assert new_d.is_schedule_active == is_schedule_active

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

    async def test_deployment_yaml_roundtrip_handles_secret_dict(self, tmp_path):
        class CustomCredentials(Block):
            auth_info: SecretDict

        class CustomInfra(Infrastructure):
            type = "CustomInfra"
            credentials: CustomCredentials

            def run(self):  # needed because abstract method
                return 42

            def preview(self):  # abstract method
                return "woof!"

        custom_creds = CustomCredentials(auth_info={"key": "val"})
        custom_infra = CustomInfra(credentials=custom_creds)
        await custom_infra.save("test-me-with-secrets")

        d = Deployment(
            name="yaml",
            infrastructure=custom_infra,
        )
        yaml_path = str(tmp_path / "dep.yaml")
        await d.to_yaml(yaml_path)
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        # ensure secret values are hidden
        auth_info = data["infrastructure"]["credentials"]["auth_info"]
        assert len(auth_info) == 1
        assert set(auth_info["key"]) == {"*"}

        # ensure secret values are re-hydrated
        new_d = await Deployment.load_from_yaml(yaml_path)
        auth_info = new_d.infrastructure.credentials.auth_info
        assert auth_info.get_secret_value() == {"key": "val"}

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


@flow
def ad_hoc_flow():
    pass


@pytest.fixture
def dep_path():
    return "./dog.py"


@pytest.fixture
def patch_import(monkeypatch):
    @flow(description="Need a non-trivial description here.", version="A")
    def fn():
        pass

    monkeypatch.setattr("prefect.utilities.importtools.import_object", lambda path: fn)


@pytest.fixture
async def test_deployment(patch_import, tmp_path):
    d = Deployment(name="TEST", flow_name="fn")
    deployment_id = await d.apply()
    return d, deployment_id


class TestDeploymentApply:
    async def test_deployment_apply_updates_concurrency_limit(
        self,
        patch_import,
        tmp_path,
        orion_client,
    ):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        deployment_id = await d.apply(work_queue_concurrency=424242)
        queue_name = d.work_queue_name
        work_queue = await orion_client.read_work_queue_by_name(queue_name)
        assert work_queue.concurrency_limit == 424242

    @pytest.mark.parametrize(
        "provided, expected",
        [(True, True), (False, False), (None, True)],
    )
    async def test_deployment_is_active_behaves_as_expected(
        self, flow_function, provided, expected, orion_client
    ):
        d = await Deployment.build_from_flow(
            flow_function,
            name="foo",
            tags=["A", "B"],
            description="foobar",
            version="12",
            is_schedule_active=provided,
        )
        assert d.flow_name == flow_function.name
        assert d.name == "foo"
        assert d.is_schedule_active is provided

        dep_id = await d.apply()
        dep = await orion_client.read_deployment(dep_id)
        assert dep.is_schedule_active == expected


class TestRunDeployment:
    @pytest.mark.parametrize(
        "terminal_state", list(sorted(s.name for s in states.TERMINAL_STATES))
    )
    def test_running_a_deployment_blocks_until_termination(
        self,
        test_deployment,
        use_hosted_orion,
        terminal_state,
    ):
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
        ) as router:
            poll_responses = [
                Response(
                    200, json={**mock_flowrun_response, "state": {"type": "PENDING"}}
                ),
                Response(
                    200, json={**mock_flowrun_response, "state": {"type": "RUNNING"}}
                ),
                Response(
                    200,
                    json={**mock_flowrun_response, "state": {"type": terminal_state}},
                ),
            ]

            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.get(re.compile("/flow_runs/.*")).mock(
                side_effect=poll_responses
            )

            assert (
                run_deployment(
                    f"{d.flow_name}/{d.name}", timeout=2, poll_interval=0
                ).state.type
                == terminal_state
            ), "run_deployment does not exit on {terminal_state}"
            assert len(flow_polls.calls) == 3

    @pytest.mark.parametrize(
        "terminal_state", list(sorted(s.name for s in states.TERMINAL_STATES))
    )
    async def test_running_a_deployment_blocks_until_termination_async(
        self,
        test_deployment,
        use_hosted_orion,
        terminal_state,
    ):
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        async with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
        ) as router:
            poll_responses = [
                Response(
                    200, json={**mock_flowrun_response, "state": {"type": "PENDING"}}
                ),
                Response(
                    200, json={**mock_flowrun_response, "state": {"type": "RUNNING"}}
                ),
                Response(
                    200,
                    json={**mock_flowrun_response, "state": {"type": terminal_state}},
                ),
            ]

            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.get(re.compile("/flow_runs/.*")).mock(
                side_effect=poll_responses
            )

            assert (
                await run_deployment(
                    f"{d.flow_name}/{d.name}",
                    timeout=2,
                    poll_interval=0,
                )
            ).state.type == terminal_state, (
                "run_deployment does not exit on {terminal_state}"
            )
            assert len(flow_polls.calls) == 3

    async def test_run_deployment_with_ephemeral_api(
        self,
        test_deployment,
        orion_client,
    ):
        d, deployment_id = test_deployment

        flow_run = await run_deployment(
            f"{d.flow_name}/{d.name}",
            timeout=0,
            poll_interval=0,
            client=orion_client,
        )
        assert flow_run.deployment_id == deployment_id
        assert flow_run.state

    def test_returns_flow_run_on_timeout(
        self,
        test_deployment,
        use_hosted_orion,
    ):
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        with respx.mock(
            base_url=PREFECT_API_URL.value(), assert_all_mocked=True
        ) as router:
            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(
                return_value=Response(
                    200, json={**mock_flowrun_response, "state": {"type": "SCHEDULED"}}
                )
            )

            flow_run = run_deployment(
                f"{d.flow_name}/{d.name}", timeout=1, poll_interval=0
            )
            assert len(flow_polls.calls) > 0
            assert flow_run.state

    def test_returns_flow_run_immediately_when_timeout_is_zero(
        self,
        test_deployment,
        use_hosted_orion,
    ):
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
            assert_all_called=False,
        ) as router:
            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(
                return_value=Response(
                    200, json={**mock_flowrun_response, "state": {"type": "SCHEDULED"}}
                )
            )

            flow_run = run_deployment(
                f"{d.flow_name}/{d.name}", timeout=0, poll_interval=0
            )
            assert len(flow_polls.calls) == 0
            assert flow_run.state.is_scheduled()

    def test_polls_indefinitely(
        self,
        test_deployment,
        use_hosted_orion,
    ):
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        side_effects = [
            Response(
                200, json={**mock_flowrun_response, "state": {"type": "SCHEDULED"}}
            )
        ] * 99
        side_effects.append(
            Response(
                200, json={**mock_flowrun_response, "state": {"type": "COMPLETED"}}
            )
        )

        with respx.mock(
            base_url=PREFECT_API_URL.value(),
            assert_all_mocked=True,
            assert_all_called=False,
        ) as router:
            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(side_effect=side_effects)

            run_deployment(f"{d.flow_name}/{d.name}", timeout=None, poll_interval=0)
            assert len(flow_polls.calls) == 100

    def test_schedules_immediately_by_default(self, test_deployment, use_hosted_orion):
        d, deployment_id = test_deployment

        scheduled_time = pendulum.now()
        flow_run = run_deployment(
            f"{d.flow_name}/{d.name}",
            timeout=0,
            poll_interval=0,
        )

        assert (flow_run.expected_start_time - scheduled_time).total_seconds() < 1

    def test_accepts_custom_scheduled_time(self, test_deployment, use_hosted_orion):
        d, deployment_id = test_deployment

        scheduled_time = pendulum.now() + pendulum.Duration(minutes=5)
        flow_run = run_deployment(
            f"{d.flow_name}/{d.name}",
            scheduled_time=scheduled_time,
            timeout=0,
            poll_interval=0,
        )

        assert (flow_run.expected_start_time - scheduled_time).total_seconds() < 1

    def test_custom_flow_run_names(self, test_deployment, use_hosted_orion):
        d, deployment_id = test_deployment

        flow_run = run_deployment(
            f"{d.flow_name}/{d.name}",
            flow_run_name="a custom flow run name",
            timeout=0,
            poll_interval=0,
        )

        assert flow_run.name == "a custom flow run name"

    def test_accepts_tags(self, test_deployment):
        d, deployment_id = test_deployment

        flow_run = run_deployment(
            f"{d.flow_name}/{d.name}",
            tags=["I", "love", "prefect"],
            timeout=0,
            poll_interval=0,
        )

        assert sorted(flow_run.tags) == ["I", "love", "prefect"]

    def test_accepts_idempotency_key(self, test_deployment):
        d, deployment_id = test_deployment

        flow_run_a = run_deployment(
            f"{d.flow_name}/{d.name}",
            idempotency_key="12345",
            timeout=0,
            poll_interval=0,
        )

        flow_run_b = run_deployment(
            f"{d.flow_name}/{d.name}",
            idempotency_key="12345",
            timeout=0,
            poll_interval=0,
        )

        assert flow_run_a.id == flow_run_b.id

    async def test_links_to_parent_flow_run_when_used_in_flow(
        self, test_deployment, use_hosted_orion, orion_client: PrefectClient
    ):
        d, deployment_id = test_deployment

        @flow
        def foo():
            return run_deployment(
                f"{d.flow_name}/{d.name}",
                timeout=0,
                poll_interval=0,
            )

        parent_state = foo(return_state=True)
        child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is not None
        task_run = await orion_client.read_task_run(child_flow_run.parent_task_run_id)
        assert task_run.flow_run_id == parent_state.state_details.flow_run_id
        assert slugify(f"{d.flow_name}/{d.name}") in task_run.task_key

    async def test_tracks_dependencies_when_used_in_flow(
        self, test_deployment, use_hosted_orion, orion_client
    ):
        d, deployment_id = test_deployment

        @task
        def bar():
            return "hello-world!!"

        @flow
        def foo():
            upstream_task_state = bar(return_state=True)
            upstream_result = upstream_task_state.result()
            child_flow_run = run_deployment(
                f"{d.flow_name}/{d.name}",
                timeout=0,
                poll_interval=0,
                parameters={"x": upstream_result},
            )
            return upstream_task_state, child_flow_run

        parent_state = foo(return_state=True)
        upstream_task_state, child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is not None
        task_run = await orion_client.read_task_run(child_flow_run.parent_task_run_id)
        assert task_run.task_inputs == {
            "x": [
                TaskRunResult(
                    input_type="task_run",
                    id=upstream_task_state.state_details.task_run_id,
                )
            ]
        }

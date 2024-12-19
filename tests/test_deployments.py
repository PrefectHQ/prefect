import datetime
import json
import re
from unittest import mock
from uuid import uuid4

import httpx
import pendulum
import pytest
import respx
import yaml
from httpx import Response

from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.objects import MinimalDeploymentSchedule
from prefect.client.schemas.schedules import CronSchedule, RRuleSchedule
from prefect.deployments.deployments import load_flow_from_flow_run

if HAS_PYDANTIC_V2:
    import pydantic.v1 as pydantic
    from pydantic.v1.error_wrappers import ValidationError
else:
    import pydantic
    from pydantic.error_wrappers import ValidationError

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect import flow, task
from prefect.blocks.core import Block
from prefect.blocks.fields import SecretDict
from prefect.client.orchestration import PrefectClient, get_client
from prefect.context import FlowRunContext
from prefect.deployments import Deployment, run_deployment
from prefect.events import DeploymentTriggerTypes
from prefect.events.schemas.deployment_triggers import DeploymentEventTrigger
from prefect.exceptions import BlockMissingCapabilities
from prefect.filesystems import S3, GitHub, LocalFileSystem
from prefect.infrastructure import DockerContainer, Infrastructure, Process
from prefect.server.schemas import states
from prefect.server.schemas.core import TaskRunResult
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_CLIENT_CSRF_SUPPORT_ENABLED,
    PREFECT_CLOUD_API_URL,
    PREFECT_EXPERIMENTAL_EVENTS,
    temporary_settings,
)
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


def test_deployment_emits_deprecation_warning():
    with pytest.warns(
        PrefectDeprecationWarning,
        match=(
            "prefect.deployments.deployments.Deployment has been deprecated."
            " It will not be available after Sep 2024."
            " Use `flow.deploy` to deploy your flows instead."
            " Refer to the upgrade guide for more information"
        ),
    ):
        Deployment(name="foo")


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

    def test_triggers_have_names(self):
        deployment = Deployment(
            name="TEST",
            flow_name="fn",
            triggers=[
                pydantic.parse_obj_as(DeploymentTriggerTypes, {}),
                pydantic.parse_obj_as(DeploymentTriggerTypes, {"name": "run-it"}),
            ],
        )

        assert deployment.triggers[0].name == "TEST__automation_1"
        assert deployment.triggers[1].name == "run-it"

    def test_triggers_have_job_variables(self):
        deployment = Deployment(
            name="TEST",
            flow_name="fn",
            triggers=[
                pydantic.parse_obj_as(DeploymentTriggerTypes, {}),
                pydantic.parse_obj_as(
                    DeploymentTriggerTypes, {"job_variables": {"foo": "bar"}}
                ),
            ],
        )

        assert deployment.triggers[0].job_variables is None
        assert deployment.triggers[1].job_variables == {"foo": "bar"}

    def test_enforce_parameter_schema_defaults_to_none(self):
        """
        enforce_parameter_schema defaults to None to allow for backwards compatibility
        with older servers
        """
        d = Deployment(name="foo")
        assert d.enforce_parameter_schema is None

    def test_schedule_rrule_count_param_raises(self):
        with pytest.raises(
            ValueError,
            match="RRule schedules with `COUNT` are not supported.",
        ):
            Deployment(
                name="foo",
                schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1;COUNT=1"),
            )

    def test_schedules_rrule_count_param_raises(self):
        with pytest.raises(
            ValueError,
            match="RRule schedules with `COUNT` are not supported.",
        ):
            Deployment(
                name="foo",
                schedules=[
                    MinimalDeploymentSchedule(
                        schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1;COUNT=1"),
                        active=True,
                    )
                ],
            )


class TestDeploymentLoad:
    async def test_deployment_load_hydrates_with_server_settings(
        self, prefect_client, flow, storage_document_id, infrastructure_document_id
    ):
        await prefect_client.create_deployment(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            infrastructure_document_id=infrastructure_document_id,
            job_variables={"limits.cpu": 24},
            storage_document_id=storage_document_id,
            schedules=[
                DeploymentScheduleCreate(
                    schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1"),
                    active=True,
                )
            ],
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
        assert d.job_variables == {"limits.cpu": 24}
        assert d.schedules == [
            MinimalDeploymentSchedule(
                schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1"),
                active=True,
            )
        ]

        infra_document = await prefect_client.read_block_document(
            infrastructure_document_id
        )
        infrastructure_block = Block._from_block_document(infra_document)
        assert d.infrastructure == infrastructure_block

        storage_document = await prefect_client.read_block_document(storage_document_id)
        storage_block = Block._from_block_document(storage_document)
        assert d.storage == storage_block

    async def test_deployment_load_doesnt_overwrite_set_fields(
        self, prefect_client, flow, storage_document_id, infrastructure_document_id
    ):
        await prefect_client.create_deployment(
            name="My Deployment",
            version="mint",
            path="/",
            entrypoint="/file.py:flow",
            flow_id=flow.id,
            tags=["foo"],
            parameters={"foo": "bar"},
            infrastructure_document_id=infrastructure_document_id,
            job_variables={"limits.cpu": 24},
            storage_document_id=storage_document_id,
        )

        d = Deployment(
            name="My Deployment",
            flow_name=flow.name,
            version="ABC",
            storage=None,
            schedules=[
                MinimalDeploymentSchedule(
                    schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1"),
                    active=True,
                )
            ],
        )
        assert await d.load()

        assert d.name == "My Deployment"
        assert d.flow_name == flow.name
        assert d.version == "ABC"
        assert d.path == "/"
        assert d.entrypoint == "/file.py:flow"
        assert d.tags == ["foo"]
        assert d.parameters == {"foo": "bar"}
        assert d.job_variables == {"limits.cpu": 24}
        assert d.schedules == [
            MinimalDeploymentSchedule(
                schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1"),
                active=True,
            )
        ]

        infra_document = await prefect_client.read_block_document(
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
            await Deployment.build_from_flow(flow=flow_function)

        with pytest.raises(ValueError, match="name must be provided"):
            await Deployment.build_from_flow(flow=flow_function, name=None)

    async def test_build_from_flow_raises_on_bad_inputs(self, flow_function):
        with pytest.raises(ValidationError, match="extra fields not permitted"):
            await Deployment.build_from_flow(
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

        # can be overridden
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
        assert d.is_schedule_active is False

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

    async def test_build_from_flow_set_schedules_shorthand(self, flow_function):
        deployment = await Deployment.build_from_flow(
            flow=flow_function,
            name="foo",
            schedules=[
                CronSchedule(cron="0 0 * * *"),
                {"schedule": {"interval": datetime.timedelta(minutes=10)}},
            ],
        )

        assert len(deployment.schedules) == 2
        assert all(
            isinstance(s, MinimalDeploymentSchedule) for s in deployment.schedules
        )

    async def test_build_from_flow_legacy_schedule_supported(
        self, flow_function, prefect_client
    ):
        deployment = await Deployment.build_from_flow(
            name="legacy_schedule_supported",
            flow=flow_function,
            schedule=CronSchedule(cron="2 1 * * *", timezone="America/Chicago"),
        )

        deployment_id = await deployment.apply()

        refreshed = await prefect_client.read_deployment(deployment_id)
        assert refreshed.schedule.cron == "2 1 * * *"

    async def test_build_from_flow_clear_schedules_via_legacy_schedule(
        self, flow_function, prefect_client
    ):
        deployment = await Deployment.build_from_flow(
            name="clear_schedules_via_legacy_schedule",
            flow=flow_function,
            schedule=CronSchedule(cron="2 1 * * *", timezone="America/Chicago"),
        )

        deployment_id = await deployment.apply()

        refreshed = await prefect_client.read_deployment(deployment_id)
        assert refreshed.schedule.cron == "2 1 * * *"

        deployment = await Deployment.build_from_flow(
            name="clear_schedules_via_legacy_schedule",
            flow=flow_function,
            schedule=None,
        )

        deployment_id_2 = await deployment.apply()
        assert deployment_id == deployment_id_2

        refreshed = await prefect_client.read_deployment(deployment_id)
        assert refreshed.schedule is None


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
            schedules=[
                MinimalDeploymentSchedule(
                    schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1"),
                    active=True,
                )
            ],
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
        assert new_d.schedules == [
            MinimalDeploymentSchedule(
                schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1"),
                active=True,
            )
        ]

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


@pytest.fixture
async def test_deployment_with_parameter_schema(patch_import, tmp_path):
    d = Deployment(
        name="TEST",
        flow_name="fn",
        enforce_parameter_schema=True,
        parameter_openapi_schema={
            "type": "object",
            "properties": {"1": {"type": "string"}, "2": {"type": "string"}},
        },
    )
    deployment_id = await d.apply()
    return d, deployment_id


class TestDeploymentApply:
    async def test_deployment_apply_updates_concurrency_limit(
        self,
        patch_import,
        tmp_path,
        prefect_client,
    ):
        d = Deployment(
            name="TEST",
            flow_name="fn",
        )
        await d.apply(work_queue_concurrency=424242)
        queue_name = d.work_queue_name
        work_queue = await prefect_client.read_work_queue_by_name(queue_name)
        assert work_queue.concurrency_limit == 424242

    async def test_deployment_apply_updates_schedules(
        self,
        patch_import,
        tmp_path,
        prefect_client,
    ):
        d = Deployment(
            name="TEST",
            flow_name="fn",
            schedules=[
                MinimalDeploymentSchedule(
                    schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1"),
                    active=True,
                )
            ],
        )
        dep_id = await d.apply()
        dep = await prefect_client.read_deployment(dep_id)

        assert len(dep.schedules) == 1
        assert dep.schedules[0].schedule == RRuleSchedule(
            rrule="FREQ=HOURLY;INTERVAL=1"
        )
        assert dep.schedules[0].active is True

    async def test_deployment_build_from_flow_clears_multiple_schedules(
        self,
        patch_import,
        flow_function,
        tmp_path,
        prefect_client,
    ):
        d = await Deployment.build_from_flow(
            flow_function,
            name="TEST",
            schedules=[
                MinimalDeploymentSchedule(
                    schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=1"),
                    active=True,
                ),
                MinimalDeploymentSchedule(
                    schedule=RRuleSchedule(rrule="FREQ=HOURLY;INTERVAL=60"),
                    active=True,
                ),
            ],
        )
        dep_id = await d.apply()
        dep = await prefect_client.read_deployment(dep_id)

        expected_rrules = {"FREQ=HOURLY;INTERVAL=1", "FREQ=HOURLY;INTERVAL=60"}

        assert dep.schedule
        assert set([s.schedule.rrule for s in dep.schedules]) == expected_rrules

        # Apply an empty list of schedules to clear schedules.
        d2 = await Deployment.build_from_flow(
            flow_function,
            name="TEST",
            schedules=[],
        )
        await d2.apply()
        assert d2.schedules == []
        assert d2.schedule is None

        # Check the API to make sure the schedules are cleared there, too.
        modified_dep = await prefect_client.read_deployment(dep_id)
        assert modified_dep.schedules == []
        assert modified_dep.schedule is None

    @pytest.mark.parametrize(
        "provided, expected",
        [(True, True), (False, False), (None, True)],
    )
    async def test_deployment_is_active_behaves_as_expected(
        self, flow_function, provided, expected, prefect_client
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
        dep = await prefect_client.read_deployment(dep_id)
        assert dep.is_schedule_active == expected

    async def test_deployment_apply_syncs_triggers_to_cloud_api(
        self,
        patch_import,
        tmp_path,
    ):
        infrastructure = Process()
        await infrastructure._save(is_anonymous=True)

        trigger = pydantic.parse_obj_as(
            DeploymentTriggerTypes, {"job_variables": {"foo": 123}}
        )

        deployment = Deployment(
            name="TEST",
            flow_name="fn",
            triggers=[trigger],
            infrastructure=infrastructure,
        )

        created_deployment_id = str(uuid4())

        with temporary_settings(
            updates={
                PREFECT_API_URL: f"https://api.prefect.cloud/api/accounts/{uuid4()}/workspaces/{uuid4()}",
                PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api/",
                PREFECT_EXPERIMENTAL_EVENTS: False,
            }
        ):
            assert get_client().server_type.supports_automations()

            with respx.mock(base_url=PREFECT_API_URL.value(), using="httpx") as router:
                router.post("/flows/").mock(
                    return_value=httpx.Response(201, json={"id": str(uuid4())})
                )
                router.post("/deployments/").mock(
                    return_value=httpx.Response(201, json={"id": created_deployment_id})
                )
                delete_route = router.delete(
                    f"/automations/owned-by/prefect.deployment.{created_deployment_id}"
                ).mock(return_value=httpx.Response(204))
                create_route = router.post("/automations/").mock(
                    return_value=httpx.Response(201, json={"id": str(uuid4())})
                )

                await deployment.apply()

                assert delete_route.called
                assert create_route.called
                assert json.loads(
                    create_route.calls[0].request.content
                ) == trigger.as_automation().dict(json_compatible=True)

    async def test_deployment_apply_syncs_triggers_to_prefect_api(
        self,
        patch_import,
        tmp_path,
    ):
        infrastructure = Process()
        await infrastructure._save(is_anonymous=True)

        trigger = pydantic.parse_obj_as(
            DeploymentTriggerTypes, {"job_variables": {"foo": 123}}
        )

        deployment = Deployment(
            name="TEST",
            flow_name="fn",
            triggers=[trigger],
            infrastructure=infrastructure,
        )

        created_deployment_id = str(uuid4())

        with temporary_settings(
            updates={
                PREFECT_API_URL: "http://localhost:4242/api",
                PREFECT_CLIENT_CSRF_SUPPORT_ENABLED: False,
                PREFECT_EXPERIMENTAL_EVENTS: True,
            }
        ):
            assert get_client().server_type.supports_automations()

            with respx.mock(base_url=PREFECT_API_URL.value(), using="httpx") as router:
                router.post("/flows/").mock(
                    return_value=httpx.Response(201, json={"id": str(uuid4())})
                )
                router.post("/deployments/").mock(
                    return_value=httpx.Response(201, json={"id": created_deployment_id})
                )
                delete_route = router.delete(
                    f"/automations/owned-by/prefect.deployment.{created_deployment_id}"
                ).mock(return_value=httpx.Response(204))
                create_route = router.post("/automations/").mock(
                    return_value=httpx.Response(201, json={"id": str(uuid4())})
                )

                await deployment.apply()

                assert delete_route.called
                assert create_route.called
                assert json.loads(
                    create_route.calls[0].request.content
                ) == trigger.as_automation().dict(json_compatible=True)

    async def test_deployment_apply_does_not_sync_triggers_to_prefect_api_when_off(
        self,
        events_disabled,
        patch_import,
        tmp_path,
    ):
        infrastructure = Process()
        await infrastructure._save(is_anonymous=True)

        trigger = pydantic.parse_obj_as(
            DeploymentTriggerTypes, {"job_variables": {"foo": 123}}
        )

        deployment = Deployment(
            name="TEST",
            flow_name="fn",
            triggers=[trigger],
            infrastructure=infrastructure,
        )

        created_deployment_id = str(uuid4())

        assert not get_client().server_type.supports_automations()

        with respx.mock(
            assert_all_mocked=False,
            assert_all_called=False,
        ) as router:
            router.post("/flows/").mock(
                return_value=httpx.Response(201, json={"id": str(uuid4())})
            )
            router.post("/deployments/").mock(
                return_value=httpx.Response(201, json={"id": created_deployment_id})
            )
            delete_route = router.delete(
                f"/automations/owned-by/prefect.deployment.{created_deployment_id}"
            ).mock(return_value=httpx.Response(204))
            create_route = router.post("/automations/").mock(
                return_value=httpx.Response(201, json={"id": str(uuid4())})
            )

            await deployment.apply()

            assert not delete_route.called
            assert not create_route.called

    async def test_trigger_job_vars(
        self,
        patch_import,
        tmp_path,
    ):
        infrastructure = Process()
        await infrastructure._save(is_anonymous=True)

        trigger = pydantic.parse_obj_as(
            DeploymentTriggerTypes, {"job_variables": {"foo": 123}}
        )
        assert isinstance(trigger, DeploymentEventTrigger)

        deployment = Deployment(
            name="TEST",
            flow_name="fn",
            triggers=[trigger],
            infrastructure=infrastructure,
        )

        created_deployment_id = str(uuid4())

        updates = {
            PREFECT_API_URL: f"https://api.prefect.cloud/api/accounts/{uuid4()}/workspaces/{uuid4()}",
            PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api/",
        }

        with temporary_settings(updates=updates):
            with respx.mock(base_url=PREFECT_API_URL.value(), using="httpx") as router:
                router.post("/flows/").mock(
                    return_value=httpx.Response(201, json={"id": str(uuid4())})
                )
                router.post("/deployments/").mock(
                    return_value=httpx.Response(201, json={"id": created_deployment_id})
                )
                delete_route = router.delete(
                    f"/automations/owned-by/prefect.deployment.{created_deployment_id}"
                ).mock(return_value=httpx.Response(204))
                create_route = router.post("/automations/").mock(
                    return_value=httpx.Response(201, json={"id": str(uuid4())})
                )

                await deployment.apply()

            assert delete_route.called
            assert create_route.called

            expected_job_vars = {"foo": 123}

            assert (
                json.loads(create_route.calls[0].request.content)["actions"][0][
                    "job_variables"
                ]
                == expected_job_vars
            )

    async def test_deployment_apply_with_dict_parameter(
        self, flow_function_dict_parameter, prefect_client
    ):
        d = await Deployment.build_from_flow(
            flow_function_dict_parameter,
            name="foo",
            parameters=dict(dict_param={1: "a", 2: "b"}),
        )

        assert d.flow_name == flow_function_dict_parameter.name
        assert d.name == "foo"

        dep_id = await d.apply()
        dep = await prefect_client.read_deployment(dep_id)

        assert dep is not None

    async def test_deployment_apply_with_enforce_parameter_schema(
        self, flow_function_dict_parameter, prefect_client
    ):
        d = await Deployment.build_from_flow(
            flow_function_dict_parameter,
            name="foo",
            enforce_parameter_schema=True,
            parameters=dict(dict_param={1: "a", 2: "b"}),
        )

        assert d.flow_name == flow_function_dict_parameter.name
        assert d.name == "foo"
        assert d.enforce_parameter_schema is True

        dep_id = await d.apply()
        dep = await prefect_client.read_deployment(dep_id)

        assert dep.enforce_parameter_schema is True


class TestRunDeployment:
    @pytest.mark.parametrize(
        "terminal_state", list(sorted(s.name for s in states.TERMINAL_STATES))
    )
    def test_running_a_deployment_blocks_until_termination(
        self,
        test_deployment,
        use_hosted_api_server,
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
            using="httpx",
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

            router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
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
        use_hosted_api_server,
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
            using="httpx",
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

            router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.get(re.compile("/flow_runs/.*")).mock(
                side_effect=poll_responses
            )

            assert (
                (
                    await run_deployment(
                        f"{d.flow_name}/{d.name}",
                        timeout=2,
                        poll_interval=0,
                    )
                ).state.type
                == terminal_state
            ), "run_deployment does not exit on {terminal_state}"
            assert len(flow_polls.calls) == 3

    async def test_run_deployment_with_ephemeral_api(
        self,
        test_deployment,
        prefect_client,
    ):
        d, deployment_id = test_deployment

        flow_run = await run_deployment(
            f"{d.flow_name}/{d.name}",
            timeout=0,
            poll_interval=0,
            client=prefect_client,
        )
        assert flow_run.deployment_id == deployment_id
        assert flow_run.state

    async def test_run_deployment_with_deployment_id_str(
        self,
        test_deployment,
        prefect_client,
    ):
        _, deployment_id = test_deployment

        flow_run = await run_deployment(
            f"{deployment_id}",
            timeout=0,
            poll_interval=0,
            client=prefect_client,
        )
        assert flow_run.deployment_id == deployment_id
        assert flow_run.state

    async def test_run_deployment_with_deployment_id_uuid(
        self,
        test_deployment,
        prefect_client,
    ):
        _, deployment_id = test_deployment

        flow_run = await run_deployment(
            deployment_id,
            timeout=0,
            poll_interval=0,
            client=prefect_client,
        )
        assert flow_run.deployment_id == deployment_id
        assert flow_run.state

    async def test_run_deployment_with_job_vars_creates_run_with_job_vars(
        self,
        test_deployment,
        prefect_client,
    ):
        # This can be removed once the flow run infra overrides is no longer an experiment
        _, deployment_id = test_deployment

        job_vars = {"foo": "bar"}
        flow_run = await run_deployment(
            deployment_id,
            timeout=0,
            job_variables=job_vars,
            client=prefect_client,
        )
        assert flow_run.job_variables == job_vars
        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.job_variables == job_vars

    def test_returns_flow_run_on_timeout(
        self,
        test_deployment,
        use_hosted_api_server,
    ):
        d, deployment_id = test_deployment

        mock_flowrun_response = {
            "id": str(uuid4()),
            "flow_id": str(uuid4()),
        }

        with respx.mock(
            base_url=PREFECT_API_URL.value(), assert_all_mocked=True, using="httpx"
        ) as router:
            router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
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
        use_hosted_api_server,
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
            using="httpx",
        ) as router:
            router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
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
        use_hosted_api_server,
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
            using="httpx",
        ) as router:
            router.get("/csrf-token", params={"client": mock.ANY}).pass_through()
            router.get(f"/deployments/name/{d.flow_name}/{d.name}").pass_through()
            router.post(f"/deployments/{deployment_id}/create_flow_run").pass_through()
            flow_polls = router.request(
                "GET", re.compile(PREFECT_API_URL.value() + "/flow_runs/.*")
            ).mock(side_effect=side_effects)

            run_deployment(f"{d.flow_name}/{d.name}", timeout=None, poll_interval=0)
            assert len(flow_polls.calls) == 100

    def test_schedules_immediately_by_default(
        self, test_deployment, use_hosted_api_server
    ):
        d, deployment_id = test_deployment

        scheduled_time = pendulum.now("UTC")
        flow_run = run_deployment(
            f"{d.flow_name}/{d.name}",
            timeout=0,
            poll_interval=0,
        )

        assert (flow_run.expected_start_time - scheduled_time).total_seconds() < 1

    def test_accepts_custom_scheduled_time(
        self, test_deployment, use_hosted_api_server
    ):
        d, deployment_id = test_deployment

        scheduled_time = pendulum.now("UTC") + pendulum.Duration(minutes=5)
        flow_run = run_deployment(
            f"{d.flow_name}/{d.name}",
            scheduled_time=scheduled_time,
            timeout=0,
            poll_interval=0,
        )

        assert (flow_run.expected_start_time - scheduled_time).total_seconds() < 1

    def test_custom_flow_run_names(self, test_deployment, use_hosted_api_server):
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

    async def test_links_to_parent_flow_run_when_used_in_flow_by_default(
        self, test_deployment, use_hosted_api_server, prefect_client: PrefectClient
    ):
        d, deployment_id = test_deployment

        @flow
        async def foo():
            return await run_deployment(
                f"{d.flow_name}/{d.name}",
                timeout=0,
                poll_interval=0,
            )

        parent_state = await foo(return_state=True)
        child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is not None
        task_run = await prefect_client.read_task_run(child_flow_run.parent_task_run_id)
        assert task_run.flow_run_id == parent_state.state_details.flow_run_id
        assert slugify(f"{d.flow_name}/{d.name}") in task_run.task_key

    async def test_optionally_does_not_link_to_parent_flow_run_when_used_in_flow(
        self, test_deployment, use_hosted_api_server, prefect_client: PrefectClient
    ):
        d, deployment_id = test_deployment

        @flow
        async def foo():
            return await run_deployment(
                f"{d.flow_name}/{d.name}",
                timeout=0,
                poll_interval=0,
                as_subflow=False,
            )

        parent_state = await foo(return_state=True)
        child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is None

    @pytest.mark.usefixtures("use_hosted_api_server")
    async def test_links_to_parent_flow_run_when_used_in_task_without_flow_context(
        self, test_deployment, prefect_client
    ):
        """
        Regression test for deployments in a task on Dask and Ray task runners
        which do not have access to the flow run context - https://github.com/PrefectHQ/prefect/issues/9135
        """
        d, deployment_id = test_deployment

        @task
        async def yeet_deployment():
            with mock.patch.object(FlowRunContext, "get", return_value=None):
                assert FlowRunContext.get() is None
                result = await run_deployment(
                    f"{d.flow_name}/{d.name}",
                    timeout=0,
                    poll_interval=0,
                )
                return result

        @flow
        async def foo():
            return await yeet_deployment()

        parent_state = await foo(return_state=True)
        child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is not None
        task_run = await prefect_client.read_task_run(child_flow_run.parent_task_run_id)
        assert task_run.flow_run_id == parent_state.state_details.flow_run_id
        assert slugify(f"{d.flow_name}/{d.name}") in task_run.task_key

    async def test_tracks_dependencies_when_used_in_flow(
        self, test_deployment, use_hosted_api_server, prefect_client
    ):
        d, deployment_id = test_deployment

        @task
        def bar():
            return "hello-world!!"

        @flow
        async def foo():
            upstream_task_state = bar(return_state=True)
            upstream_result = await upstream_task_state.result()
            child_flow_run = await run_deployment(
                f"{d.flow_name}/{d.name}",
                timeout=0,
                poll_interval=0,
                parameters={"x": upstream_result},
            )
            return upstream_task_state, child_flow_run

        parent_state = await foo(return_state=True)
        upstream_task_state, child_flow_run = await parent_state.result()
        assert child_flow_run.parent_task_run_id is not None
        task_run = await prefect_client.read_task_run(child_flow_run.parent_task_run_id)
        assert task_run.task_inputs == {
            "x": [
                TaskRunResult(
                    input_type="task_run",
                    id=upstream_task_state.state_details.task_run_id,
                )
            ]
        }


class TestLoadFlowFromFlowRun:
    async def test_load_flow_from_module_entrypoint(
        self, prefect_client: PrefectClient, monkeypatch
    ):
        @flow
        def pretend_flow():
            pass

        load_flow_from_entrypoint = mock.MagicMock(return_value=pretend_flow)
        monkeypatch.setattr(
            "prefect.deployments.deployments.load_flow_from_entrypoint",
            load_flow_from_entrypoint,
        )

        flow_id = await prefect_client.create_flow_from_name(pretend_flow.__name__)

        deployment_id = await prefect_client.create_deployment(
            name="My Module Deployment",
            entrypoint="my.module.pretend_flow",
            flow_id=flow_id,
        )

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        result = await load_flow_from_flow_run(flow_run, client=prefect_client)

        assert result == pretend_flow
        load_flow_from_entrypoint.assert_called_once_with(
            "my.module.pretend_flow", True
        )

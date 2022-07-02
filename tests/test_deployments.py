import os
import sys
import textwrap
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from prefect.blocks.core import Block
from prefect.blocks.storage import FileStorageBlock, LocalStorageBlock
from prefect.deployments import (
    DeploymentSpec,
    deployment_specs_from_script,
    deployment_specs_from_yaml,
    load_flow_from_deployment,
    load_flow_from_script,
)
from prefect.exceptions import (
    DeploymentValidationError,
    MissingFlowError,
    ScriptError,
    UnspecifiedFlowError,
)
from prefect.flow_runners import (
    DockerFlowRunner,
    FlowRunner,
    FlowRunnerSettings,
    KubernetesFlowRunner,
    SubprocessFlowRunner,
    UniversalFlowRunner,
)
from prefect.flows import Flow, flow
from prefect.orion.schemas.core import Deployment
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.schedules import IntervalSchedule

from .deployment_test_files.single_flow import hello_world as hello_world_flow

TEST_FILES_DIR = Path(__file__).parent / "deployment_test_files"


@pytest.fixture
async def tmp_remote_storage_block_id(tmp_path, orion_client):

    block = FileStorageBlock(base_path=str(tmp_path))

    block_schema = await orion_client.read_block_schema_by_checksum(
        block._calculate_schema_checksum()
    )

    block_document = await orion_client.create_block_document(
        block._to_block_document(
            name="test",
            block_schema_id=block_schema.id,
            block_type_id=block_schema.block_type_id,
        )
    )
    return block_document.id


@pytest.fixture
async def tmp_local_storage_block(tmp_path, orion_client):

    block = LocalStorageBlock(storage_path=str(tmp_path))
    block_schema = await orion_client.read_block_schema_by_checksum(
        block._calculate_schema_checksum()
    )
    block_document = await orion_client.create_block_document(
        block._to_block_document(
            name="test",
            block_schema_id=block_schema.id,
            block_type_id=block_schema.block_type_id,
        )
    )
    return block_document.id


@pytest.fixture
async def remote_default_storage(orion_client, tmp_remote_storage_block_id):
    # A "remote" default storage is required for the default flow runner type
    await orion_client.set_default_storage_block_document(tmp_remote_storage_block_id)


class TestDeploymentSpec:
    async def test_infers_flow_location_from_flow(self, remote_default_storage):
        spec = DeploymentSpec(flow=hello_world_flow)
        await spec.validate()
        assert spec.flow_location == str(TEST_FILES_DIR / "single_flow.py")

    async def test_flow_location_is_coerced_to_string(self, remote_default_storage):
        spec = DeploymentSpec(flow_location=TEST_FILES_DIR / "single_flow.py")
        await spec.validate()
        assert type(spec.flow_location) is str
        assert spec.flow_location == str(TEST_FILES_DIR / "single_flow.py")

    def test_flow_location_is_absolute(self, remote_default_storage):
        spec = DeploymentSpec(
            flow_location=(TEST_FILES_DIR / "single_flow.py").relative_to(os.getcwd()),
        )
        assert spec.flow_location == str((TEST_FILES_DIR / "single_flow.py").absolute())

    async def test_infers_flow_name_from_flow(self, remote_default_storage):
        spec = DeploymentSpec(flow=hello_world_flow)
        await spec.validate()
        assert spec.flow_name == "hello-world"

    async def test_checks_for_flow_name_consistency(self, remote_default_storage):
        spec = DeploymentSpec(flow=hello_world_flow, flow_name="other-name")
        with pytest.raises(
            DeploymentValidationError, match="`flow.name` and `flow_name` must match"
        ):
            await spec.validate()

    async def test_loads_flow_and_name_from_location(self, remote_default_storage):
        spec = DeploymentSpec(
            name="test", flow_location=TEST_FILES_DIR / "single_flow.py"
        )
        assert spec.flow is None
        assert spec.flow_name is None
        await spec.validate()
        assert isinstance(spec.flow, Flow)
        assert spec.flow.name == "hello-world"
        assert spec.flow_name == "hello-world"

    async def test_loads_flow_from_location_by_name(self, remote_default_storage):
        spec = DeploymentSpec(
            name="test",
            flow_location=TEST_FILES_DIR / "multiple_flows.py",
            flow_name="hello-sun",
        )
        assert spec.flow is None
        assert spec.flow_name == "hello-sun"
        await spec.validate()
        assert isinstance(spec.flow, Flow)
        assert spec.flow.name == "hello-sun"
        assert spec.flow_name == "hello-sun"

    async def test_raises_validation_error_on_missing_flow_name(
        self, remote_default_storage
    ):
        spec = DeploymentSpec(
            name="test",
            flow_location=TEST_FILES_DIR / "multiple_flows.py",
            flow_name="shall-not-be-found",
        )
        assert spec.flow is None
        assert spec.flow_name == "shall-not-be-found"
        with pytest.raises(
            DeploymentValidationError, match="'shall-not-be-found' not found"
        ):
            await spec.validate()

    @pytest.mark.parametrize(
        "name",
        [
            "my/deployment",
            r"my%deployment",
            "my>deployment",
            "my<deployment",
            "my&deployment",
        ],
    )
    def test_invalid_name(self, name):
        with pytest.raises(ValidationError, match="contains an invalid character"):
            DeploymentSpec(name=name)

    async def test_defaults_name_to_match_flow_name(self, remote_default_storage):
        @flow
        def foo():
            pass

        spec = DeploymentSpec(flow=foo)
        await spec.validate()
        assert spec.name == "foo" == spec.flow.name

    async def test_converts_flow_runner_settings_to_flow_runner(
        self, remote_default_storage
    ):
        @flow
        def foo():
            pass

        spec = DeploymentSpec(
            flow=foo,
            flow_runner=FlowRunnerSettings(
                type="subprocess", config={"env": {"test": "test"}}
            ),
        )
        await spec.validate()
        assert isinstance(spec.flow_runner, SubprocessFlowRunner)
        assert spec.flow_runner.typename == "subprocess"
        assert spec.flow_runner.env == {"test": "test"}

    async def test_does_not_allow_base_flow_runner_type(self, remote_default_storage):
        @flow
        def foo():
            pass

        spec = DeploymentSpec(
            flow=foo,
            flow_runner=FlowRunner(typename="test"),
        )
        with pytest.raises(
            DeploymentValidationError, match="The base.*type cannot be used"
        ):
            await spec.validate()

    async def test_does_not_allow_default_flow_runner_without_storage(
        self, orion_client
    ):
        await orion_client.clear_default_storage_block_document()

        @flow
        def foo():
            pass

        spec = DeploymentSpec(flow=foo)
        with pytest.raises(
            DeploymentValidationError, match="have not configured default storage"
        ):
            await spec.validate()

    @pytest.mark.parametrize(
        "flow_runner",
        [UniversalFlowRunner(), DockerFlowRunner(), KubernetesFlowRunner()],
    )
    async def test_does_not_allow_remote_flow_runner_without_storage(
        self, orion_client, flow_runner
    ):
        await orion_client.clear_default_storage_block_document()

        @flow
        def foo():
            pass

        spec = DeploymentSpec(flow=foo, flow_runner=flow_runner)
        with pytest.raises(
            DeploymentValidationError, match="have not configured default storage"
        ):
            await spec.validate()

    @pytest.mark.parametrize(
        "flow_runner",
        [
            UniversalFlowRunner(),
            SubprocessFlowRunner(),
            DockerFlowRunner(),
            KubernetesFlowRunner(),
        ],
    )
    async def test_allows_any_flow_runner_with_remote_default_storage(
        self,
        orion_client,
        flow_runner,
        remote_default_storage,
    ):
        @flow
        def foo():
            pass

        spec = DeploymentSpec(flow=foo, flow_runner=flow_runner)
        await spec.validate()
        assert spec._packager.storage == Block._from_block_document(
            await orion_client.get_default_storage_block_document()
        )

    @pytest.mark.parametrize(
        "flow_runner",
        [
            UniversalFlowRunner(),
            DockerFlowRunner(),
            KubernetesFlowRunner(),
        ],
    )
    async def test_does_not_allow_remote_flow_runner_with_local_default_storage(
        self,
        orion_client,
        flow_runner,
        tmp_local_storage_block,
    ):
        await orion_client.set_default_storage_block_document(tmp_local_storage_block)

        @flow
        def foo():
            pass

        spec = DeploymentSpec(flow=foo, flow_runner=flow_runner)

        with pytest.raises(
            DeploymentValidationError,
            match="have configured local storage but.*requires remote storage",
        ):
            await spec.validate()

    @pytest.mark.parametrize("flow_runner", [SubprocessFlowRunner()])
    async def test_allows_local_flow_runner_with_local_storage(
        self,
        orion_client,
        flow_runner,
        tmp_local_storage_block,
    ):
        await orion_client.set_default_storage_block_document(tmp_local_storage_block)

        @flow
        def foo():
            pass

        spec = DeploymentSpec(flow=foo, flow_runner=flow_runner)
        with pytest.warns(match="only be usable from the current machine"):
            await spec.validate()

    @pytest.mark.parametrize("flow_runner", [SubprocessFlowRunner()])
    async def test_allows_local_flow_runner_with_no_storage(
        self,
        orion_client,
        flow_runner,
        tmp_local_storage_block,
    ):
        await orion_client.set_default_storage_block_document(tmp_local_storage_block)

        @flow
        def foo():
            pass

        spec = DeploymentSpec(flow=foo, flow_runner=flow_runner)
        with pytest.warns(match="only be usable from the current machine"):
            await spec.validate()
        assert isinstance(spec._packager.storage, LocalStorageBlock)

    @pytest.mark.parametrize(
        "flow_runner",
        [
            UniversalFlowRunner(),
            SubprocessFlowRunner(),
            DockerFlowRunner(),
            KubernetesFlowRunner(),
        ],
    )
    async def test_allows_any_flow_runner_with_explicit_remote_storage(
        self, orion_client, flow_runner, tmp_remote_storage_block_id
    ):
        await orion_client.clear_default_storage_block_document()
        block = Block._from_block_document(
            await orion_client.read_block_document(tmp_remote_storage_block_id)
        )

        @flow
        def foo():
            pass

        spec = DeploymentSpec(flow=foo, flow_runner=flow_runner, flow_storage=block)
        await spec.validate()
        assert spec._packager.storage == block


class TestCreateDeploymentFromSpec:
    async def test_create_deployment_with_unregistered_storage(
        self, orion_client, tmp_path
    ):

        block = FileStorageBlock(base_path=str(tmp_path))

        spec = DeploymentSpec(
            flow_location=TEST_FILES_DIR / "single_flow.py", flow_storage=block
        )
        deployment_id = await spec.create(client=orion_client)

        # Check that the flow is retrievable

        deployment = await orion_client.read_deployment(deployment_id)
        flow = await load_flow_from_deployment(deployment, client=orion_client)
        expected_flow = load_flow_from_script(TEST_FILES_DIR / "single_flow.py")
        assert flow.name == expected_flow.name
        assert flow.version == expected_flow.version

    async def test_create_deployment_with_unregistered_storage_collision(
        self, orion_client, tmp_path
    ):
        """
        Regression test for bug where dynamically generated block names would collide
        resulting in an `ObjectAlreadyExists` error
        """

        def make_spec():
            # A unique instance is required for each test or the id will be
            # cached on the object
            block = FileStorageBlock(base_path=str(tmp_path))

            return DeploymentSpec(
                flow_location=TEST_FILES_DIR / "single_flow.py", flow_storage=block
            )

        deployment_id_1 = await make_spec().create(client=orion_client)
        deployment_id_2 = await make_spec().create(client=orion_client)
        deployment_id_3 = await make_spec().create(client=orion_client)

        # Check that the flow is retrievable
        async def check_retrievable(deployment_id):
            deployment = await orion_client.read_deployment(deployment_id)
            flow = await load_flow_from_deployment(deployment, client=orion_client)
            expected_flow = load_flow_from_script(TEST_FILES_DIR / "single_flow.py")
            assert flow.name == expected_flow.name
            assert flow.version == expected_flow.version

        await check_retrievable(deployment_id_1)
        await check_retrievable(deployment_id_2)
        await check_retrievable(deployment_id_3)

    async def test_create_deployment_with_registered_storage(
        self, orion_client, tmp_remote_storage_block_id
    ):
        block = Block._from_block_document(
            await orion_client.read_block_document(tmp_remote_storage_block_id)
        )

        spec = DeploymentSpec(
            flow_location=TEST_FILES_DIR / "single_flow.py", flow_storage=block
        )
        deployment_id = await spec.create(client=orion_client)

        # Check that the flow is retrievable
        deployment = await orion_client.read_deployment(deployment_id)
        flow = await load_flow_from_deployment(deployment, client=orion_client)
        expected_flow = load_flow_from_script(TEST_FILES_DIR / "single_flow.py")
        assert flow.name == expected_flow.name
        assert flow.version == expected_flow.version

    async def test_create_deployment_with_registered_storage_by_id(
        self, orion_client, tmp_remote_storage_block_id
    ):
        spec = DeploymentSpec(
            flow_location=TEST_FILES_DIR / "single_flow.py",
            flow_storage=tmp_remote_storage_block_id,
        )
        deployment_id = await spec.create(client=orion_client)

        # Check that the flow is retrievable
        deployment = await orion_client.read_deployment(deployment_id)
        flow = await load_flow_from_deployment(deployment, client=orion_client)
        expected_flow = load_flow_from_script(TEST_FILES_DIR / "single_flow.py")
        assert flow.name == expected_flow.name
        assert flow.version == expected_flow.version

    async def test_create_deployment_with_default_storage(
        self, orion_client, remote_default_storage
    ):
        spec = DeploymentSpec(flow_location=TEST_FILES_DIR / "single_flow.py")
        deployment_id = await spec.create(client=orion_client)

        # Check that the flow is retrievable

        deployment = await orion_client.read_deployment(deployment_id)
        flow = await load_flow_from_deployment(deployment, client=orion_client)
        expected_flow = load_flow_from_script(TEST_FILES_DIR / "single_flow.py")
        assert flow.name == expected_flow.name
        assert flow.version == expected_flow.version

    async def test_create_deployment_respects_name(
        self, orion_client, remote_default_storage
    ):
        spec = DeploymentSpec(
            flow_location=TEST_FILES_DIR / "single_flow.py", name="test"
        )
        deployment_id = await spec.create(client=orion_client)

        deployment = await orion_client.read_deployment(deployment_id)
        assert deployment.name == "test"

    async def test_create_deployment_respects_flow_runner(
        self, orion_client, remote_default_storage
    ):
        spec = DeploymentSpec(
            flow_location=TEST_FILES_DIR / "single_flow.py",
            flow_runner=SubprocessFlowRunner(env={"test": "test"}),
        )
        deployment_id = await spec.create(client=orion_client)

        deployment = await orion_client.read_deployment(deployment_id)
        assert deployment.flow_runner == spec.flow_runner.to_settings()


class TestLoadFlowFromScript:
    def test_loads_from_file_with_one_flow(self):
        loaded_flow = load_flow_from_script(TEST_FILES_DIR / "single_flow.py")
        assert isinstance(loaded_flow, Flow)
        assert loaded_flow.name == "hello-world"

    def test_loads_from_file_with_multiple_flows_by_name(self):
        loaded_flow = load_flow_from_script(
            TEST_FILES_DIR / "multiple_flows.py", flow_name="hello-moon"
        )
        assert isinstance(loaded_flow, Flow)
        assert loaded_flow.name == "hello-moon"
        loaded_flow = load_flow_from_script(
            TEST_FILES_DIR / "multiple_flows.py", flow_name="hello-sun"
        )
        assert isinstance(loaded_flow, Flow)
        assert loaded_flow.name == "hello-sun"

    def test_requires_name_for_file_with_multiple_flows(self):
        with pytest.raises(
            UnspecifiedFlowError, match="Found 2 flows.*'hello-moon' 'hello-sun'"
        ):
            load_flow_from_script(TEST_FILES_DIR / "multiple_flows.py")

    def test_throws_error_when_name_not_found(self):
        with pytest.raises(
            MissingFlowError, match="Flow 'foo' not found.*Found.*'hello-world'"
        ):
            load_flow_from_script(TEST_FILES_DIR / "single_flow.py", flow_name="foo")

    def test_errors_in_flow_script_are_reraised(self):
        with pytest.raises(ScriptError) as exc:
            load_flow_from_script(TEST_FILES_DIR / "flow_with_load_error.py")
        script_err = exc.value.__cause__
        assert script_err is not None
        with pytest.raises(RuntimeError, match="This flow shall not load"):
            raise script_err

    def test_execution_blocked_during_load(self):
        loaded_flow = load_flow_from_script(
            TEST_FILES_DIR / "flow_with_execution_blocked_assert.py"
        )
        assert isinstance(loaded_flow, Flow)
        assert loaded_flow.name == "hello-world"


class TestDeploymentSpecFromFile:
    @pytest.fixture(autouse=True)
    async def autouse_storage(self, remote_default_storage):
        pass

    async def test_spec_inline_with_flow(self):
        specs = deployment_specs_from_script(TEST_FILES_DIR / "inline_deployment.py")
        assert len(specs) == 1
        spec = list(specs)[0]
        await spec.validate()
        assert spec.name == "inline-deployment"
        assert spec.flow.name == "hello-world"
        assert spec.flow_name == "hello-world"
        assert spec.flow_location == str(TEST_FILES_DIR / "inline_deployment.py")
        assert spec.parameters == {"name": "Marvin"}
        assert spec.tags == ["foo", "bar"]
        assert spec._source["file"] == str(TEST_FILES_DIR / "inline_deployment.py")
        if sys.version_info < (3, 8):
            #  Python 3.7 reports the line number for the last arg instead
            assert spec._source["line"] == 14
        else:
            assert spec._source["line"] == 10

    async def test_spec_separate_from_flow(self):
        specs = deployment_specs_from_script(TEST_FILES_DIR / "single_deployment.py")
        assert len(specs) == 1
        spec = list(specs)[0]
        await spec.validate()
        assert spec.name == "hello-world-daily"
        assert spec.flow_location == str(TEST_FILES_DIR / "single_flow.py")
        assert isinstance(spec.schedule, IntervalSchedule)
        assert spec.parameters == {"foo": "bar"}
        assert spec.tags == ["foo", "bar"]
        assert spec._source["file"] == str(TEST_FILES_DIR / "single_deployment.py")
        if sys.version_info < (3, 8):
            # Python 3.7 reports the line number for the last arg instead
            assert spec._source["line"] == 14
        else:
            assert spec._source["line"] == 8

    async def test_multiple_specs_separate_from_flow(self):
        specs = deployment_specs_from_script(TEST_FILES_DIR / "multiple_deployments.py")
        assert len(specs) == 2
        for spec in specs:
            await spec.validate()
        specs_by_name = {spec.name: spec for spec in specs}
        assert set(specs_by_name.keys()) == {
            "hello-sun-deployment",
            "hello-moon-deployment",
        }
        sun_deploy = specs_by_name["hello-sun-deployment"]
        moon_deploy = specs_by_name["hello-moon-deployment"]
        assert sun_deploy.flow_location == str(TEST_FILES_DIR / "multiple_flows.py")
        assert sun_deploy.flow_name == "hello-sun"
        assert moon_deploy.flow_location == str(TEST_FILES_DIR / "multiple_flows.py")
        assert moon_deploy.flow_name == "hello-moon"

    async def test_spec_from_yaml(self):
        specs = deployment_specs_from_yaml(TEST_FILES_DIR / "single-deployment.yaml")
        assert len(specs) == 1
        spec = specs[0]

        assert spec._source["file"] == str(TEST_FILES_DIR / "single-deployment.yaml")
        assert spec._source["line"] == 1

        await spec.validate()

        assert spec.name == "hello-world-deployment"
        assert spec.flow_location == str(TEST_FILES_DIR / "single_flow.py")
        assert isinstance(spec.schedule, IntervalSchedule)
        assert spec.parameters == {"foo": "bar"}
        assert spec.tags == ["foo", "bar"]

    async def test_multiple_specs_from_yaml(self):
        specs = deployment_specs_from_yaml(TEST_FILES_DIR / "multiple-deployments.yaml")
        assert len(specs) == 2
        specs_by_name = {spec.name: spec for spec in specs}
        assert set(specs_by_name.keys()) == {
            "hello-sun-deployment",
            "hello-moon-deployment",
        }

        sun_deploy = specs_by_name["hello-sun-deployment"]
        moon_deploy = specs_by_name["hello-moon-deployment"]
        assert sun_deploy.flow_location == str(TEST_FILES_DIR / "multiple_flows.py")
        assert sun_deploy.flow_name == "hello-sun"
        assert moon_deploy.flow_location == str(TEST_FILES_DIR / "multiple_flows.py")
        assert moon_deploy.flow_name == "hello-moon"

        assert sun_deploy._source["file"] == str(
            TEST_FILES_DIR / "multiple-deployments.yaml"
        )
        assert moon_deploy._source["file"] == str(
            TEST_FILES_DIR / "multiple-deployments.yaml"
        )
        assert sun_deploy._source["line"] == 1
        assert moon_deploy._source["line"] == 5

        for spec in specs:
            await spec.validate()

    async def test_loading_spec_does_not_raise_until_flow_is_loaded(self):
        specs = deployment_specs_from_yaml(
            TEST_FILES_DIR / "deployment-with-flow-load-error.yaml"
        )
        assert len(specs) == 1
        spec = specs[0]
        with pytest.raises(ScriptError):
            await spec.validate()

    async def test_loading_spec_blocks_code_execution(self):
        specs = deployment_specs_from_yaml(
            TEST_FILES_DIR / "deployment-with-execution-blocked-assert.yaml"
        )
        assert len(specs) == 1

    async def test_create_deployment(self, orion_client):
        schedule = IntervalSchedule(interval=timedelta(days=1))

        spec = DeploymentSpec(
            name="test",
            flow_location=TEST_FILES_DIR / "single_flow.py",
            schedule=schedule,
            parameters={"foo": "bar"},
            tags=["foo", "bar"],
            flow_runner=SubprocessFlowRunner(env={"FOO": "BAR"}),
        )
        deployment_id = await spec.create(client=orion_client)

        # Deployment was created in backend
        lookup = await orion_client.read_deployment(deployment_id)
        assert lookup.name == "test"
        assert lookup.schedule == schedule
        assert lookup.parameters == {"foo": "bar"}
        assert lookup.tags == ["foo", "bar"]
        assert lookup.flow_runner == spec.flow_runner.to_settings()

        # Flow was loaded
        assert spec.flow is not None


class TestLoadFlowFromDeployment:
    @pytest.fixture
    def flow_object(self):
        @flow
        def foo():
            pass

        return foo

    @pytest.fixture
    async def flow_id(self, flow_object, orion_client):
        return await orion_client.create_flow(flow_object)

    async def test_load_pickled_flow_from_deployment(
        self, flow_object, flow_id, orion_client
    ):
        deployment = Deployment(
            name="test",
            flow_id=flow_id,
            flow_data=DataDocument.encode("cloudpickle", flow_object),
        )
        loaded_flow_object = await load_flow_from_deployment(
            deployment, client=orion_client
        )
        assert flow_object == loaded_flow_object

    async def test_load_persisted_flow_pickle_from_deployment(
        self, flow_object, flow_id, orion_client, local_storage_block
    ):
        deployment = Deployment(
            name="test",
            flow_id=flow_id,
            flow_data=await orion_client.persist_object(
                flow_object, storage_block=local_storage_block
            ),
        )
        loaded_flow_object = await load_flow_from_deployment(
            deployment, client=orion_client
        )
        assert isinstance(loaded_flow_object, Flow)
        assert flow_object.name == loaded_flow_object.name

    async def test_load_flow_for_legacy_deployment(
        self, flow_id, flow_object, local_storage_block, orion_client
    ):
        """
        Test to verify that deployments created pre-2.0b6 still work. The datadoc for
        pre-2.0b6 deployments used block_id which was then switched to
        block_document_id due to a suite of renames in the blocks feature.
        """
        flow_datadoc = DataDocument.encode(encoding="cloudpickle", data=flow_object)
        storage_key = await local_storage_block.write(flow_datadoc.json().encode())
        legacy_flow_data = DataDocument.encode(
            encoding="blockstorage",
            data={
                "block_id": local_storage_block._block_document_id,
                "data": storage_key,
            },
        )

        deployment = Deployment(
            name="test",
            flow_id=flow_id,
            flow_data=legacy_flow_data,
        )

        loaded_flow_object = await load_flow_from_deployment(
            deployment, client=orion_client
        )
        assert isinstance(loaded_flow_object, Flow)
        assert flow_object.name == loaded_flow_object.name

    async def test_load_persisted_flow_script_from_deployment(
        self, flow_object, flow_id, orion_client, local_storage_block
    ):
        deployment = Deployment(
            name="test",
            flow_id=flow_id,
            flow_data=await orion_client.persist_object(
                textwrap.dedent(
                    """
                    from prefect import flow

                    @flow
                    def foo():
                        pass
                    """
                ),
                encoder="text",
                storage_block=local_storage_block,
            ),
        )
        loaded_flow_object = await load_flow_from_deployment(
            deployment, client=orion_client
        )
        assert isinstance(loaded_flow_object, Flow)
        assert flow_object.name == loaded_flow_object.name

    async def test_load_bad_flow_script_from_deployment(
        self, flow_id, orion_client, local_storage_block
    ):
        deployment = Deployment(
            name="test",
            flow_id=flow_id,
            flow_data=await orion_client.persist_object(
                "test",
                encoder="text",
                storage_block=local_storage_block,
            ),
        )
        with pytest.raises(ScriptError):
            await load_flow_from_deployment(deployment, client=orion_client)

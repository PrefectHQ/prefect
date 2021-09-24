import os
import textwrap
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from prefect.deployments import (
    DeploymentSpec,
    create_deployment_from_spec,
    deployment_specs_from_script,
    deployment_specs_from_yaml,
    load_flow_from_deployment,
    load_flow_from_script,
)
from prefect.exceptions import FlowScriptError, MissingFlowError, UnspecifiedFlowError
from prefect.flows import Flow, flow
from prefect.orion.schemas.core import Deployment
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.schedules import IntervalSchedule
from prefect.orion.serializers import D

from .deployment_test_files.single_flow import hello_world as hello_world_flow


TEST_FILES_DIR = Path(__file__).parent / "deployment_test_files"


class TestDeploymentSpec:
    def test_infers_flow_location_from_flow(self):
        spec = DeploymentSpec(name="test", flow=hello_world_flow)
        assert spec.flow_location == str(TEST_FILES_DIR / "single_flow.py")

    def test_flow_location_is_coerced_to_string(self):
        spec = DeploymentSpec(
            name="test", flow_location=TEST_FILES_DIR / "single_flow.py"
        )
        assert type(spec.flow_location) is str
        assert spec.flow_location == str(TEST_FILES_DIR / "single_flow.py")

    def test_flow_location_is_absolute(self):
        spec = DeploymentSpec(
            name="test",
            flow_location=(TEST_FILES_DIR / "single_flow.py").relative_to(os.getcwd()),
        )
        assert spec.flow_location == str((TEST_FILES_DIR / "single_flow.py").absolute())

    def test_infers_flow_name_from_flow(self):
        spec = DeploymentSpec(name="test", flow=hello_world_flow)
        assert spec.flow_name == "hello-world"

    def test_checks_for_flow_name_consistency(self):
        with pytest.raises(
            ValidationError, match="`flow.name` and `flow_name` must match"
        ):
            DeploymentSpec(name="test", flow=hello_world_flow, flow_name="other-name")

    def test_loads_flow_and_name_from_location(self):
        spec = DeploymentSpec(
            name="test", flow_location=TEST_FILES_DIR / "single_flow.py"
        )
        assert spec.flow is None
        assert spec.flow_name is None
        spec.load_flow()
        assert isinstance(spec.flow, Flow)
        assert spec.flow.name == "hello-world"
        assert spec.flow_name == "hello-world"

    def test_loads_flow_from_location_by_name(self):
        spec = DeploymentSpec(
            name="test",
            flow_location=TEST_FILES_DIR / "multiple_flows.py",
            flow_name="hello-sun",
        )
        assert spec.flow is None
        assert spec.flow_name == "hello-sun"
        spec.load_flow()
        assert isinstance(spec.flow, Flow)
        assert spec.flow.name == "hello-sun"
        assert spec.flow_name == "hello-sun"


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
            UnspecifiedFlowError, match="Found 2 flows.*'hello-sun' 'hello-moon'"
        ):
            load_flow_from_script(TEST_FILES_DIR / "multiple_flows.py")

    def test_throws_error_when_name_not_found(self):
        with pytest.raises(
            MissingFlowError, match="Flow 'foo' not found.*Found.*'hello-world'"
        ):
            load_flow_from_script(TEST_FILES_DIR / "single_flow.py", flow_name="foo")

    def test_errors_in_flow_script_are_reraised(self):
        with pytest.raises(FlowScriptError) as exc:
            load_flow_from_script(TEST_FILES_DIR / "flow_with_load_error.py")
        script_err = exc.value.__cause__
        assert script_err is not None
        with pytest.raises(RuntimeError, match="This flow shall not load"):
            raise script_err


class TestDeploymentSpecFromFile:
    def test_spec_inline_with_flow(self):
        specs = deployment_specs_from_script(TEST_FILES_DIR / "inline_deployment.py")
        assert len(specs) == 1
        spec = list(specs)[0]
        assert spec.name == "inline-deployment"
        assert spec.flow.name == "hello-world"
        assert spec.flow_name == "hello-world"
        assert spec.flow_location == str(TEST_FILES_DIR / "inline_deployment.py")
        assert spec.parameters == {"foo": "bar"}
        assert spec.tags == ["foo", "bar"]

    def test_spec_separate_from_flow(self):
        specs = deployment_specs_from_script(TEST_FILES_DIR / "single_deployment.py")
        assert len(specs) == 1
        spec = list(specs)[0]
        assert spec.name == "hello-world-daily"
        assert spec.flow_location == str(TEST_FILES_DIR / "single_flow.py")
        assert isinstance(spec.schedule, IntervalSchedule)
        assert spec.parameters == {"foo": "bar"}
        assert spec.tags == ["foo", "bar"]

    def test_multiple_specs_separate_from_flow(self):
        specs = deployment_specs_from_script(TEST_FILES_DIR / "multiple_deployments.py")
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

    def test_spec_from_yaml(self):
        specs = deployment_specs_from_yaml(TEST_FILES_DIR / "single-deployment.yaml")
        assert len(specs) == 1
        spec = list(specs)[0]
        assert spec.name == "hello-world-deployment"
        assert spec.flow_location == str(TEST_FILES_DIR / "single_flow.py")
        assert isinstance(spec.schedule, IntervalSchedule)
        assert spec.parameters == {"foo": "bar"}
        assert spec.tags == ["foo", "bar"]

    def test_multiple_specs_from_yaml(self):
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

    def test_loading_spec_does_not_raise_until_flow_is_loaded(self):
        specs = deployment_specs_from_yaml(
            TEST_FILES_DIR / "deployment-with-flow-load-error.yaml"
        )
        assert len(specs) == 1
        spec = list(specs)[0]
        with pytest.raises(FlowScriptError):
            spec.load_flow()


async def test_create_deployment_from_spec(orion_client):
    schedule = IntervalSchedule(interval=timedelta(days=1))

    spec = DeploymentSpec(
        name="test",
        flow_location=TEST_FILES_DIR / "single_flow.py",
        schedule=schedule,
        parameters={"foo": "bar"},
        tags=["foo", "bar"]
    )
    deployment_id = await create_deployment_from_spec(spec, client=orion_client)

    # Deployment was created in backend
    lookup = await orion_client.read_deployment(deployment_id)
    assert lookup.name == "test"
    assert lookup.schedule == schedule
    assert lookup.parameters == {"foo": "bar"}
    assert lookup.tags == ["foo", "bar"]

    # Location was encoded into a data document
    assert lookup.flow_data == DataDocument(
        encoding="file", blob=spec.flow_location.encode()
    )

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

    async def test_load_file_flow_from_deployment(
        self, flow_id, orion_client, tmp_path
    ):
        (tmp_path / "flow-script.py").write_text(
            textwrap.dedent(
                """
                from prefect import flow

                @flow
                def foo():
                    pass
                """
            )
        )
        deployment = Deployment(
            name="test",
            flow_id=flow_id,
            flow_data=DataDocument(
                encoding="file",
                blob=str((tmp_path / "flow-script.py").absolute()).encode(),
            ),
        )
        loaded_flow_object = await load_flow_from_deployment(
            deployment, client=orion_client
        )
        assert isinstance(loaded_flow_object, Flow)
        assert loaded_flow_object.name == "foo"

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
        self, flow_object, flow_id, orion_client
    ):
        deployment = Deployment(
            name="test",
            flow_id=flow_id,
            flow_data=await orion_client.persist_object(flow_object),
        )
        loaded_flow_object = await load_flow_from_deployment(
            deployment, client=orion_client
        )
        assert isinstance(loaded_flow_object, Flow)
        assert flow_object.name == loaded_flow_object.name

    async def test_load_persisted_flow_script_from_deployment(
        self, flow_object, flow_id, orion_client
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
            ),
        )
        loaded_flow_object = await load_flow_from_deployment(
            deployment, client=orion_client
        )
        assert isinstance(loaded_flow_object, Flow)
        assert flow_object.name == loaded_flow_object.name

    async def test_load_bad_flow_scriptfrom_deployment(self, flow_id, orion_client):
        deployment = Deployment(
            name="test",
            flow_id=flow_id,
            flow_data=await orion_client.persist_object(
                "test",
                encoder="text",
            ),
        )
        with pytest.raises(FlowScriptError):
            await load_flow_from_deployment(deployment, client=orion_client)

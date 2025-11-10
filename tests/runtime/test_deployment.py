import pytest

from prefect import flow
from prefect.flow_engine import run_flow_async
from prefect.runtime import deployment


@pytest.fixture
async def deployment_id(flow, prefect_client):
    response = await prefect_client.create_deployment(
        name="My Deployment",
        version="gold",
        flow_id=flow.id,
        tags=["foo"],
        parameters={"foo": "bar"},
    )
    return response


class TestAttributeAccessPatterns:
    async def test_access_unknown_attribute_fails(self):
        with pytest.raises(AttributeError, match="beep"):
            deployment.beep

    async def test_import_unknown_attribute_fails(self):
        with pytest.raises(ImportError, match="boop"):
            from prefect.runtime.deployment import boop  # noqa

    async def test_known_attributes_autocomplete(self):
        assert "id" in dir(deployment)
        assert "foo" not in dir(deployment)

    async def test_new_attribute_via_env_var(self, monkeypatch):
        monkeypatch.setenv(name="PREFECT__RUNTIME__DEPLOYMENT__NEW_KEY", value="foobar")
        assert deployment.new_key == "foobar"

    @pytest.mark.parametrize(
        "attribute_name, attribute_value, env_value, expected_value",
        [
            # check allowed types for existing attributes
            ("bool_attribute", True, "False", False),
            ("int_attribute", 10, "20", 20),
            ("float_attribute", 10.5, "20.5", 20.5),
            ("str_attribute", "foo", "bar", "bar"),
        ],
    )
    async def test_attribute_override_via_env_var(
        self, monkeypatch, attribute_name, attribute_value, env_value, expected_value
    ):
        # mock attribute_name to be a function that generates attribute_value
        monkeypatch.setitem(deployment.FIELDS, attribute_name, lambda: attribute_value)

        monkeypatch.setenv(
            name=f"PREFECT__RUNTIME__DEPLOYMENT__{attribute_name.upper()}",
            value=env_value,
        )
        deployment_attr = getattr(deployment, attribute_name)
        # check the type of the deployment attribute
        assert isinstance(deployment_attr, type(expected_value))
        # check the deployment attribute value is expected_value
        assert deployment_attr == expected_value

    @pytest.mark.parametrize(
        "attribute_name, attribute_value",
        [
            # complex types (list and dict) not allowed to be mocked using environment variables
            ("list_of_values", [1, 2, 3]),
            ("dict_of_values", {"foo": "bar"}),
        ],
    )
    async def test_attribute_override_via_env_var_not_allowed(
        self, monkeypatch, attribute_name, attribute_value
    ):
        # mock attribute_name to be a function that generates attribute_value
        monkeypatch.setitem(deployment.FIELDS, attribute_name, lambda: attribute_value)

        monkeypatch.setenv(
            name=f"PREFECT__RUNTIME__DEPLOYMENT__{attribute_name.upper()}", value="foo"
        )
        with pytest.raises(ValueError, match="cannot be mocked"):
            getattr(deployment, attribute_name)


class TestID:
    """
    This class may appear to reproduce some tests from the AttributeAccessPatterns tests
    but is intended to be copy / pastable for other new attributes to ensure full coverage of
    feature set for each attribute.
    """

    async def test_id_is_attribute(self):
        assert "id" in dir(deployment)

    async def test_id_is_none_when_not_set(self, monkeypatch, prefect_client):
        assert deployment.id is None

        run = await prefect_client.create_flow_run(flow=flow(lambda: None, name="test"))
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert deployment.id is None

    async def test_id_is_loaded_when_run_id_known(
        self, deployment_id, monkeypatch, prefect_client
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(deployment_id)

        assert deployment.id is None

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(flow_run.id))
        assert deployment.id == str(deployment_id)


class TestName:
    async def test_name_is_attribute(self):
        assert "name" in dir(deployment)

    async def test_name_is_none_when_not_set(self, monkeypatch, prefect_client):
        assert deployment.name is None

        run = await prefect_client.create_flow_run(flow=flow(lambda: None, name="test"))
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert deployment.name is None

    async def test_name_is_loaded_when_run_name_known(
        self, deployment_id, monkeypatch, prefect_client
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(deployment_id)

        assert deployment.name is None

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(flow_run.id))
        assert deployment.name == "My Deployment"


class TestVersion:
    async def test_version_is_attribute(self):
        assert "version" in dir(deployment)

    async def test_version_is_none_when_not_set(self, monkeypatch, prefect_client):
        assert deployment.version is None

        run = await prefect_client.create_flow_run(flow=flow(lambda: None, name="test"))

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert deployment.version is None

    async def test_version_is_loaded_when_run_version_known(
        self, deployment_id, monkeypatch, prefect_client
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(deployment_id)

        assert deployment.version is None

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(flow_run.id))
        assert deployment.version == "gold"


class TestFlowRunId:
    async def test_run_id_is_attribute(self):
        assert "flow_run_id" in dir(deployment)

    async def test_run_id_is_none_when_not_set(self):
        assert deployment.flow_run_id is None

    async def test_run_id_uses_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value="foo")
        assert deployment.flow_run_id == "foo"


class TestParameters:
    async def test_parameters_is_attribute(self):
        assert "parameters" in dir(deployment)

    async def test_parameters_is_empty_when_not_set(self):
        assert deployment.parameters == {}

    async def test_parameters_are_loaded_when_run_id_known(
        self, deployment_id, monkeypatch, prefect_client
    ):
        flow_run = await prefect_client.create_flow_run_from_deployment(deployment_id)

        assert deployment.parameters == {}

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(flow_run.id))
        assert deployment.parameters == {"foo": "bar"}  # see fixture at top of file

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id, parameters={"foo": 42}
        )

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(flow_run.id))
        assert deployment.parameters == {"foo": 42}

    async def test_parameters_accessible_in_nested_flows(
        self, deployment_id, prefect_client
    ):
        """Test that deployment.parameters is accessible in nested flows (issue #19329)."""

        seen_params = {}

        @flow
        async def nested_flow():
            seen_params["nested"] = deployment.parameters
            return deployment.parameters

        @flow
        async def parent_flow():
            seen_params["parent"] = deployment.parameters
            result = await nested_flow()
            return {"parent": deployment.parameters, "nested": result}

        # Create flow run from deployment with custom parameters
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id, parameters={"foo": "from_deployment"}
        )

        # Execute the flow using the flow engine helper
        await run_flow_async(parent_flow, flow_run=flow_run)

        # Both parent and nested should see the deployment parameters
        assert seen_params["parent"] == {"foo": "from_deployment"}
        assert seen_params["nested"] == {"foo": "from_deployment"}

    async def test_parameters_accessible_in_deeply_nested_flows(
        self, deployment_id, prefect_client
    ):
        """Test that deployment.parameters propagates through multiple nesting levels."""

        # Track what we saw at each level
        seen_params = {}

        @flow
        async def doubly_nested_flow():
            seen_params["doubly_nested"] = deployment.parameters
            return deployment.parameters

        @flow
        async def nested_flow():
            seen_params["nested"] = deployment.parameters
            result = await doubly_nested_flow()
            return result

        @flow
        async def parent_flow():
            seen_params["parent"] = deployment.parameters
            result = await nested_flow()
            return result

        # Create flow run from deployment with custom parameters
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id, parameters={"foo": "from_deployment", "level": "deep"}
        )

        # Execute the flow using the flow engine helper
        await run_flow_async(parent_flow, flow_run=flow_run)

        # All levels should see the deployment parameters
        expected = {"foo": "from_deployment", "level": "deep"}
        assert seen_params["parent"] == expected
        assert seen_params["nested"] == expected
        assert seen_params["doubly_nested"] == expected

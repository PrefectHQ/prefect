import pytest

from prefect import flow
from prefect.runtime import deployment


@pytest.fixture
async def deployment_id(flow, orion_client):
    response = await orion_client.create_deployment(
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


class TestID:
    """
    This class may appear to reproduce some tests from the AttributeAccessPatterns tests
    but is intended to be copy / pastable for other new attributes to ensure full coverage of
    feature set for each attribute.
    """

    async def test_id_is_attribute(self):
        assert "id" in dir(deployment)

    async def test_id_is_none_when_not_set(self, monkeypatch, orion_client):
        assert deployment.id is None

        run = await orion_client.create_flow_run(flow=flow(lambda: None, name="test"))
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert deployment.id is None

    async def test_id_is_loaded_when_run_id_known(
        self, deployment_id, monkeypatch, orion_client
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(deployment_id)

        assert deployment.id is None

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(flow_run.id))
        assert deployment.id == str(deployment_id)


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
        self, deployment_id, monkeypatch, orion_client
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(deployment_id)

        assert deployment.parameters == {}

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(flow_run.id))
        assert deployment.parameters == {"foo": "bar"}  # see fixture at top of file

        flow_run = await orion_client.create_flow_run_from_deployment(
            deployment_id, parameters={"foo": 42}
        )

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(flow_run.id))
        assert deployment.parameters == {"foo": 42}

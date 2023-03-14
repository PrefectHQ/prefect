import pytest

from prefect.runtime import deployment


class TestAttributeAccessPatterns:
    async def test_access_unknown_attribute_fails(self):
        with pytest.raises(AttributeError, match="beep"):
            deployment.beep

    async def test_import_unknown_attribute_fails(self):
        with pytest.raises(ImportError, match="boop"):
            from prefect.runtime.deployment import boop

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

    async def test_id_is_none_when_not_set(self):
        assert deployment.id is None


class TestFlowRunId:
    async def test_id_uses_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value="foo")
        assert deployment.flow_run_id == "foo"

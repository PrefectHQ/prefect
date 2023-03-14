import pytest
from prefect import flow
from prefect.runtime import flow_run


class TestAttributeAccessPatterns:
    async def test_access_unknown_attribute_fails(self):
        with pytest.raises(AttributeError, match="beep"):
            flow_run.beep

    async def test_import_unknown_attribute_fails(self):
        with pytest.raises(ImportError, match="boop"):
            from prefect.runtime.flow_run import boop

    async def test_known_attributes_autocomplete(self):
        assert "id" in dir(flow_run)
        assert "foo" not in dir(flow_run)


class TestID:
    """
    This class may appear to reproduce some tests from the AttributeAccessPatterns tests
    but is intended to be copy / pastable for other new attributes to ensure full coverage of
    feature set for each attribute.
    """

    async def test_id_is_attribute(self):
        assert "id" in dir(flow_run)

    async def test_id_is_none_when_not_set(self):
        assert flow_run.id is None

    async def test_id_uses_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value="foo")
        assert flow_run.id == "foo"

    async def test_id_prioritizes_context_info_over_env_var_dynamically(
        self, monkeypatch
    ):
        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value="foo")

        assert flow_run.id == "foo"

        @flow
        def flow_with_new_id():
            return flow_run.id

        assert flow_with_new_id() != "foo"
        assert flow_run.id == "foo"

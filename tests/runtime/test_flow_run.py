import pytest

from prefect import flow, tags
from prefect.runtime import flow_run


class TestAttributeAccessPatterns:
    async def test_access_unknown_attribute_fails(self):
        with pytest.raises(AttributeError, match="beep"):
            flow_run.beep

    async def test_import_unknown_attribute_fails(self):
        with pytest.raises(ImportError, match="boop"):
            from prefect.runtime.flow_run import boop  # noqa

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

        new_id = flow_with_new_id()
        assert isinstance(new_id, str)
        assert flow_with_new_id() != "foo"
        assert flow_run.id == "foo"


class TestTags:
    async def test_tags_is_attribute(self):
        assert "tags" in dir(flow_run)

    async def test_tags_is_empty_when_not_set(self):
        assert flow_run.tags == []

    async def test_tags_returns_tags_when_present_dynamically(self):
        assert flow_run.tags == []

        @flow
        def run_with_tags():
            return flow_run.tags

        with tags("foo", "bar"):
            assert set(run_with_tags()) == {"foo", "bar"}

        assert flow_run.tags == []

    async def test_tags_pulls_from_api_when_needed(self, monkeypatch, orion_client):
        run = await orion_client.create_flow_run(
            flow=flow(lambda: None, name="test"), tags=["red", "green"]
        )
        assert flow_run.tags == []

        monkeypatch.setenv(name="PREFECT__FLOW_RUN_ID", value=str(run.id))

        assert set(flow_run.tags) == {"red", "green"}

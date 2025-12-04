import pydantic
import pytest
from pydantic import ValidationError

from prefect.context import FlowRunContext
from prefect.flows import flow
from prefect.input import (
    acreate_flow_run_input,
    acreate_flow_run_input_from_model,
    adelete_flow_run_input,
    afilter_flow_run_input,
    aread_flow_run_input,
    create_flow_run_input,
    create_flow_run_input_from_model,
    delete_flow_run_input,
    filter_flow_run_input,
    read_flow_run_input,
)


class DemoModel(pydantic.BaseModel):
    name: str
    age: int


@pytest.fixture
def flow_run_context(flow_run, prefect_client):
    with FlowRunContext.model_construct(
        flow_run=flow_run, client=prefect_client
    ) as context:
        yield context


class TestCreateFlowRunInputFromModel:
    async def test_creates_flow_run_input(self, flow_run_context):
        demo = DemoModel(name="Bob", age=100)
        await create_flow_run_input_from_model(key="key", model_instance=demo)

        value = await read_flow_run_input(
            key="key", flow_run_id=flow_run_context.flow_run.id
        )

        assert DemoModel(**value) == demo

    async def test_sets_sender_to_flow_run_in_context(self, flow_run_context):
        demo = DemoModel(name="Bob", age=100)
        await create_flow_run_input_from_model(key="key", model_instance=demo)

        flow_run_inputs = await filter_flow_run_input(
            key_prefix="key", flow_run_id=flow_run_context.flow_run.id
        )

        assert len(flow_run_inputs) == 1
        assert (
            flow_run_inputs[0].sender
            == f"prefect.flow-run.{flow_run_context.flow_run.id}"
        )

    async def test_can_set_sender(self, flow_run_context):
        demo = DemoModel(name="Bob", age=100)
        await create_flow_run_input_from_model(
            key="key", model_instance=demo, sender="somebody"
        )

        flow_run_inputs = await filter_flow_run_input(
            key_prefix="key", flow_run_id=flow_run_context.flow_run.id
        )

        assert len(flow_run_inputs) == 1
        assert flow_run_inputs[0].sender == "somebody"

    async def test_no_sender_no_flow_run_context(self, flow_run):
        demo = DemoModel(name="Bob", age=100)
        await create_flow_run_input_from_model(
            key="key", model_instance=demo, flow_run_id=flow_run.id
        )

        flow_run_inputs = await filter_flow_run_input(
            key_prefix="key", flow_run_id=flow_run.id
        )

        assert len(flow_run_inputs) == 1
        assert flow_run_inputs[0].sender is None


class TestCreateFlowRunInput:
    async def test_implicit_flow_run(self, flow_run_context):
        await create_flow_run_input(key="key", value="value")
        assert (
            await read_flow_run_input(
                key="key", flow_run_id=flow_run_context.flow_run.id
            )
            == "value"
        )

    async def test_explicit_flow_run(self, flow_run):
        await create_flow_run_input(key="key", value="value", flow_run_id=flow_run.id)
        assert await read_flow_run_input(key="key", flow_run_id=flow_run.id) == "value"

    async def test_no_flow_run_raises(self):
        with pytest.raises(
            RuntimeError, match="provide a flow run ID or be within a flow run"
        ):
            await create_flow_run_input(key="key", value="value")

    async def test_validates_key(self, flow_run):
        with pytest.raises(ValidationError):
            await create_flow_run_input(
                key="invalid key *@&*$&", value="value", flow_run_id=flow_run.id
            )

    def test_can_be_used_sync(self):
        @flow
        def test_flow():
            create_flow_run_input(key="key", value="value")
            assert (
                read_flow_run_input(key="key", flow_run_id=flow_run_context.flow_run.id)
                == "value"
            )


class TestDeleteFlowRunInput:
    async def test_implicit_flow_run(self, flow_run_context):
        await create_flow_run_input(key="key", value="value")
        await delete_flow_run_input(key="key")
        assert (
            await read_flow_run_input(
                key="key", flow_run_id=flow_run_context.flow_run.id
            )
            is None
        )

    async def test_explicit_flow_run(self, flow_run):
        await create_flow_run_input(key="key", value="value", flow_run_id=flow_run.id)
        await delete_flow_run_input(key="key", flow_run_id=flow_run.id)
        assert await read_flow_run_input(key="key", flow_run_id=flow_run.id) is None


class TestReadFlowRunInput:
    async def test_implicit_flow_run(self, flow_run_context):
        await create_flow_run_input(key="key", value="value")
        assert await read_flow_run_input(key="key") == "value"

    async def test_explicit_flow_run(self, flow_run):
        await create_flow_run_input(key="key", value="value", flow_run_id=flow_run.id)
        assert await read_flow_run_input(key="key", flow_run_id=flow_run.id) == "value"

    async def test_missing_key_returns_none(self, flow_run):
        assert await read_flow_run_input(key="missing", flow_run_id=flow_run.id) is None


class TestFilterFlowRunInput:
    @pytest.fixture
    async def flow_run_input_keys(self, flow_run):
        keys = {"key-1", "key-2", "different-1"}
        for key in keys:
            await create_flow_run_input(key=key, value="value", flow_run_id=flow_run.id)

        return keys

    async def test_implicit_flow_run(self, flow_run_context, flow_run_input_keys):
        filtered = await filter_flow_run_input(
            key_prefix="key", limit=len(flow_run_input_keys) + 1
        )
        assert len(filtered) == 2
        assert {"key-1", "key-2"} != flow_run_input_keys
        assert {"key-1", "key-2"} == {item.key for item in filtered}

    async def test_explicit_flow_run(self, flow_run, flow_run_input_keys):
        filtered = await filter_flow_run_input(
            key_prefix="key",
            limit=len(flow_run_input_keys) + 1,
            flow_run_id=flow_run.id,
        )
        assert len(filtered) == 2
        assert {"key-1", "key-2"} != flow_run_input_keys
        assert {"key-1", "key-2"} == {item.key for item in filtered}

    async def test_no_flow_run_raises(self):
        with pytest.raises(
            RuntimeError, match="provide a flow run ID or be within a flow run"
        ):
            await filter_flow_run_input(key_prefix="key")

    async def test_exclude_keys(self, flow_run_context, flow_run_input_keys):
        filtered = await filter_flow_run_input(
            key_prefix="key", limit=len(flow_run_input_keys) + 1, exclude_keys={"key-2"}
        )
        assert len(filtered) == 1
        assert {"key-1"} == {item.key for item in filtered}
        assert "key-2" in flow_run_input_keys


class TestAsyncDispatch:
    """Tests for the async_dispatch migration of input actions."""

    async def test_acreate_and_aread_flow_run_input(self, flow_run):
        """Test calling async functions directly."""
        await acreate_flow_run_input(
            key="test-key", value="test-value", flow_run_id=flow_run.id
        )
        result = await aread_flow_run_input(key="test-key", flow_run_id=flow_run.id)
        assert result == "test-value"

    async def test_afilter_flow_run_input(self, flow_run):
        """Test calling afilter directly."""
        await acreate_flow_run_input(
            key="filter-test-1", value="v1", flow_run_id=flow_run.id
        )
        await acreate_flow_run_input(
            key="filter-test-2", value="v2", flow_run_id=flow_run.id
        )

        results = await afilter_flow_run_input(
            key_prefix="filter-test", limit=10, flow_run_id=flow_run.id
        )
        assert len(results) == 2
        assert {r.key for r in results} == {"filter-test-1", "filter-test-2"}

    async def test_adelete_flow_run_input(self, flow_run):
        """Test calling adelete directly."""
        await acreate_flow_run_input(
            key="delete-key", value="to-delete", flow_run_id=flow_run.id
        )
        await adelete_flow_run_input(key="delete-key", flow_run_id=flow_run.id)
        result = await aread_flow_run_input(key="delete-key", flow_run_id=flow_run.id)
        assert result is None

    async def test_acreate_flow_run_input_from_model(self, flow_run):
        """Test calling async model creation directly."""
        demo = DemoModel(name="Alice", age=25)
        await acreate_flow_run_input_from_model(
            key="model-key", model_instance=demo, flow_run_id=flow_run.id
        )
        result = await aread_flow_run_input(key="model-key", flow_run_id=flow_run.id)
        assert DemoModel(**result) == demo

    async def test_dispatches_to_async_in_async_context(self, flow_run):
        """Test that sync functions dispatch to async when awaited."""
        # These should dispatch to async versions and can be awaited
        await create_flow_run_input(
            key="dispatch-key", value="dispatch-value", flow_run_id=flow_run.id
        )
        result = await read_flow_run_input(key="dispatch-key", flow_run_id=flow_run.id)
        assert result == "dispatch-value"

    def test_sync_functions_work_in_sync_context(self, flow_run):
        """Test that sync functions work in pure sync context."""
        # In a sync context (no event loop), should use sync implementations
        create_flow_run_input(
            key="sync-key", value="sync-value", flow_run_id=flow_run.id
        )
        result = read_flow_run_input(key="sync-key", flow_run_id=flow_run.id)
        assert result == "sync-value"

    def test_filter_in_sync_context(self, flow_run):
        """Test filter works in sync context."""
        create_flow_run_input(key="sync-filter-1", value="v1", flow_run_id=flow_run.id)
        create_flow_run_input(key="sync-filter-2", value="v2", flow_run_id=flow_run.id)

        results = filter_flow_run_input(
            key_prefix="sync-filter", limit=10, flow_run_id=flow_run.id
        )
        assert len(results) == 2
        assert {r.key for r in results} == {"sync-filter-1", "sync-filter-2"}

    def test_delete_in_sync_context(self, flow_run):
        """Test delete works in sync context."""
        create_flow_run_input(
            key="sync-delete", value="to-delete", flow_run_id=flow_run.id
        )
        delete_flow_run_input(key="sync-delete", flow_run_id=flow_run.id)
        result = read_flow_run_input(key="sync-delete", flow_run_id=flow_run.id)
        assert result is None

    def test_model_creation_in_sync_context(self, flow_run):
        """Test model creation works in sync context."""
        demo = DemoModel(name="Bob", age=30)
        create_flow_run_input_from_model(
            key="sync-model", model_instance=demo, flow_run_id=flow_run.id
        )
        result = read_flow_run_input(key="sync-model", flow_run_id=flow_run.id)
        assert DemoModel(**result) == demo

    def test_sync_in_sync_flow(self, flow_run):
        """Test sync usage within a sync flow."""

        @flow
        def sync_test_flow():
            create_flow_run_input(
                key="flow-key", value="flow-value", flow_run_id=flow_run.id
            )
            result = read_flow_run_input(key="flow-key", flow_run_id=flow_run.id)
            return result

        result = sync_test_flow()
        assert result == "flow-value"

    async def test_async_in_async_flow(self, flow_run):
        """Test async usage within an async flow."""

        @flow
        async def async_test_flow():
            await create_flow_run_input(
                key="async-flow-key", value="async-flow-value", flow_run_id=flow_run.id
            )
            result = await read_flow_run_input(
                key="async-flow-key", flow_run_id=flow_run.id
            )
            return result

        result = await async_test_flow()
        assert result == "async-flow-value"

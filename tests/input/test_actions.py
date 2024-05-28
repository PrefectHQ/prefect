import pydantic
import pytest
from pydantic import ValidationError

from prefect.context import FlowRunContext
from prefect.flows import flow
from prefect.input import (
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

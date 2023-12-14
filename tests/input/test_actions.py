import pytest

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import ValidationError
else:
    from pydantic import ValidationError

from prefect.context import FlowRunContext
from prefect.input import (
    create_flow_run_input,
    delete_flow_run_input,
    read_flow_run_input,
)


@pytest.fixture
def flow_run_context(flow_run, prefect_client):
    with FlowRunContext.construct(flow_run=flow_run, client=prefect_client) as context:
        yield context


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
        with pytest.raises(ValidationError, match="value must only contain"):
            await create_flow_run_input(
                key="invalid key *@&*$&", value="value", flow_run_id=flow_run.id
            )

    def test_can_be_used_sync(self, flow_run_context):
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

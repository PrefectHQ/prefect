import json

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.server import models

if HAS_PYDANTIC_V2:
    from pydantic.v1 import ValidationError
else:
    from pydantic import ValidationError


class TestCreateFlowRunInput:
    async def test_creates_flow_run_input(self, session: AsyncSession, flow_run):
        flow_run_input = await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.core.FlowRunInput(
                flow_run_id=flow_run.id,
                key="my-key",
                value=json.dumps({"complex": True}),
            ),
        )

        assert isinstance(flow_run_input, schemas.core.FlowRunInput)
        assert flow_run_input.flow_run_id == flow_run.id
        assert flow_run_input.key == "my-key"
        assert flow_run_input.value == json.dumps({"complex": True})

    async def test_flow_run_id_and_key_are_unique(
        self, session: AsyncSession, flow_run
    ):
        await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.core.FlowRunInput(
                flow_run_id=flow_run.id, key="my-key", value="my-value"
            ),
        )

        with pytest.raises(IntegrityError):
            await models.flow_run_input.create_flow_run_input(
                session=session,
                flow_run_input=schemas.core.FlowRunInput(
                    flow_run_id=flow_run.id, key="my-key", value="my-value"
                ),
            )

    @pytest.mark.parametrize(
        "key", ["my key", "user!123", "product?description", "my(key)", "my&key"]
    )
    async def test_non_url_safe_keys_invalid(
        self, key, session: AsyncSession, flow_run
    ):
        with pytest.raises(ValidationError):
            await models.flow_run_input.create_flow_run_input(
                session=session,
                flow_run_input=schemas.core.FlowRunInput(
                    flow_run_id=flow_run.id, key=key, value="my-value"
                ),
            )


class TestReadFlowRunInput:
    async def test_reads_flow_run_input(self, session: AsyncSession, flow_run):
        await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.core.FlowRunInput(
                flow_run_id=flow_run.id, key="my-key", value="my-value"
            ),
        )

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session, flow_run_id=flow_run.id, key="my-key"
        )

        assert isinstance(flow_run_input, schemas.core.FlowRunInput)
        assert flow_run_input.flow_run_id == flow_run.id
        assert flow_run_input.key == "my-key"


class TestDeleteFlowRunInput:
    async def test_deletes_flow_run_input(self, session: AsyncSession, flow_run):
        await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.core.FlowRunInput(
                flow_run_id=flow_run.id, key="my-key", value="my-value"
            ),
        )

        assert await models.flow_run_input.delete_flow_run_input(
            session=session, flow_run_id=flow_run.id, key="my-key"
        )

        assert (
            await models.flow_run_input.read_flow_run_input(
                session=session, flow_run_id=flow_run.id, key="my-key"
            )
            is None
        )

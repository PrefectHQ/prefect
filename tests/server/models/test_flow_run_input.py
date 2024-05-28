import json

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server import models


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


class TestFilterFlowRunInput:
    async def test_reads_flow_run_input(self, session: AsyncSession, flow_run):
        for key in ["my-key", "my-key2", "other-key"]:
            await models.flow_run_input.create_flow_run_input(
                session=session,
                flow_run_input=schemas.core.FlowRunInput(
                    flow_run_id=flow_run.id, key=key, value="my-value"
                ),
            )

        flow_run_inputs = await models.flow_run_input.filter_flow_run_input(
            session=session,
            flow_run_id=flow_run.id,
            prefix="my-key",
            limit=10,
            exclude_keys=[],
        )

        assert len(flow_run_inputs) == 2
        assert all(
            isinstance(flow_run_input, schemas.core.FlowRunInput)
            for flow_run_input in flow_run_inputs
        )
        assert {flow_run_input.key for flow_run_input in flow_run_inputs} == {
            "my-key",
            "my-key2",
        }

    async def test_reads_flow_run_input_exclude_keys(
        self, session: AsyncSession, flow_run
    ):
        for key in ["my-key", "my-key2", "other-key"]:
            await models.flow_run_input.create_flow_run_input(
                session=session,
                flow_run_input=schemas.core.FlowRunInput(
                    flow_run_id=flow_run.id, key=key, value="my-value"
                ),
            )

        flow_run_inputs = await models.flow_run_input.filter_flow_run_input(
            session=session,
            flow_run_id=flow_run.id,
            prefix="my-key",
            limit=10,
            exclude_keys=["my-key2"],
        )

        assert len(flow_run_inputs) == 1
        assert all(
            isinstance(flow_run_input, schemas.core.FlowRunInput)
            for flow_run_input in flow_run_inputs
        )
        assert {flow_run_input.key for flow_run_input in flow_run_inputs} == {"my-key"}


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

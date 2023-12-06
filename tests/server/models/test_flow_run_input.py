import json

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import prefect.server.schemas as schemas
from prefect.server import models


class TestCreateFlowRunInput:
    async def test_creates_flow_run_input(self, session: AsyncSession, flow_run):
        flow_run_input = await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.actions.FlowRunInputCreate(
                flow_run_id=flow_run.id, key="my-key", value=json.dumps("my-value")
            ),
        )

        assert isinstance(flow_run_input, schemas.core.FlowRunInput)
        assert flow_run_input.flow_run_id == flow_run.id
        assert flow_run_input.key == "my-key"

        # The value is stored as a JSON string, and the modeling makes no
        # attempts to decode it, so the value returned within the value
        # container is a string that has been JSON encoded.
        value_id = flow_run_input.value["items"][0]["_item_id"]
        assert flow_run_input.value == {
            "__prefect_metadata": {},
            "items": [{"_item_id": value_id, "value": '"my-value"'}],
        }

    async def test_creates_flow_run_input_complex_value(
        self, session: AsyncSession, flow_run
    ):
        flow_run_json = schemas.core.FlowRun.from_orm(flow_run).json()

        flow_run_input = await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.actions.FlowRunInputCreate(
                flow_run_id=flow_run.id,
                key="my-key",
                value=flow_run_json,
            ),
        )

        assert isinstance(flow_run_input, schemas.core.FlowRunInput)
        assert flow_run_input.flow_run_id == flow_run.id
        assert flow_run_input.key == "my-key"

        value_id = flow_run_input.value["items"][0]["_item_id"]
        assert flow_run_input.value == {
            "__prefect_metadata": {},
            "items": [{"_item_id": value_id, "value": flow_run_json}],
        }

    async def test_flow_run_id_and_key_are_unique(
        self, session: AsyncSession, flow_run
    ):
        await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.actions.FlowRunInputCreate(
                flow_run_id=flow_run.id, key="my-key", value="my-value"
            ),
        )

        with pytest.raises(IntegrityError):
            await models.flow_run_input.create_flow_run_input(
                session=session,
                flow_run_input=schemas.actions.FlowRunInputCreate(
                    flow_run_id=flow_run.id, key="my-key", value="my-value"
                ),
            )


class TestReadFlowRunInput:
    async def test_reads_flow_run_input(self, session: AsyncSession, flow_run):
        await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.actions.FlowRunInputCreate(
                flow_run_id=flow_run.id, key="my-key", value="my-value"
            ),
        )

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session, flow_run_id=flow_run.id, key="my-key"
        )

        assert isinstance(flow_run_input, schemas.core.FlowRunInput)
        assert flow_run_input.flow_run_id == flow_run.id
        assert flow_run_input.key == "my-key"


class TestUpdateFlowRun:
    async def test_updates_flow_run_input(self, session: AsyncSession, flow_run):
        await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.actions.FlowRunInputCreate(
                flow_run_id=flow_run.id, key="my-key", value=json.dumps("my-value")
            ),
        )

        assert await models.flow_run_input.update_flow_run_input(
            session=session,
            flow_run_input=schemas.actions.FlowRunInputUpdate(
                flow_run_id=flow_run.id,
                key="my-key",
                value=json.dumps("my-new-value"),
            ),
        )

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session, flow_run_id=flow_run.id, key="my-key"
        )
        value_id = flow_run_input.value["items"][0]["_item_id"]
        assert flow_run_input.value == {
            "__prefect_metadata": {},
            "items": [{"_item_id": value_id, "value": '"my-new-value"'}],
        }

    async def test_updates_flow_run_input_complex_value(
        self, session: AsyncSession, flow_run
    ):
        flow_run_input = await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.actions.FlowRunInputCreate(
                flow_run_id=flow_run.id,
                key="my-key",
                value="some-value",
            ),
        )

        flow_run_json = schemas.core.FlowRun.from_orm(flow_run).json()

        assert await models.flow_run_input.update_flow_run_input(
            session=session,
            flow_run_input=schemas.actions.FlowRunInputUpdate(
                flow_run_id=flow_run.id,
                key="my-key",
                value=flow_run_json,
            ),
        )

        flow_run_input = await models.flow_run_input.read_flow_run_input(
            session=session, flow_run_id=flow_run.id, key="my-key"
        )
        value_id = flow_run_input.value["items"][0]["_item_id"]
        assert flow_run_input.value == {
            "__prefect_metadata": {},
            "items": [{"_item_id": value_id, "value": flow_run_json}],
        }


class TestDeleteFlowRunInput:
    async def test_deletes_flow_run_input(self, session: AsyncSession, flow_run):
        await models.flow_run_input.create_flow_run_input(
            session=session,
            flow_run_input=schemas.actions.FlowRunInputCreate(
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

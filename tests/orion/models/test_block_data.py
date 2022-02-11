import time
from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from tests.fixtures.database import session


class TestBlockDatas:
    async def test_creating_block_datii_then_reading_as_blocks(self, session):
        # the plural of data is datii right?

        blockdata = await models.block_data.create_block_data(
            session=session,
            block_data=schemas.core.BlockData(
                name="hi-im-some-blockdata",
                blockref="a-definitely-implemented-stateful-api",
                data=dict(),
            ),
        )
        assert blockdata.name == "hi-im-some-blockdata"
        assert blockdata.blockref == "a-definitely-implemented-stateful-api"

        block = await models.block_data.read_block_data_by_name_as_block(
            session=session, name="hi-im-some-blockdata"
        )

        assert isinstance(block, dict)
        assert block["blockname"] == blockdata.name
        assert block["blockref"] == blockdata.blockref

    async def test_deleting_block_datums(self, session):

        blockdata = await models.block_data.create_block_data(
            session=session,
            block_data=schemas.core.BlockData(
                name="i-want-to-live-forever",
                blockref="a-trendy-api",
                data=dict(),
            ),
        )
        assert blockdata.name == "i-want-to-live-forever"
        assert blockdata.blockref == "a-trendy-api"

        await models.block_data.delete_block_data_by_name(
            session=session, name="i-want-to-live-forever"
        )

        fetched_blockdata = await models.block_data.read_block_data_by_name_as_block(
            session=session, name="i-want-to-live-forever"
        )

        assert fetched_blockdata is None

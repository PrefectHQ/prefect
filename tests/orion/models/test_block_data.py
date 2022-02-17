import time
from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.models.block_data import pack_blockdata, unpack_blockdata
from tests.fixtures.database import session


class TestBlockData:
    async def test_creating_block_data_then_reading_by_name_as_blocks(self, session):
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
        assert blockdata.data != dict(), "block data is encrypted"

        block = await models.block_data.read_block_data_by_name_as_block(
            session=session, name="hi-im-some-blockdata"
        )

        assert isinstance(block, dict)
        assert block["blockname"] == blockdata.name
        assert block["blockref"] == blockdata.blockref
        assert (
            len(block) == 3
        ), "because the data field is empty, the unpacked block will have only 3 fields"

    async def test_creating_block_data_then_reading_as_blocks(self, session):

        blockdata = await models.block_data.create_block_data(
            session=session,
            block_data=schemas.core.BlockData(
                name="hi-im-some-blockdata",
                blockref="a-definitely-implemented-stateful-api",
                data=dict(realdata=42),
            ),
        )
        assert blockdata.name == "hi-im-some-blockdata"
        assert blockdata.blockref == "a-definitely-implemented-stateful-api"
        assert blockdata.data != dict(realdata=42), "block data is encrypted"

        block = await models.block_data.read_block_data_as_block(
            session=session, block_data_id=blockdata.id
        )

        assert isinstance(block, dict)
        assert block["blockname"] == blockdata.name
        assert block["blockref"] == blockdata.blockref
        assert block["blockref"] == blockdata.blockref
        assert block["realdata"] == 42

    async def test_deleting_block_data(self, session):

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

        delete_result = await models.block_data.delete_block_data_by_name(
            session=session, name="i-want-to-live-forever"
        )

        assert delete_result is True

        fetched_blockdata = await models.block_data.read_block_data_by_name_as_block(
            session=session, name="i-want-to-live-forever"
        )

        assert fetched_blockdata is None

    async def test_deleting_gracefully(self, session):

        delete_result = await models.block_data.delete_block_data_by_name(
            session=session, name="hello-is-anybody-home"
        )
        assert delete_result is False

    async def test_updating_block_name(self, session):
        blockdata = await models.block_data.create_block_data(
            session=session,
            block_data=schemas.core.BlockData(
                name="2d-lattice",
                blockref="transfer-matrix-methods",
                data=dict(),
            ),
        )

        fancier_blockdata = schemas.actions.BlockDataCreate(
            name="nd-lattice",
            blockref="hartree-fock",
            data=dict(interactions="nearest-neighbor-spin"),
        )

        update_result = await models.block_data.update_block_data(
            session=session,
            name="2d-lattice",
            block_data=fancier_blockdata,
        )
        assert update_result is True

        less_fancy = await models.block_data.read_block_data_by_name_as_block(
            session=session, name="2d-lattice"
        )
        assert less_fancy is None

        too_fancy = await models.block_data.read_block_data_by_name_as_block(
            session=session, name="nd-lattice"
        )
        assert too_fancy["blockref"] == "hartree-fock"
        assert too_fancy["interactions"] == "nearest-neighbor-spin"

    async def test_updating_nonexistent_blocks(self, session):
        imaginary = schemas.actions.BlockDataUpdate(
            name="willed-into-existence",
            data=dict(),
        )

        update_result = await models.block_data.update_block_data(
            session=session,
            name="a-block-that-never-was",
            block_data=imaginary,
        )
        assert update_result is False

    async def test_packing_and_unpacking_data_are_invertable(self, session):
        starting_blockdata = {
            "blockname": "neo",
            "blockref": "the matrix",
            "needs": "trinity",
            "also_needs": "smith",
        }

        packed_blockdata = pack_blockdata(starting_blockdata.copy())
        roundtrip_blockdata = unpack_blockdata(packed_blockdata)
        roundtrip_blockdata.pop("blockid", None)
        assert starting_blockdata == roundtrip_blockdata

"""
Functions for interacting with block ORM objects.
Intended for internal use by the Orion API.
"""
import json
import os
from uuid import UUID

import pendulum
import sqlalchemy as sa
from cryptography.fernet import Fernet

from prefect.orion import schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.models import configurations


@inject_db
async def create_block(
    session: sa.orm.Session,
    block: schemas.core.Block,
    db: OrionDBInterface,
):
    insert_values = block.dict(
        shallow=True, exclude_unset=False, exclude={"created", "updated"}
    )
    insert_values["data"] = await encrypt_blockdata(session, insert_values["data"])
    insert_stmt = (await db.insert(db.Block)).values(**insert_values)

    await session.execute(insert_stmt)
    query = (
        sa.select(db.Block)
        .filter_by(name=block.name, block_spec_id=block.block_spec_id)
        .execution_options(populate_existing=True)
    )

    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_block_by_id(
    session: sa.orm.Session,
    block_id: UUID,
    db: OrionDBInterface,
):
    query = sa.select(db.Block).where(db.Block.id == block_id).with_for_update()

    result = await session.execute(query)
    block = result.scalar()

    if not block:
        return None

    block.data = await decrypt_blockdata(session, block.data)
    return block


@inject_db
async def read_block_by_name(
    session: sa.orm.Session,
    name: str,
    block_spec_name: str,
    db: OrionDBInterface,
    block_spec_version: str = None,
):
    """
    Read a block with the given name and block spec name. If a block spec version
    is provided, it is matched as well, otherwise the latest matching version is returned.
    """
    where_clause = [
        db.Block.name == name,
        db.BlockSpec.name == block_spec_name,
    ]
    if block_spec_version is not None:
        where_clause.append(db.BlockSpec.version == block_spec_version)

    query = (
        sa.select(db.Block)
        .join(db.BlockSpec, db.BlockSpec.id == db.Block.block_spec_id)
        .where(sa.and_(*where_clause))
        .order_by(db.BlockSpec.version.desc())
        .limit(1)
    )
    result = await session.execute(query)
    block = result.scalar()

    if not block:
        return None

    block.data = await decrypt_blockdata(session, block.data)
    return block


@inject_db
async def delete_block(
    session: sa.orm.Session,
    block_id: UUID,
    db: OrionDBInterface,
) -> bool:

    query = sa.delete(db.Block).where(db.Block.id == block_id)
    result = await session.execute(query)
    return result.rowcount > 0


@inject_db
async def update_block(
    session: sa.orm.Session,
    block_id: UUID,
    block: schemas.actions.BlockUpdate,
    db: OrionDBInterface,
) -> bool:

    update_values = block.dict(shallow=True, exclude_unset=True)
    update_values = {k: v for k, v in update_values.items() if v is not None}
    if "data" in update_values:
        update_values["data"] = await encrypt_blockdata(session, update_values["data"])

    update_stmt = (
        sa.update(db.Block).where(db.Block.id == block_id).values(update_values)
    )

    result = await session.execute(update_stmt)
    return result.rowcount > 0


async def get_fernet_encryption(session):
    environment_key = os.getenv("ORION_BLOCK_ENCRYPTION_KEY")
    if environment_key:
        return Fernet(environment_key.encode())

    configured_key = await configurations.read_configuration_by_key(
        session, "BLOCK_ENCRYPTION_KEY"
    )

    if configured_key is None:
        encryption_key = Fernet.generate_key()
        configured_key = schemas.core.Configuration(
            key="BLOCK_ENCRYPTION_KEY", value={"fernet_key": encryption_key.decode()}
        )
        await configurations.create_configuration(session, configured_key)
    else:
        encryption_key = configured_key.value["fernet_key"].encode()
    return Fernet(encryption_key)


async def encrypt_blockdata(session, blockdata: dict):
    fernet = await get_fernet_encryption(session)
    byte_blob = json.dumps(blockdata).encode()
    return {"encrypted_blob": fernet.encrypt(byte_blob).decode()}


async def decrypt_blockdata(session, blockdata: dict):
    fernet = await get_fernet_encryption(session)
    byte_blob = blockdata["encrypted_blob"].encode()
    return json.loads(fernet.decrypt(byte_blob).decode())

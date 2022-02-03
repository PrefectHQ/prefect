import datetime
from functools import wraps

from pydantic import BaseModel


class BlockData(BaseModel):
    data: dict
    blockref: str


def register_blockapi(blockref):
    def wrapper(fn):
        return fn

    return wrapper


def assemble_block(blockdata=None):
    # block = BlockRegistry.get(blockdata.blockref)
    # return block(blockdata)
    from prefect.blocks.storage import LocalStorageBlock, OrionStorageBlock

    return LocalStorageBlock(dict())


class BlockAPI:
    pass

import datetime
from functools import wraps
from typing import Dict

from pydantic import BaseModel

BLOCK_API_REGISTRY: Dict[str, "BlockAPI"] = dict()


def register_blockapi(blockref):
    def wrapper(blockapi):
        BLOCK_API_REGISTRY[blockref] = blockapi
        return blockapi

    return wrapper


class BlockAPI:
    pass


def assemble_block(blockdata=None):
    from prefect.blocks import storage

    block = BLOCK_API_REGISTRY.get(blockdata.blockref)
    return block(blockdata)


import datetime
from functools import wraps
from typing import Dict

from pydantic import BaseModel, parse_obj_as

BLOCK_API_REGISTRY: Dict[str, "BlockAPI"] = dict()


def register_blockapi(blockref):
    def wrapper(blockapi):
        BLOCK_API_REGISTRY[blockref] = blockapi
        return blockapi

    return wrapper


class BlockAPI(BaseModel):
    name: str


def assemble_block(blockdata=None):
    from prefect.blocks import storage

    blockapi = BLOCK_API_REGISTRY.get(blockdata.blockref)
    block = {"name": blockdata.name, **blockdata.data}

    return parse_obj_as(blockapi, block)

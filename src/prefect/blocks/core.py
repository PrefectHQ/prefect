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
    blockname: str
    blockref: str
    blockid: str


def assemble_block(block=None):
    from prefect.blocks import storage

    blockapi = BLOCK_API_REGISTRY.get(block["blockref"])
    return parse_obj_as(blockapi, block)

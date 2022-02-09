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


def get_blockapi(blockref):
    from prefect.blocks import storage

    return BLOCK_API_REGISTRY.get(blockref)


class BlockAPI(BaseModel):
    blockname: str
    blockref: str
    blockid: str

import sys
from types import ModuleType
from typing import Optional

from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.orchestration import get_client


def get(name: str, default: str = None) -> Optional[str]:
    """Get a variable by name from a sync context"""
    variable = get_variable_by_name(name)
    return variable.value if variable else default


async def aget(name: str, default: str = None) -> Optional[str]:
    """Get a variable by name from an async context"""
    variable = await _get_variable_by_name(name)
    return variable.value if variable else default


async def _get_variable_by_name(name):
    async with get_client() as client:
        variable = await client.read_variable_by_name(name)
        return variable


def get_variable_by_name(name: str):
    variable = from_sync.call_soon_in_loop_thread(
        create_call(_get_variable_by_name, name)
    ).result()

    return variable


class VariablesModule(ModuleType):
    def __getitem__(self, name) -> Optional[str]:
        variable = get_variable_by_name(name)
        return variable.value if variable else None


sys.modules[__name__].__class__ = VariablesModule

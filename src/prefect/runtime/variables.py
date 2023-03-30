import sys
from types import ModuleType
from typing import Any

from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.orchestration import get_client


async def _get_variable_by_name(variable_name):
    async with get_client() as client:
        return await client.read_variable_by_name(variable_name)


def get_variable_by_name(variable_name: str) -> str:
    variable = from_sync.call_soon_in_loop_thread(
        create_call(_get_variable_by_name, variable_name)
    ).result()

    return variable.value if variable else None


class VariablesModule(ModuleType):
    def __getattr__(self, name) -> Any:
        return get_variable_by_name(name.replace("_", "-"))

    def __getitem__(self, name) -> Any:
        return get_variable_by_name(name)

    def get(self, name) -> Any:
        return get_variable_by_name(name)


sys.modules[__name__].__class__ = VariablesModule

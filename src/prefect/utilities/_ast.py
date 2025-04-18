import ast
import math
from typing import TYPE_CHECKING, Literal

import anyio
from typing_extensions import TypeAlias

from prefect.logging.loggers import get_logger
from prefect.settings import get_current_settings
from prefect.utilities.asyncutils import LazySemaphore
from prefect.utilities.filesystem import get_open_file_limit

# Only allow half of the open file limit to be open at once to allow for other
# actors to open files.
OPEN_FILE_SEMAPHORE = LazySemaphore(lambda: math.floor(get_open_file_limit() * 0.5))

# this potentially could be a TypedDict, but you
# need some way to convince the type checker that
# Literal["flow_name", "task_name"] are being provided
DecoratedFnMetadata: TypeAlias = dict[str, str]


async def find_prefect_decorated_functions_in_file(
    path: anyio.Path, decorator_module: str, decorator_name: Literal["flow", "task"]
) -> list[DecoratedFnMetadata]:
    logger = get_logger()
    decorator_name_key = f"{decorator_name}_name"
    decorated_functions: list[DecoratedFnMetadata] = []

    async with OPEN_FILE_SEMAPHORE:
        try:
            async with await anyio.open_file(path) as f:
                try:
                    tree = ast.parse(await f.read())
                except SyntaxError:
                    if get_current_settings().debug_mode:
                        logger.debug(
                            f"Could not parse {path} as a Python file. Skipping."
                        )
                    return decorated_functions
        except Exception as exc:
            if get_current_settings().debug_mode:
                logger.debug(f"Could not open {path}: {exc}. Skipping.")
            return decorated_functions

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            for decorator in node.decorator_list:
                # handles @decorator_name
                is_name_match = (
                    isinstance(decorator, ast.Name) and decorator.id == decorator_name
                )
                # handles @decorator_name()
                is_func_name_match = (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Name)
                    and decorator.func.id == decorator_name
                )
                # handles @decorator_module.decorator_name
                is_module_attribute_match = (
                    isinstance(decorator, ast.Attribute)
                    and isinstance(decorator.value, ast.Name)
                    and decorator.value.id == decorator_module
                    and decorator.attr == decorator_name
                )
                # handles @decorator_module.decorator_name()
                is_module_attribute_func_match = (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == decorator_name
                    and isinstance(decorator.func.value, ast.Name)
                    and decorator.func.value.id == decorator_module
                )
                if is_name_match or is_module_attribute_match:
                    decorated_functions.append(
                        {
                            decorator_name_key: node.name,
                            "function_name": node.name,
                            "filepath": str(path),
                        }
                    )
                if is_func_name_match or is_module_attribute_func_match:
                    name_kwarg_node = None
                    if TYPE_CHECKING:
                        assert isinstance(decorator, ast.Call)
                    for kw in decorator.keywords:
                        if kw.arg == "name":
                            name_kwarg_node = kw
                            break
                    if name_kwarg_node is not None and isinstance(
                        name_kwarg_node.value, ast.Constant
                    ):
                        decorated_fn_name = name_kwarg_node.value.value
                    else:
                        decorated_fn_name = node.name
                    decorated_functions.append(
                        {
                            decorator_name_key: decorated_fn_name,
                            "function_name": node.name,
                            "filepath": str(path),
                        }
                    )
    return decorated_functions


async def find_flow_functions_in_file(path: anyio.Path) -> list[DecoratedFnMetadata]:
    return await find_prefect_decorated_functions_in_file(path, "prefect", "flow")


async def find_task_functions_in_file(path: anyio.Path) -> list[DecoratedFnMetadata]:
    return await find_prefect_decorated_functions_in_file(path, "prefect", "task")

"""
Calls in `src/prefect/` to FastAPI's request parameter functions (`Path`,
`Query`, `Header`, `Cookie`, `Body`, `Form`, `File`, `Security`, `Depends`)
pass only keywords those functions name in their signatures, and never unpack
`**kwargs` into them.

FastAPI before 0.155 accepted unknown keywords, copied them into the OpenAPI
schema, and did not validate them, so `Body(max_items=200)` accepted a list of
any length. FastAPI 0.155 raises `TypeError` on an unknown keyword, so one such
call makes `prefect.server.api` fail to import.
"""

import ast
import importlib
import inspect
from pathlib import Path

import prefect

SRC_DIR = Path(prefect.__file__).parent

PARAM_FUNCTION_NAMES = frozenset(
    {"Path", "Query", "Header", "Cookie", "Body", "Form", "File", "Security", "Depends"}
)
PARAM_FUNCTION_MODULES = frozenset(
    {"fastapi", "fastapi.params", "fastapi.param_functions"}
)

# `src/prefect/` makes about 470 such calls. A scan that finds far fewer has
# stopped resolving imports and would pass without checking anything.
MINIMUM_EXPECTED_CALLS = 280


def _named_keywords(module: str, name: str) -> frozenset[str]:
    signature = inspect.signature(getattr(importlib.import_module(module), name))
    return frozenset(
        parameter.name
        for parameter in signature.parameters.values()
        if parameter.kind is not inspect.Parameter.VAR_KEYWORD
    )


def _param_function_calls(tree: ast.Module) -> list[tuple[ast.Call, str, str]]:
    imported_functions: dict[str, tuple[str, str]] = {}
    fastapi_module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in PARAM_FUNCTION_MODULES:
            for alias in node.names:
                if alias.name in PARAM_FUNCTION_NAMES:
                    imported_functions[alias.asname or alias.name] = (
                        node.module,
                        alias.name,
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "fastapi":
                    fastapi_module_names.add(alias.asname or alias.name)

    calls: list[tuple[ast.Call, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in imported_functions:
            calls.append((node, *imported_functions[node.func.id]))
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in fastapi_module_names
            and node.func.attr in PARAM_FUNCTION_NAMES
        ):
            calls.append((node, "fastapi", node.func.attr))
    return calls


def test_fastapi_param_function_calls_use_only_named_keywords():
    call_count = 0
    violations: list[str] = []
    for py_file in sorted(SRC_DIR.rglob("*.py")):
        location = py_file.relative_to(SRC_DIR.parent)
        for call, module, name in _param_function_calls(ast.parse(py_file.read_text())):
            call_count += 1
            named_keywords = _named_keywords(module, name)
            for keyword in call.keywords:
                if keyword.arg is None:
                    violations.append(
                        f"{location}:{call.lineno}: {module}.{name}(**...) "
                        "unpacks keywords that cannot be checked"
                    )
                elif keyword.arg not in named_keywords:
                    violations.append(
                        f"{location}:{call.lineno}: {module}.{name}() has no "
                        f"parameter named {keyword.arg!r}"
                    )

    assert call_count >= MINIMUM_EXPECTED_CALLS, (
        f"found only {call_count} FastAPI parameter function calls in "
        f"{SRC_DIR}; the scan no longer resolves imports"
    )
    assert not violations, (
        "FastAPI parameter functions called with keywords they do not name "
        "(for example, use max_length= rather than max_items=):\n"
        + "\n".join(violations)
    )

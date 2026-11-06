"""
The MicroVM entrypoint calls private `prefect` engine functions. These tests fail
when one of them is removed or its signature changes.
"""

import inspect
import typing
from uuid import UUID

import prefect.engine
import prefect.flow_engine

POSITIONAL_OR_KEYWORD = inspect.Parameter.POSITIONAL_OR_KEYWORD
NO_DEFAULT = inspect.Parameter.empty


def describe_parameters(
    function: typing.Callable[..., object],
) -> list[tuple[str, object, object, object]]:
    hints = typing.get_type_hints(function)
    return [
        (name, parameter.kind, parameter.default, hints.get(name))
        for name, parameter in inspect.signature(function).parameters.items()
    ]


def test_run_flow_from_runtime_entrypoint_signature():
    function = prefect.flow_engine._run_flow_from_runtime_entrypoint

    assert describe_parameters(function) == [
        ("flow_run_id", POSITIONAL_OR_KEYWORD, NO_DEFAULT, UUID),
        ("entrypoint", POSITIONAL_OR_KEYWORD, NO_DEFAULT, str),
    ]


def test_drive_run_flow_result_signature():
    function = prefect.engine._drive_run_flow_result

    assert [name for name, *_ in describe_parameters(function)] == [
        "flow",
        "run_result",
    ]

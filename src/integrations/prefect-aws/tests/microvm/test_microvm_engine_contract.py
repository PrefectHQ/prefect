"""
The MicroVM entrypoint calls private `prefect` engine functions. These tests fail
when one of them is removed or its signature changes.
"""

import importlib
import inspect
import typing
from uuid import UUID

import pytest

import prefect.engine
import prefect.flow_engine
from prefect._internal.concurrency.services import QueueService
from prefect.events.worker import EventsWorker
from prefect.logging.handlers import APILogWorker

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


@pytest.mark.parametrize("worker", [QueueService, APILogWorker, EventsWorker])
def test_drain_all_accepts_a_timeout(worker: type[QueueService[typing.Any]]):
    parameters = inspect.signature(worker.drain_all).parameters

    assert "timeout" in parameters
    assert parameters["timeout"].kind in (
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    )


@pytest.mark.parametrize(
    "module, name",
    [
        ("prefect.engine", "handle_engine_signals"),
        ("prefect.context", "refresh_global_settings_context"),
        ("prefect._internal.control_listener", "configure_from_env"),
        ("prefect._internal.metrics", "RunMetrics"),
        ("prefect.flow_engine", "load_flow_run"),
        ("prefect.flow_engine", "load_flow"),
        ("prefect.flow_engine", "flow_run_logger"),
        ("prefect.utilities.engine", "propose_state_sync"),
    ],
)
def test_engine_functions_the_entrypoint_calls_import(module: str, name: str):
    assert callable(getattr(importlib.import_module(module), name))

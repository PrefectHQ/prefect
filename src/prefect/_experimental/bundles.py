from __future__ import annotations

import asyncio
import base64
import gzip
import logging
import multiprocessing
import multiprocessing.context
import os
from typing import Any, TypedDict

import cloudpickle

from prefect.client.schemas.objects import FlowRun
from prefect.context import SettingsContext, get_settings_context, serialize_context
from prefect.exceptions import Abort, Pause
from prefect.flow_engine import run_flow
from prefect.flows import Flow
from prefect.settings.context import get_current_settings
from prefect.settings.models.root import Settings


class Bundle(TypedDict):
    serialized_function: str
    serialized_parameters: str
    serialized_context: str
    serialized_flow_run: dict[str, Any]


def _serialize_bundle_object(obj: Any) -> str:
    """
    Serializes an object to a string.
    """
    return base64.b64encode(gzip.compress(cloudpickle.dumps(obj))).decode()


def _deserialize_bundle_object(serialized_obj: str) -> Any:
    """
    Deserializes an object from a string.
    """
    return cloudpickle.loads(gzip.decompress(base64.b64decode(serialized_obj)))


def create_bundle_for_flow_run(
    flow: Flow[Any, Any],
    flow_run: FlowRun,
) -> Bundle:
    context = serialize_context()

    return {
        "serialized_function": _serialize_bundle_object(flow),
        "serialized_parameters": _serialize_bundle_object(flow_run.parameters),
        "serialized_context": _serialize_bundle_object(context),
        "serialized_flow_run": flow_run.model_dump(),
    }


def extract_and_run_flow(bundle: Bundle, env: dict[str, Any] | None = None):
    engine_logger = logging.getLogger("prefect.engine")

    os.environ.update(env or {})
    settings_context = get_settings_context()

    flow = _deserialize_bundle_object(bundle["serialized_function"])
    parameters = _deserialize_bundle_object(bundle["serialized_parameters"])
    context = _deserialize_bundle_object(bundle["serialized_context"])
    flow_run = FlowRun.model_validate(bundle["serialized_flow_run"])

    with SettingsContext(
        profile=settings_context.profile,
        settings=Settings(),
    ):
        try:
            maybe_coro = run_flow(
                flow=flow,
                flow_run=flow_run,
                parameters=parameters,
                context=context,
            )
            if asyncio.iscoroutine(maybe_coro):
                # This is running in a brand new process, so there won't be an existing
                # event loop.
                asyncio.run(maybe_coro)
        except Abort:
            if flow_run:
                msg = f"Execution of flow run '{flow_run.id}' aborted by orchestrator."
            else:
                msg = "Execution aborted by orchestrator."
            engine_logger.info(msg)
            exit(0)
        except Pause:
            if flow_run:
                msg = f"Execution of flow run '{flow_run.id}' is paused."
            else:
                msg = "Execution is paused."
            engine_logger.info(msg)
            exit(0)
        except Exception:
            if flow_run:
                msg = f"Execution of flow run '{flow_run.id}' exited with unexpected exception"
            else:
                msg = "Execution exited with unexpected exception"
            engine_logger.error(msg, exc_info=True)
            exit(1)
        except BaseException:
            if flow_run:
                msg = f"Execution of flow run '{flow_run.id}' interrupted by base exception"
            else:
                msg = "Execution interrupted by base exception"
            engine_logger.error(msg, exc_info=True)
            # Let the exit code be determined by the base exception type
            raise


def execute_bundle_in_subprocess(
    bundle: Bundle,
) -> multiprocessing.context.SpawnProcess:
    """
    Executes a bundle in a subprocess.
    """

    ctx = multiprocessing.get_context("spawn")

    process = ctx.Process(
        target=extract_and_run_flow,
        kwargs={
            "bundle": bundle,
            "env": get_current_settings().to_environment_variables(exclude_unset=True)
            | os.environ
            | {
                # TODO: make this a thing we can pass into the engine
                "PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS": "false",
            },
        },
    )

    process.start()

    return process

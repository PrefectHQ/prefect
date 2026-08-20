from __future__ import annotations

import argparse
import functools
import inspect
import json
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

import anyio

from prefect.client.schemas.objects import FlowRun, State
from prefect.exceptions import MissingFlowError
from prefect.flows import load_flow_from_entrypoint, load_function_and_convert_to_flow
from prefect.logging.loggers import flow_run_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from prefect.flows import Flow


HookType = Literal["cancellation", "crashed"]


def _read_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _absolute_file_entrypoint(manifest: dict[str, Any]) -> str:
    entrypoint = cast(str, manifest["runtime_entrypoint"])
    if ":" not in entrypoint:
        return entrypoint

    path, object_name = entrypoint.rsplit(":", 1)
    if not path.endswith(".py"):
        return entrypoint

    entrypoint_path = Path(path).expanduser()
    if not entrypoint_path.is_absolute():
        entrypoint_path = Path(manifest["working_directory"]) / entrypoint_path
    return f"{entrypoint_path.resolve()}:{object_name}"


async def _load_flow(manifest: dict[str, Any]) -> Flow[Any, Any]:
    entrypoint = _absolute_file_entrypoint(manifest)
    try:
        return await anyio.to_thread.run_sync(
            functools.partial(
                load_flow_from_entrypoint,
                entrypoint,
                use_placeholder_flow=False,
            )
        )
    except MissingFlowError:
        return await anyio.to_thread.run_sync(
            load_function_and_convert_to_flow,
            entrypoint,
        )


async def _run_hooks(
    hooks: list[Callable[..., Any]],
    flow_run: FlowRun,
    flow: Flow[Any, Any],
    state: State,
) -> None:
    logger = flow_run_logger(flow_run, flow)
    for hook in hooks:
        hook_name = getattr(hook, "__name__", type(hook).__name__)
        try:
            result = await anyio.to_thread.run_sync(
                functools.partial(
                    hook,
                    flow=flow,
                    flow_run=flow_run,
                    state=state,
                )
            )
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception(
                "An error was encountered while running hook %r",
                hook_name,
            )


async def execute_hook_subprocess(
    hook_type: HookType,
    manifest_path: Path,
    flow_run_path: Path,
    state_path: Path,
) -> None:
    manifest = _read_manifest(manifest_path)
    flow_run = FlowRun.model_validate_json(flow_run_path.read_text(encoding="utf-8"))
    state = State.model_validate_json(state_path.read_text(encoding="utf-8"))
    flow = await _load_flow(manifest)
    hooks = (
        flow.on_cancellation_hooks
        if hook_type == "cancellation"
        else flow.on_crashed_hooks
    )
    await _run_hooks(hooks or [], flow_run, flow, state)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load a prepared flow and execute its runner-owned hooks."
    )
    parser.add_argument("hook_type", choices=("cancellation", "crashed"))
    parser.add_argument("manifest", type=Path)
    parser.add_argument("flow_run", type=Path)
    parser.add_argument("state", type=Path)
    return parser.parse_args(argv)


async def _main_async(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        await execute_hook_subprocess(
            cast(HookType, args.hook_type),
            args.manifest,
            args.flow_run,
            args.state,
        )
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    return anyio.run(_main_async, argv)


if __name__ == "__main__":
    raise SystemExit(main())

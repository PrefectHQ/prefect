from __future__ import annotations

import argparse
import functools
import inspect
import json
import runpy
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

if TYPE_CHECKING:
    from collections.abc import Callable

    from prefect.client.schemas.objects import FlowRun, State
    from prefect.flows import Flow


HookType = Literal["cancellation", "crashed"]


def _run_engine(entrypoint: str) -> int:
    sys.argv = ["prefect.flow_engine", entrypoint]
    runpy.run_module("prefect.flow_engine", run_name="__main__")
    return 0


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


async def _run_sync(call: Callable[..., Any], *args: Any) -> Any:
    import anyio

    return await anyio.to_thread.run_sync(call, *args)


async def _load_flow(manifest: dict[str, Any]) -> Flow[Any, Any]:
    from prefect.exceptions import MissingFlowError
    from prefect.flows import (
        load_flow_from_entrypoint,
        load_function_and_convert_to_flow,
    )

    entrypoint = _absolute_file_entrypoint(manifest)
    try:
        return await _run_sync(
            functools.partial(
                load_flow_from_entrypoint,
                entrypoint,
                use_placeholder_flow=False,
            )
        )
    except MissingFlowError:
        return await _run_sync(load_function_and_convert_to_flow, entrypoint)


async def _run_hooks(
    hooks: list[Callable[..., Any]],
    flow_run: FlowRun,
    flow: Flow[Any, Any],
    state: State,
) -> None:
    from prefect.logging.loggers import flow_run_logger

    logger = flow_run_logger(flow_run, flow)
    for hook in hooks:
        hook_name = getattr(hook, "__name__", type(hook).__name__)
        try:
            result = await _run_sync(
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


async def _execute_hook(
    hook_type: HookType,
    manifest_path: Path,
    flow_run_path: Path,
    state_path: Path,
) -> None:
    from prefect.client.schemas.objects import FlowRun, State

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
        description="Run a flow engine or hooks in a prepared project runtime."
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)

    engine = subparsers.add_parser("engine")
    engine.add_argument("entrypoint")

    hook = subparsers.add_parser("hook")
    hook.add_argument("hook_type", choices=("cancellation", "crashed"))
    hook.add_argument("manifest", type=Path)
    hook.add_argument("flow_run", type=Path)
    hook.add_argument("state", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.operation == "engine":
            return _run_engine(args.entrypoint)

        import anyio

        anyio.run(
            _execute_hook,
            cast(HookType, args.hook_type),
            args.manifest,
            args.flow_run,
            args.state,
        )
    except Exception:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

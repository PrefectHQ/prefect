from __future__ import annotations

import ast
import asyncio
import base64
import gzip
import importlib
import inspect
import json
import logging
import multiprocessing
import multiprocessing.context
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
import tempfile
from types import ModuleType
from typing import Any, TypedDict

import anyio
import cloudpickle  # pyright: ignore[reportMissingTypeStubs]

from prefect.client.schemas.objects import FlowRun
from prefect.context import SettingsContext, get_settings_context, serialize_context
from prefect.engine import handle_engine_signals
from prefect.flow_engine import run_flow
from prefect.flows import Flow
from prefect.logging import get_logger
from prefect.settings.context import get_current_settings
from prefect.settings.models.root import Settings
from prefect.utilities.slugify import slugify

from .execute import execute_bundle_from_file

logger: logging.Logger = get_logger(__name__)


def _get_uv_path() -> str:
    """
    Get the path to the uv binary.

    First tries to use the uv Python package to find the binary.
    Falls back to "uv" string (assumes uv is in PATH).
    """
    try:
        import uv

        return uv.find_uv_bin()
    except (ImportError, ModuleNotFoundError, FileNotFoundError):
        return "uv"


class SerializedBundle(TypedDict):
    """
    A serialized bundle is a serialized function, context, and flow run that can be
    easily transported for later execution.
    """

    function: str
    context: str
    flow_run: dict[str, Any]
    dependencies: str


def _serialize_bundle_object(obj: Any) -> str:
    """
    Serializes an object to a string.
    """
    return base64.b64encode(gzip.compress(cloudpickle.dumps(obj))).decode()  # pyright: ignore[reportUnknownMemberType]


def _deserialize_bundle_object(serialized_obj: str) -> Any:
    """
    Deserializes an object from a string.
    """
    return cloudpickle.loads(gzip.decompress(base64.b64decode(serialized_obj)))


def _is_local_module(module_name: str, module_path: str | None = None) -> bool:
    """
    Check if a module is a local module (not from standard library or site-packages).

    Args:
        module_name: The name of the module.
        module_path: Optional path to the module file.

    Returns:
        True if the module is a local module, False otherwise.
    """
    # Skip modules that are known to be problematic or not needed
    skip_modules = {
        "__pycache__",
        # Skip test modules
        "unittest",
        "pytest",
        "test_",
        "_pytest",
        # Skip prefect modules - they'll be available on remote
        "prefect",
    }

    # Check module name prefixes
    for skip in skip_modules:
        if module_name.startswith(skip):
            return False

    # Check if it's a built-in module
    if module_name in sys.builtin_module_names:
        return False

    # Check if it's in the standard library (Python 3.10+)
    if hasattr(sys, "stdlib_module_names"):
        # Check both full module name and base module name
        base_module = module_name.split(".")[0]
        if (
            module_name in sys.stdlib_module_names
            or base_module in sys.stdlib_module_names
        ):
            return False

    # If we have the module path, check if it's in site-packages or dist-packages
    if module_path:
        path_str = str(module_path)
        # Also exclude standard library paths
        if (
            "site-packages" in path_str
            or "dist-packages" in path_str
            or "/lib/python" in path_str
            or "/.venv/" in path_str
        ):
            return False
    else:
        # Try to import the module to get its path
        try:
            module = importlib.import_module(module_name)
            if hasattr(module, "__file__") and module.__file__:
                path_str = str(module.__file__)
                if (
                    "site-packages" in path_str
                    or "dist-packages" in path_str
                    or "/lib/python" in path_str
                    or "/.venv/" in path_str
                ):
                    return False
        except (ImportError, AttributeError):
            # If we can't import it, it's probably not a real module
            return False

    # Only consider it local if it exists and we can verify it
    return True


def _extract_imports_from_source(source_code: str) -> set[str]:
    """
    Extract all import statements from Python source code.

    Args:
        source_code: The Python source code to analyze.

    Returns:
        A set of imported module names.
    """
    imports: set[str] = set()

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        logger.debug("Failed to parse source code for import extraction")
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
                # Don't add individual imported items as they might be classes/functions
                # Only track the module itself

    return imports


def _discover_local_dependencies(
    flow: Flow[Any, Any], visited: set[str] | None = None
) -> set[str]:
    """
    Recursively discover local module dependencies of a flow.

    Args:
        flow: The flow to analyze.
        visited: Set of already visited modules to avoid infinite recursion.

    Returns:
        A set of local module names that should be serialized by value.
    """
    if visited is None:
        visited = set()

    local_modules: set[str] = set()

    # Get the module containing the flow
    try:
        flow_module = inspect.getmodule(flow.fn)
    except (AttributeError, TypeError):
        # Flow function doesn't have a module (e.g., defined in REPL)
        return local_modules

    if not flow_module:
        return local_modules

    module_name = flow_module.__name__

    # Process the flow's module and all its dependencies recursively
    _process_module_dependencies(flow_module, module_name, local_modules, visited)

    return local_modules


def _process_module_dependencies(
    module: ModuleType,
    module_name: str,
    local_modules: set[str],
    visited: set[str],
) -> None:
    """
    Recursively process a module and discover its local dependencies.

    Args:
        module: The module to process.
        module_name: The name of the module.
        local_modules: Set to accumulate discovered local modules.
        visited: Set of already visited modules to avoid infinite recursion.
    """
    # Skip if we've already processed this module
    if module_name in visited:
        return
    visited.add(module_name)

    # Check if this is a local module
    module_file = getattr(module, "__file__", None)
    if not module_file or not _is_local_module(module_name, module_file):
        return

    local_modules.add(module_name)

    # Get the source code of the module
    try:
        source_code = inspect.getsource(module)
    except (OSError, TypeError):
        # Can't get source for this module
        return

    imports = _extract_imports_from_source(source_code)

    # Check each import to see if it's local and recursively process it
    for import_name in imports:
        # Skip if already visited
        if import_name in visited:
            continue

        # Try to resolve the import
        imported_module = None
        try:
            # Handle relative imports by resolving them
            if module_name and "." in module_name:
                package = ".".join(module_name.split(".")[:-1])
                try:
                    imported_module = importlib.import_module(import_name, package)
                except ImportError:
                    imported_module = importlib.import_module(import_name)
            else:
                imported_module = importlib.import_module(import_name)
        except (ImportError, AttributeError):
            # Can't import, skip it
            continue

        # Recursively process this imported module
        _process_module_dependencies(
            imported_module, import_name, local_modules, visited
        )


@contextmanager
def _pickle_local_modules_by_value(flow: Flow[Any, Any]):
    """
    Context manager that registers local modules for pickle-by-value serialization.

    Args:
        flow: The flow whose dependencies should be registered.
    """
    registered_modules: list[ModuleType] = []

    try:
        # Discover local dependencies
        local_modules = _discover_local_dependencies(flow)
        logger.debug("Local modules: %s", local_modules)

        if local_modules:
            logger.debug(
                "Registering local modules for pickle-by-value serialization: %s",
                ", ".join(local_modules),
            )

        # Register each local module for pickle-by-value
        for module_name in local_modules:
            try:
                module = importlib.import_module(module_name)
                cloudpickle.register_pickle_by_value(module)  # pyright: ignore[reportUnknownMemberType] Missing stubs
                registered_modules.append(module)
            except (ImportError, AttributeError) as e:
                logger.debug(
                    "Failed to register module %s for pickle-by-value: %s",
                    module_name,
                    e,
                )

        yield

    finally:
        # Unregister all modules we registered
        for module in registered_modules:
            try:
                cloudpickle.unregister_pickle_by_value(module)  # pyright: ignore[reportUnknownMemberType] Missing stubs
            except Exception as e:
                logger.debug(
                    "Failed to unregister module %s from pickle-by-value: %s",
                    getattr(module, "__name__", module),
                    e,
                )


def create_bundle_for_flow_run(
    flow: Flow[Any, Any],
    flow_run: FlowRun,
    context: dict[str, Any] | None = None,
) -> SerializedBundle:
    """
    Creates a bundle for a flow run.

    Args:
        flow: The flow to bundle.
        flow_run: The flow run to bundle.
        context: The context to use when running the flow.

    Returns:
        A serialized bundle.
    """
    context = context or serialize_context()

    dependencies = (
        subprocess.check_output(
            [
                _get_uv_path(),
                "pip",
                "freeze",
                # Exclude editable installs because we won't be able to install them in the execution environment
                "--exclude-editable",
            ]
        )
        .decode()
        .strip()
    )

    # Remove dependencies installed from a local file path because we won't be able
    # to install them in the execution environment. The user will be responsible for
    # making sure they are available in the execution environment
    filtered_dependencies: list[str] = []
    file_dependencies: list[str] = []
    for line in dependencies.split("\n"):
        if "file://" in line:
            file_dependencies.append(line)
        else:
            filtered_dependencies.append(line)
    dependencies = "\n".join(filtered_dependencies)
    if file_dependencies:
        logger.warning(
            "The following dependencies were installed from a local file path and will not be "
            "automatically installed in the execution environment: %s. If these dependencies "
            "are not available in the execution environment, your flow run may fail.",
            "\n".join(file_dependencies),
        )

    # Automatically register local modules for pickle-by-value serialization
    with _pickle_local_modules_by_value(flow):
        return {
            "function": _serialize_bundle_object(flow),
            "context": _serialize_bundle_object(context),
            "flow_run": flow_run.model_dump(mode="json"),
            "dependencies": dependencies,
        }


def extract_flow_from_bundle(bundle: SerializedBundle) -> Flow[Any, Any]:
    """
    Extracts a flow from a bundle.
    """
    return _deserialize_bundle_object(bundle["function"])


def _extract_and_run_flow(
    bundle: SerializedBundle,
    cwd: Path | str | None = None,
    env: dict[str, Any] | None = None,
) -> None:
    """
    Extracts a flow from a bundle and runs it.

    Designed to be run in a subprocess.

    Args:
        bundle: The bundle to extract and run.
        cwd: The working directory to use when running the flow.
        env: The environment to use when running the flow.
    """

    os.environ.update(env or {})
    # TODO: make this a thing we can pass directly to the engine
    os.environ["PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS"] = "false"
    settings_context = get_settings_context()

    flow = _deserialize_bundle_object(bundle["function"])
    context = _deserialize_bundle_object(bundle["context"])
    flow_run = FlowRun.model_validate(bundle["flow_run"])

    if cwd:
        os.chdir(cwd)

    with SettingsContext(
        profile=settings_context.profile,
        settings=Settings(),
    ):
        with handle_engine_signals(flow_run.id):
            maybe_coro = run_flow(
                flow=flow,
                flow_run=flow_run,
                context=context,
            )
            if asyncio.iscoroutine(maybe_coro):
                # This is running in a brand new process, so there won't be an existing
                # event loop.
                asyncio.run(maybe_coro)


def execute_bundle_in_subprocess(
    bundle: SerializedBundle,
    env: dict[str, Any] | None = None,
    cwd: Path | str | None = None,
) -> multiprocessing.context.SpawnProcess:
    """
    Executes a bundle in a subprocess.

    Args:
        bundle: The bundle to execute.

    Returns:
        A multiprocessing.context.SpawnProcess.
    """

    ctx = multiprocessing.get_context("spawn")
    env = env or {}

    # Install dependencies if necessary
    if dependencies := bundle.get("dependencies"):
        subprocess.check_call(
            [_get_uv_path(), "pip", "install", *dependencies.split("\n")],
            # Copy the current environment to ensure we install into the correct venv
            env=os.environ,
        )

    process = ctx.Process(
        target=_extract_and_run_flow,
        kwargs={
            "bundle": bundle,
            "env": get_current_settings().to_environment_variables(exclude_unset=True)
            | os.environ
            | env,
            "cwd": cwd,
        },
    )

    process.start()

    return process


def convert_step_to_command(
    step: dict[str, Any], key: str, quiet: bool = False
) -> list[str]:
    """
    Converts a bundle upload or execution step to a command.

    Args:
        step: The step to convert.
        key: The key to use for the remote file when downloading or uploading.
        quiet: Whether to suppress `uv` output from the command.

    Returns:
        A list of strings representing the command to run the step.
    """
    # Start with uv run
    command = ["uv", "run"]

    if quiet:
        command.append("--quiet")

    step_keys = list(step.keys())

    if len(step_keys) != 1:
        raise ValueError("Expected exactly one function in step")

    function_fqn = step_keys[0]
    function_args = step[function_fqn]

    # Add the `--with` argument to handle dependencies for running the step
    requires: list[str] | str = function_args.get("requires", [])
    if isinstance(requires, str):
        requires = [requires]
    if requires:
        command.extend(["--with", ",".join(requires)])

    # Add the `--python` argument to handle the Python version for running the step
    python_version = sys.version_info
    command.extend(["--python", f"{python_version.major}.{python_version.minor}"])

    # Add the `-m` argument to defined the function to run
    command.extend(["-m", function_fqn])

    # Add any arguments with values defined in the step
    for arg_name, arg_value in function_args.items():
        if arg_name == "requires":
            continue

        command.extend([f"--{slugify(arg_name)}", arg_value])

    # Add the `--key` argument to specify the remote file name
    command.extend(["--key", key])

    return command


def upload_bundle_to_storage(
    bundle: SerializedBundle, key: str, upload_command: list[str]
) -> None:
    """
    Uploads a bundle to storage.

    Args:
        bundle: The serialized bundle to upload.
        key: The key to use for the remote file when uploading.
        upload_command: The command to use to upload the bundle as a list of strings.
    """
    # Write the bundle to a temporary directory so it can be uploaded to the bundle storage
    # via the upload command
    with tempfile.TemporaryDirectory() as temp_dir:
        Path(temp_dir).joinpath(key).write_bytes(json.dumps(bundle).encode("utf-8"))

        try:
            full_command = upload_command + [key]
            logger.debug("Uploading execution bundle with command: %s", full_command)
            subprocess.check_call(
                full_command,
                cwd=temp_dir,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(e.stderr.decode("utf-8")) from e


async def aupload_bundle_to_storage(
    bundle: SerializedBundle, key: str, upload_command: list[str]
) -> None:
    """
    Asynchronously uploads a bundle to storage.

    Args:
        bundle: The serialized bundle to upload.
        key: The key to use for the remote file when uploading.
        upload_command: The command to use to upload the bundle as a list of strings.
    """
    # Write the bundle to a temporary directory so it can be uploaded to the bundle storage
    # via the upload command
    with tempfile.TemporaryDirectory() as temp_dir:
        await (
            anyio.Path(temp_dir)
            .joinpath(key)
            .write_bytes(json.dumps(bundle).encode("utf-8"))
        )

        try:
            full_command = upload_command + [key]
            logger.debug("Uploading execution bundle with command: %s", full_command)
            await anyio.run_process(
                full_command,
                cwd=temp_dir,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(e.stderr.decode("utf-8")) from e


__all__ = [
    "execute_bundle_from_file",
    "convert_step_to_command",
    "create_bundle_for_flow_run",
    "extract_flow_from_bundle",
    "execute_bundle_in_subprocess",
    "SerializedBundle",
]

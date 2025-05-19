"""
Module containing the base workflow class and decorator - for most use cases, using the [`@flow` decorator][prefect.flows.flow] is preferred.
"""

from __future__ import annotations

# This file requires type-checking with pyright because mypy does not yet support PEP612
# See https://github.com/python/mypy/issues/8645
import ast
import asyncio
import datetime
import importlib.util
import inspect
import os
import re
import sys
import tempfile
import warnings
from copy import copy
from functools import partial, update_wrapper
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Generic,
    Iterable,
    List,
    NoReturn,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import UUID

import pydantic
from exceptiongroup import BaseExceptionGroup, ExceptionGroup
from pydantic.v1 import BaseModel as V1BaseModel
from pydantic.v1.decorator import ValidatedFunction as V1ValidatedFunction
from pydantic.v1.errors import ConfigError  # TODO
from rich.console import Console
from typing_extensions import Literal, ParamSpec

from prefect._experimental.sla.objects import SlaTypes
from prefect._internal.concurrency.api import create_call, from_async
from prefect._versioning import VersionType
from prefect.blocks.core import Block
from prefect.client.schemas.filters import WorkerFilter, WorkerFilterStatus
from prefect.client.schemas.objects import ConcurrencyLimitConfig, FlowRun
from prefect.client.utilities import client_injector
from prefect.docker.docker_image import DockerImage
from prefect.events import DeploymentTriggerTypes, TriggerTypes
from prefect.exceptions import (
    InvalidNameError,
    MissingFlowError,
    ObjectNotFound,
    ParameterTypeError,
    ScriptError,
    TerminationSignal,
    UnspecifiedFlowError,
)
from prefect.filesystems import LocalFileSystem, ReadableDeploymentStorage
from prefect.futures import PrefectFlowRunFuture, PrefectFuture
from prefect.logging import get_logger
from prefect.logging.loggers import flow_run_logger
from prefect.results import ResultSerializer, ResultStorage
from prefect.schedules import Schedule
from prefect.settings import (
    PREFECT_DEFAULT_WORK_POOL_NAME,
    PREFECT_FLOW_DEFAULT_RETRIES,
    PREFECT_FLOW_DEFAULT_RETRY_DELAY_SECONDS,
    PREFECT_TESTING_UNIT_TEST_MODE,
    PREFECT_UI_URL,
)
from prefect.states import State
from prefect.task_runners import TaskRunner, ThreadPoolTaskRunner
from prefect.types import BANNED_CHARACTERS, WITHOUT_BANNED_CHARACTERS
from prefect.types.entrypoint import EntrypointType
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import (
    run_coro_as_sync,
    run_sync_in_worker_thread,
    sync_compatible,
)
from prefect.utilities.callables import (
    ParameterSchema,
    get_call_parameters,
    parameter_schema,
    parameters_to_args_kwargs,
    raise_for_reserved_arguments,
)
from prefect.utilities.collections import listrepr, visit_collection
from prefect.utilities.filesystem import relative_path_to_current_platform
from prefect.utilities.hashing import file_hash
from prefect.utilities.importtools import import_object, safe_load_namespace

from ._internal.compatibility.async_dispatch import async_dispatch, is_in_async_context
from ._internal.pydantic.v2_schema import is_v2_type
from ._internal.pydantic.v2_validated_func import V2ValidatedFunction
from ._internal.pydantic.v2_validated_func import (
    V2ValidatedFunction as ValidatedFunction,
)

if TYPE_CHECKING:
    from prefect.workers.base import BaseWorker

T = TypeVar("T")  # Generic type var for capturing the inner return type of async funcs
R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")  # The parameters of the flow
F = TypeVar("F", bound="Flow[Any, Any]")  # The type of the flow


class FlowStateHook(Protocol, Generic[P, R]):
    """
    A callable that is invoked when a flow enters a given state.
    """

    __name__: str

    def __call__(
        self, flow: Flow[P, R], flow_run: FlowRun, state: State
    ) -> Awaitable[None] | None: ...


if TYPE_CHECKING:
    import logging

    from prefect.client.orchestration import PrefectClient
    from prefect.client.schemas.objects import FlowRun
    from prefect.client.types.flexible_schedule_list import FlexibleScheduleList
    from prefect.deployments.runner import RunnerDeployment
    from prefect.runner.storage import RunnerStorage

logger: "logging.Logger" = get_logger("flows")


class Flow(Generic[P, R]):
    """
    A Prefect workflow definition.

    !!! note
        We recommend using the [`@flow` decorator][prefect.flows.flow] for most use-cases.

    Wraps a function with an entrypoint to the Prefect engine. To preserve the input
    and output types, we use the generic type variables `P` and `R` for "Parameters" and
    "Returns" respectively.

    Args:
        fn: The function defining the workflow.
        name: An optional name for the flow; if not provided, the name will be inferred
            from the given function.
        version: An optional version string for the flow; if not provided, we will
            attempt to create a version string as a hash of the file containing the
            wrapped function; if the file cannot be located, the version will be null.
        flow_run_name: An optional name to distinguish runs of this flow; this name can
            be provided as a string template with the flow's parameters as variables,
            or a function that returns a string.
        task_runner: An optional task runner to use for task execution within the flow;
            if not provided, a `ThreadPoolTaskRunner` will be used.
        description: An optional string description for the flow; if not provided, the
            description will be pulled from the docstring for the decorated function.
        timeout_seconds: An optional number of seconds indicating a maximum runtime for
            the flow. If the flow exceeds this runtime, it will be marked as failed.
            Flow execution may continue until the next task is called.
        validate_parameters: By default, parameters passed to flows are validated by
            Pydantic. This will check that input values conform to the annotated types
            on the function. Where possible, values will be coerced into the correct
            type; for example, if a parameter is defined as `x: int` and "5" is passed,
            it will be resolved to `5`. If set to `False`, no validation will be
            performed on flow parameters.
        retries: An optional number of times to retry on flow run failure.
        retry_delay_seconds: An optional number of seconds to wait before retrying the
            flow after failure. This is only applicable if `retries` is nonzero.
        persist_result: An optional toggle indicating whether the result of this flow
            should be persisted to result storage. Defaults to `None`, which indicates
            that Prefect should choose whether the result should be persisted depending on
            the features being used.
        result_storage: An optional block to use to persist the result of this flow.
            This value will be used as the default for any tasks in this flow.
            If not provided, the local file system will be used unless called as
            a subflow, at which point the default will be loaded from the parent flow.
        result_serializer: An optional serializer to use to serialize the result of this
            flow for persistence. This value will be used as the default for any tasks
            in this flow. If not provided, the value of `PREFECT_RESULTS_DEFAULT_SERIALIZER`
            will be used unless called as a subflow, at which point the default will be
            loaded from the parent flow.
        on_failure: An optional list of callables to run when the flow enters a failed state.
        on_completion: An optional list of callables to run when the flow enters a completed state.
        on_cancellation: An optional list of callables to run when the flow enters a cancelling state.
        on_crashed: An optional list of callables to run when the flow enters a crashed state.
        on_running: An optional list of callables to run when the flow enters a running state.
    """

    # NOTE: These parameters (types, defaults, and docstrings) should be duplicated
    #       exactly in the @flow decorator
    def __init__(
        self,
        fn: Callable[P, R] | "classmethod[Any, P, R]" | "staticmethod[P, R]",
        name: Optional[str] = None,
        version: Optional[str] = None,
        flow_run_name: Optional[Union[Callable[[], str], str]] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[Union[int, float]] = None,
        task_runner: Union[
            Type[TaskRunner[PrefectFuture[Any]]], TaskRunner[PrefectFuture[Any]], None
        ] = None,
        description: Optional[str] = None,
        timeout_seconds: Union[int, float, None] = None,
        validate_parameters: bool = True,
        persist_result: Optional[bool] = None,
        result_storage: Optional[Union[ResultStorage, str]] = None,
        result_serializer: Optional[ResultSerializer] = None,
        cache_result_in_memory: bool = True,
        log_prints: Optional[bool] = None,
        on_completion: Optional[list[FlowStateHook[P, R]]] = None,
        on_failure: Optional[list[FlowStateHook[P, R]]] = None,
        on_cancellation: Optional[list[FlowStateHook[P, R]]] = None,
        on_crashed: Optional[list[FlowStateHook[P, R]]] = None,
        on_running: Optional[list[FlowStateHook[P, R]]] = None,
    ):
        if name is not None and not isinstance(name, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(
                "Expected string for flow parameter 'name'; got {} instead. {}".format(
                    type(name).__name__,
                    (
                        "Perhaps you meant to call it? e.g."
                        " '@flow(name=get_flow_run_name())'"
                        if callable(name)
                        else ""
                    ),
                )
            )

        # Validate if hook passed is list and contains callables
        hook_categories = [
            on_completion,
            on_failure,
            on_cancellation,
            on_crashed,
            on_running,
        ]
        hook_names = [
            "on_completion",
            "on_failure",
            "on_cancellation",
            "on_crashed",
            "on_running",
        ]
        for hooks, hook_name in zip(hook_categories, hook_names):
            if hooks is not None:
                try:
                    hooks = list(hooks)
                except TypeError:
                    raise TypeError(
                        f"Expected iterable for '{hook_name}'; got"
                        f" {type(hooks).__name__} instead. Please provide a list of"
                        f" hooks to '{hook_name}':\n\n"
                        f"@flow({hook_name}=[hook1, hook2])\ndef"
                        " my_flow():\n\tpass"
                    )

                for hook in hooks:
                    if not callable(hook):
                        raise TypeError(
                            f"Expected callables in '{hook_name}'; got"
                            f" {type(hook).__name__} instead. Please provide a list of"
                            f" hooks to '{hook_name}':\n\n"
                            f"@flow({hook_name}=[hook1, hook2])\ndef"
                            " my_flow():\n\tpass"
                        )

        if isinstance(fn, classmethod):
            fn = cast(Callable[P, R], fn.__func__)
            self._isclassmethod = True

        if isinstance(fn, staticmethod):
            fn = cast(Callable[P, R], fn.__func__)
            self._isstaticmethod = True

        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name: str = name or fn.__name__.replace("_", "-").replace(
            "<lambda>",
            "unknown-lambda",  # prefect API will not accept "<" or ">" in flow names
        )
        _raise_on_name_with_banned_characters(self.name)

        if flow_run_name is not None:
            if not isinstance(flow_run_name, str) and not callable(flow_run_name):
                raise TypeError(
                    "Expected string or callable for 'flow_run_name'; got"
                    f" {type(flow_run_name).__name__} instead."
                )
        self.flow_run_name = flow_run_name

        if task_runner is None:
            self.task_runner: TaskRunner[PrefectFuture[Any]] = cast(
                TaskRunner[PrefectFuture[Any]], ThreadPoolTaskRunner()
            )
        else:
            self.task_runner: TaskRunner[PrefectFuture[Any]] = (
                task_runner() if isinstance(task_runner, type) else task_runner
            )

        self.log_prints = log_prints

        self.description: str | None = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn

        # the flow is considered async if its function is async or an async
        # generator
        self.isasync: bool = asyncio.iscoroutinefunction(
            self.fn
        ) or inspect.isasyncgenfunction(self.fn)

        # the flow is considered a generator if its function is a generator or
        # an async generator
        self.isgenerator: bool = inspect.isgeneratorfunction(
            self.fn
        ) or inspect.isasyncgenfunction(self.fn)

        raise_for_reserved_arguments(self.fn, ["return_state", "wait_for"])

        # Version defaults to a hash of the function's file
        if not version:
            try:
                flow_file = inspect.getsourcefile(self.fn)
                if flow_file is None:
                    raise FileNotFoundError
                version = file_hash(flow_file)
            except (FileNotFoundError, TypeError, OSError):
                pass  # `getsourcefile` can return null values and "<stdin>" for objects in repls
        self.version = version

        self.timeout_seconds: float | None = (
            float(timeout_seconds) if timeout_seconds else None
        )

        # FlowRunPolicy settings
        # TODO: We can instantiate a `FlowRunPolicy` and add Pydantic bound checks to
        #       validate that the user passes positive numbers here
        self.retries: int = (
            retries if retries is not None else PREFECT_FLOW_DEFAULT_RETRIES.value()
        )

        self.retry_delay_seconds: float | int = (
            retry_delay_seconds
            if retry_delay_seconds is not None
            else PREFECT_FLOW_DEFAULT_RETRY_DELAY_SECONDS.value()
        )

        self.parameters: ParameterSchema = parameter_schema(self.fn)
        self.should_validate_parameters = validate_parameters

        if self.should_validate_parameters:
            # Try to create the validated function now so that incompatibility can be
            # raised at declaration time rather than at runtime
            # We cannot, however, store the validated function on the flow because it
            # is not picklable in some environments
            try:
                ValidatedFunction(self.fn, config={"arbitrary_types_allowed": True})
            except ConfigError as exc:
                raise ValueError(
                    "Flow function is not compatible with `validate_parameters`. "
                    "Disable validation or change the argument names."
                ) from exc

        # result persistence settings
        if persist_result is None:
            if result_storage is not None or result_serializer is not None:
                persist_result = True

        self.persist_result = persist_result
        if result_storage and not isinstance(result_storage, str):
            if getattr(result_storage, "_block_document_id", None) is None:
                raise TypeError(
                    "Result storage configuration must be persisted server-side."
                    " Please call `.save()` on your block before passing it in."
                )
        self.result_storage = result_storage
        self.result_serializer = result_serializer
        self.cache_result_in_memory = cache_result_in_memory
        self.on_completion_hooks: list[FlowStateHook[P, R]] = on_completion or []
        self.on_failure_hooks: list[FlowStateHook[P, R]] = on_failure or []
        self.on_cancellation_hooks: list[FlowStateHook[P, R]] = on_cancellation or []
        self.on_crashed_hooks: list[FlowStateHook[P, R]] = on_crashed or []
        self.on_running_hooks: list[FlowStateHook[P, R]] = on_running or []

        # Used for flows loaded from remote storage
        self._storage: Optional["RunnerStorage"] = None
        self._entrypoint: Optional[str] = None

        module = fn.__module__
        if module and (module == "__main__" or module.startswith("__prefect_loader_")):
            module_name = inspect.getfile(fn)
            module = module_name if module_name != "__main__" else module

        self._entrypoint = f"{module}:{getattr(fn, '__qualname__', fn.__name__)}"

    @property
    def ismethod(self) -> bool:
        return hasattr(self.fn, "__prefect_self__")

    @property
    def isclassmethod(self) -> bool:
        return getattr(self, "_isclassmethod", False)

    @property
    def isstaticmethod(self) -> bool:
        return getattr(self, "_isstaticmethod", False)

    def __get__(self, instance: Any, owner: Any) -> "Flow[P, R]":
        """
        Implement the descriptor protocol so that the flow can be used as an instance or class method.
        When an instance method is loaded, this method is called with the "self" instance as
        an argument. We return a copy of the flow with that instance bound to the flow's function.
        """
        # wrapped function is a classmethod
        if self.isclassmethod:
            bound_task = copy(self)
            setattr(bound_task.fn, "__prefect_cls__", owner)
            return bound_task

        # if the task is being accessed on an instance, bind the instance to the __prefect_self__ attribute
        # of the task's function. This will allow it to be automatically added to the task's parameters
        if instance:
            bound_task = copy(self)
            bound_task.fn.__prefect_self__ = instance  # type: ignore[attr-defined]
            return bound_task

        return self

    def with_options(
        self,
        *,
        name: Optional[str] = None,
        version: Optional[str] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[Union[int, float]] = None,
        description: Optional[str] = None,
        flow_run_name: Optional[Union[Callable[[], str], str]] = None,
        task_runner: Union[
            Type[TaskRunner[PrefectFuture[Any]]], TaskRunner[PrefectFuture[Any]], None
        ] = None,
        timeout_seconds: Union[int, float, None] = None,
        validate_parameters: Optional[bool] = None,
        persist_result: Optional[bool] = NotSet,  # type: ignore
        result_storage: Optional[ResultStorage] = NotSet,  # type: ignore
        result_serializer: Optional[ResultSerializer] = NotSet,  # type: ignore
        cache_result_in_memory: Optional[bool] = None,
        log_prints: Optional[bool] = NotSet,  # type: ignore
        on_completion: Optional[list[FlowStateHook[P, R]]] = None,
        on_failure: Optional[list[FlowStateHook[P, R]]] = None,
        on_cancellation: Optional[list[FlowStateHook[P, R]]] = None,
        on_crashed: Optional[list[FlowStateHook[P, R]]] = None,
        on_running: Optional[list[FlowStateHook[P, R]]] = None,
    ) -> "Flow[P, R]":
        """
        Create a new flow from the current object, updating provided options.

        Args:
            name: A new name for the flow.
            version: A new version for the flow.
            description: A new description for the flow.
            flow_run_name: An optional name to distinguish runs of this flow; this name
                can be provided as a string template with the flow's parameters as variables,
                or a function that returns a string.
            task_runner: A new task runner for the flow.
            timeout_seconds: A new number of seconds to fail the flow after if still
                running.
            validate_parameters: A new value indicating if flow calls should validate
                given parameters.
            retries: A new number of times to retry on flow run failure.
            retry_delay_seconds: A new number of seconds to wait before retrying the
                flow after failure. This is only applicable if `retries` is nonzero.
            persist_result: A new option for enabling or disabling result persistence.
            result_storage: A new storage type to use for results.
            result_serializer: A new serializer to use for results.
            cache_result_in_memory: A new value indicating if the flow's result should
                be cached in memory.
            on_failure: A new list of callables to run when the flow enters a failed state.
            on_completion: A new list of callables to run when the flow enters a completed state.
            on_cancellation: A new list of callables to run when the flow enters a cancelling state.
            on_crashed: A new list of callables to run when the flow enters a crashed state.
            on_running: A new list of callables to run when the flow enters a running state.

        Returns:
            A new `Flow` instance.

        Examples:

            Create a new flow from an existing flow and update the name:

            >>> @flow(name="My flow")
            >>> def my_flow():
            >>>     return 1
            >>>
            >>> new_flow = my_flow.with_options(name="My new flow")

            Create a new flow from an existing flow, update the task runner, and call
            it without an intermediate variable:

            >>> from prefect.task_runners import ThreadPoolTaskRunner
            >>>
            >>> @flow
            >>> def my_flow(x, y):
            >>>     return x + y
            >>>
            >>> state = my_flow.with_options(task_runner=ThreadPoolTaskRunner)(1, 3)
            >>> assert state.result() == 4
        """
        new_task_runner = (
            task_runner() if isinstance(task_runner, type) else task_runner
        )
        if new_task_runner is None:
            new_task_runner = self.task_runner
        new_flow = Flow(
            fn=self.fn,
            name=name or self.name,
            description=description or self.description,
            flow_run_name=flow_run_name or self.flow_run_name,
            version=version or self.version,
            task_runner=new_task_runner,
            retries=retries if retries is not None else self.retries,
            retry_delay_seconds=(
                retry_delay_seconds
                if retry_delay_seconds is not None
                else self.retry_delay_seconds
            ),
            timeout_seconds=(
                timeout_seconds if timeout_seconds is not None else self.timeout_seconds
            ),
            validate_parameters=(
                validate_parameters
                if validate_parameters is not None
                else self.should_validate_parameters
            ),
            persist_result=(
                persist_result if persist_result is not NotSet else self.persist_result
            ),
            result_storage=(
                result_storage if result_storage is not NotSet else self.result_storage
            ),
            result_serializer=(
                result_serializer
                if result_serializer is not NotSet
                else self.result_serializer
            ),
            cache_result_in_memory=(
                cache_result_in_memory
                if cache_result_in_memory is not None
                else self.cache_result_in_memory
            ),
            log_prints=log_prints if log_prints is not NotSet else self.log_prints,
            on_completion=on_completion or self.on_completion_hooks,
            on_failure=on_failure or self.on_failure_hooks,
            on_cancellation=on_cancellation or self.on_cancellation_hooks,
            on_crashed=on_crashed or self.on_crashed_hooks,
            on_running=on_running or self.on_running_hooks,
        )
        new_flow._storage = self._storage
        new_flow._entrypoint = self._entrypoint
        return new_flow

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Validate parameters for compatibility with the flow by attempting to cast the inputs to the
        associated types specified by the function's type annotations.

        Returns:
            A new dict of parameters that have been cast to the appropriate types

        Raises:
            ParameterTypeError: if the provided parameters are not valid
        """

        def resolve_block_reference(data: Any | dict[str, Any]) -> Any:
            if isinstance(data, dict) and "$ref" in data:
                return Block.load_from_ref(data["$ref"], _sync=True)
            return data

        try:
            parameters = visit_collection(
                parameters, resolve_block_reference, return_data=True
            )
        except (ValueError, RuntimeError) as exc:
            raise ParameterTypeError(
                "Failed to resolve block references in parameters."
            ) from exc

        args, kwargs = parameters_to_args_kwargs(self.fn, parameters)

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", category=pydantic.warnings.PydanticDeprecatedSince20
            )
            has_v1_models = any(isinstance(o, V1BaseModel) for o in args) or any(
                isinstance(o, V1BaseModel) for o in kwargs.values()
            )

        has_v2_types = any(is_v2_type(o) for o in args) or any(
            is_v2_type(o) for o in kwargs.values()
        )

        if has_v1_models and has_v2_types:
            raise ParameterTypeError(
                "Cannot mix Pydantic v1 and v2 types as arguments to a flow."
            )

        validated_fn_kwargs = dict(arbitrary_types_allowed=True)

        if has_v1_models:
            validated_fn = V1ValidatedFunction(self.fn, config=validated_fn_kwargs)
        else:
            validated_fn = V2ValidatedFunction(self.fn, config=validated_fn_kwargs)

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=pydantic.warnings.PydanticDeprecatedSince20
                )
                model = validated_fn.init_model_instance(*args, **kwargs)
        except pydantic.ValidationError as exc:
            # We capture the pydantic exception and raise our own because the pydantic
            # exception is not picklable when using a cythonized pydantic installation
            logger.error(
                f"Parameter validation failed for flow {self.name!r}: {exc.errors()}"
                f"\nParameters: {parameters}"
            )
            raise ParameterTypeError.from_validation_error(exc) from None

        # Get the updated parameter dict with cast values from the model
        cast_parameters = {
            k: v
            for k, v in dict(iter(model)).items()
            if k in model.model_fields_set
            or type(model).model_fields[k].default_factory
        }
        return cast_parameters

    def serialize_parameters(
        self, parameters: dict[str, Any | PrefectFuture[Any] | State]
    ) -> dict[str, Any]:
        """
        Convert parameters to a serializable form.

        Uses FastAPI's `jsonable_encoder` to convert to JSON compatible objects without
        converting everything directly to a string. This maintains basic types like
        integers during API roundtrips.
        """
        serialized_parameters: dict[str, Any] = {}
        for key, value in parameters.items():
            # do not serialize the bound self object
            if self.ismethod and value is getattr(self.fn, "__prefect_self__", None):
                continue
            if self.isclassmethod and value is getattr(
                self.fn, "__prefect_cls__", None
            ):
                continue
            if isinstance(value, (PrefectFuture, State)):
                # Don't call jsonable_encoder() on a PrefectFuture or State to
                # avoid triggering a __getitem__ call
                serialized_parameters[key] = f"<{type(value).__name__}>"
                continue
            try:
                from fastapi.encoders import jsonable_encoder

                serialized_parameters[key] = jsonable_encoder(value)
            except (TypeError, ValueError):
                logger.debug(
                    f"Parameter {key!r} for flow {self.name!r} is unserializable. "
                    f"Type {type(value).__name__!r} and will not be stored "
                    "in the backend."
                )
                serialized_parameters[key] = f"<{type(value).__name__}>"
        return serialized_parameters

    async def ato_deployment(
        self,
        name: str,
        interval: Optional[
            Union[
                Iterable[Union[int, float, datetime.timedelta]],
                int,
                float,
                datetime.timedelta,
            ]
        ] = None,
        cron: Optional[Union[Iterable[str], str]] = None,
        rrule: Optional[Union[Iterable[str], str]] = None,
        paused: Optional[bool] = None,
        schedule: Optional[Schedule] = None,
        schedules: Optional["FlexibleScheduleList"] = None,
        concurrency_limit: Optional[Union[int, ConcurrencyLimitConfig, None]] = None,
        parameters: Optional[dict[str, Any]] = None,
        triggers: Optional[list[Union[DeploymentTriggerTypes, TriggerTypes]]] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        version: Optional[str] = None,
        version_type: Optional[VersionType] = None,
        enforce_parameter_schema: bool = True,
        work_pool_name: Optional[str] = None,
        work_queue_name: Optional[str] = None,
        job_variables: Optional[dict[str, Any]] = None,
        entrypoint_type: EntrypointType = EntrypointType.FILE_PATH,
        _sla: Optional[Union[SlaTypes, list[SlaTypes]]] = None,  # experimental
    ) -> "RunnerDeployment":
        """
        Asynchronously creates a runner deployment object for this flow.

        Args:
            name: The name to give the created deployment.
            interval: An interval on which to execute the new deployment. Accepts either a number
                or a timedelta object. If a number is given, it will be interpreted as seconds.
            cron: A cron schedule of when to execute runs of this deployment.
            rrule: An rrule schedule of when to execute runs of this deployment.
            paused: Whether or not to set this deployment as paused.
            schedule: A schedule object defining when to execute runs of this deployment.
                Used to provide additional scheduling options like `timezone` or `parameters`.
            schedules: A list of schedule objects defining when to execute runs of this deployment.
                Used to define multiple schedules or additional scheduling options such as `timezone`.
            concurrency_limit: The maximum number of runs of this deployment that can run at the same time.
            parameters: A dictionary of default parameter values to pass to runs of this deployment.
            triggers: A list of triggers that will kick off runs of this deployment.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            version_type: The type of version to use for the created deployment. The version type
                will be inferred if not provided.
            enforce_parameter_schema: Whether or not the Prefect API should enforce the
                parameter schema for the created deployment.
            work_pool_name: The name of the work pool to use for this deployment.
            work_queue_name: The name of the work queue to use for this deployment's scheduled runs.
                If not provided the default work queue for the work pool will be used.
            job_variables: Settings used to override the values specified default base job template
                of the chosen work pool. Refer to the base job template of the chosen work pool for
            entrypoint_type: Type of entrypoint to use for the deployment. When using a module path
                entrypoint, ensure that the module will be importable in the execution environment.
            _sla: (Experimental) SLA configuration for the deployment. May be removed or modified at any time. Currently only supported on Prefect Cloud.

        Examples:
            Prepare two deployments and serve them:

            ```python
            from prefect import flow, serve

            @flow
            def my_flow(name):
                print(f"hello {name}")

            @flow
            def my_other_flow(name):
                print(f"goodbye {name}")

            if __name__ == "__main__":
                hello_deploy = my_flow.to_deployment("hello", tags=["dev"])
                bye_deploy = my_other_flow.to_deployment("goodbye", tags=["dev"])
                serve(hello_deploy, bye_deploy)
            ```
        """
        from prefect.deployments.runner import RunnerDeployment

        if not name.endswith(".py"):
            _raise_on_name_with_banned_characters(name)

        if self._storage and self._entrypoint:
            return await RunnerDeployment.afrom_storage(
                storage=self._storage,
                entrypoint=self._entrypoint,
                name=name,
                flow_name=self.name,
                interval=interval,
                cron=cron,
                rrule=rrule,
                paused=paused,
                schedule=schedule,
                schedules=schedules,
                concurrency_limit=concurrency_limit,
                tags=tags,
                triggers=triggers,
                parameters=parameters or {},
                description=description,
                version=version,
                version_type=version_type,
                enforce_parameter_schema=enforce_parameter_schema,
                work_pool_name=work_pool_name,
                work_queue_name=work_queue_name,
                job_variables=job_variables,
                _sla=_sla,
            )
        else:
            return RunnerDeployment.from_flow(
                flow=self,
                name=name,
                interval=interval,
                cron=cron,
                rrule=rrule,
                paused=paused,
                schedule=schedule,
                schedules=schedules,
                concurrency_limit=concurrency_limit,
                tags=tags,
                triggers=triggers,
                parameters=parameters or {},
                description=description,
                version=version,
                version_type=version_type,
                enforce_parameter_schema=enforce_parameter_schema,
                work_pool_name=work_pool_name,
                work_queue_name=work_queue_name,
                job_variables=job_variables,
                entrypoint_type=entrypoint_type,
                _sla=_sla,
            )

    @async_dispatch(ato_deployment)
    def to_deployment(
        self,
        name: str,
        interval: Optional[
            Union[
                Iterable[Union[int, float, datetime.timedelta]],
                int,
                float,
                datetime.timedelta,
            ]
        ] = None,
        cron: Optional[Union[Iterable[str], str]] = None,
        rrule: Optional[Union[Iterable[str], str]] = None,
        paused: Optional[bool] = None,
        schedule: Optional[Schedule] = None,
        schedules: Optional["FlexibleScheduleList"] = None,
        concurrency_limit: Optional[Union[int, ConcurrencyLimitConfig, None]] = None,
        parameters: Optional[dict[str, Any]] = None,
        triggers: Optional[list[Union[DeploymentTriggerTypes, TriggerTypes]]] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        version: Optional[str] = None,
        version_type: Optional[VersionType] = None,
        enforce_parameter_schema: bool = True,
        work_pool_name: Optional[str] = None,
        work_queue_name: Optional[str] = None,
        job_variables: Optional[dict[str, Any]] = None,
        entrypoint_type: EntrypointType = EntrypointType.FILE_PATH,
        _sla: Optional[Union[SlaTypes, list[SlaTypes]]] = None,  # experimental
    ) -> "RunnerDeployment":
        """
        Creates a runner deployment object for this flow.

        Args:
            name: The name to give the created deployment.
            interval: An interval on which to execute the new deployment. Accepts either a number
                or a timedelta object. If a number is given, it will be interpreted as seconds.
            cron: A cron schedule of when to execute runs of this deployment.
            rrule: An rrule schedule of when to execute runs of this deployment.
            paused: Whether or not to set this deployment as paused.
            schedule: A schedule object defining when to execute runs of this deployment.
                Used to provide additional scheduling options like `timezone` or `parameters`.
            schedules: A list of schedule objects defining when to execute runs of this deployment.
                Used to define multiple schedules or additional scheduling options such as `timezone`.
            concurrency_limit: The maximum number of runs of this deployment that can run at the same time.
            parameters: A dictionary of default parameter values to pass to runs of this deployment.
            triggers: A list of triggers that will kick off runs of this deployment.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            version_type: The type of version to use for the created deployment. The version type
                will be inferred if not provided.
            enforce_parameter_schema: Whether or not the Prefect API should enforce the
                parameter schema for the created deployment.
            work_pool_name: The name of the work pool to use for this deployment.
            work_queue_name: The name of the work queue to use for this deployment's scheduled runs.
                If not provided the default work queue for the work pool will be used.
            job_variables: Settings used to override the values specified default base job template
                of the chosen work pool. Refer to the base job template of the chosen work pool for
            entrypoint_type: Type of entrypoint to use for the deployment. When using a module path
                entrypoint, ensure that the module will be importable in the execution environment.
            _sla: (Experimental) SLA configuration for the deployment. May be removed or modified at any time. Currently only supported on Prefect Cloud.

        Examples:
            Prepare two deployments and serve them:

            ```python
            from prefect import flow, serve

            @flow
            def my_flow(name):
                print(f"hello {name}")

            @flow
            def my_other_flow(name):
                print(f"goodbye {name}")

            if __name__ == "__main__":
                hello_deploy = my_flow.to_deployment("hello", tags=["dev"])
                bye_deploy = my_other_flow.to_deployment("goodbye", tags=["dev"])
                serve(hello_deploy, bye_deploy)
            ```
        """
        from prefect.deployments.runner import RunnerDeployment

        if not name.endswith(".py"):
            _raise_on_name_with_banned_characters(name)

        if self._storage and self._entrypoint:
            return cast(
                RunnerDeployment,
                RunnerDeployment.from_storage(
                    storage=self._storage,
                    entrypoint=self._entrypoint,
                    name=name,
                    flow_name=self.name,
                    interval=interval,
                    cron=cron,
                    rrule=rrule,
                    paused=paused,
                    schedule=schedule,
                    schedules=schedules,
                    concurrency_limit=concurrency_limit,
                    tags=tags,
                    triggers=triggers,
                    parameters=parameters or {},
                    description=description,
                    version=version,
                    version_type=version_type,
                    enforce_parameter_schema=enforce_parameter_schema,
                    work_pool_name=work_pool_name,
                    work_queue_name=work_queue_name,
                    job_variables=job_variables,
                    _sla=_sla,
                    _sync=True,  # pyright: ignore[reportCallIssue] _sync is valid because .from_storage is decorated with async_dispatch
                ),
            )
        else:
            return RunnerDeployment.from_flow(
                flow=self,
                name=name,
                interval=interval,
                cron=cron,
                rrule=rrule,
                paused=paused,
                schedule=schedule,
                schedules=schedules,
                concurrency_limit=concurrency_limit,
                tags=tags,
                triggers=triggers,
                parameters=parameters or {},
                description=description,
                version=version,
                version_type=version_type,
                enforce_parameter_schema=enforce_parameter_schema,
                work_pool_name=work_pool_name,
                work_queue_name=work_queue_name,
                job_variables=job_variables,
                entrypoint_type=entrypoint_type,
                _sla=_sla,
            )

    def on_completion(self, fn: FlowStateHook[P, R]) -> FlowStateHook[P, R]:
        self.on_completion_hooks.append(fn)
        return fn

    def on_cancellation(self, fn: FlowStateHook[P, R]) -> FlowStateHook[P, R]:
        self.on_cancellation_hooks.append(fn)
        return fn

    def on_crashed(self, fn: FlowStateHook[P, R]) -> FlowStateHook[P, R]:
        self.on_crashed_hooks.append(fn)
        return fn

    def on_running(self, fn: FlowStateHook[P, R]) -> FlowStateHook[P, R]:
        self.on_running_hooks.append(fn)
        return fn

    def on_failure(self, fn: FlowStateHook[P, R]) -> FlowStateHook[P, R]:
        self.on_failure_hooks.append(fn)
        return fn

    def serve(
        self,
        name: Optional[str] = None,
        interval: Optional[
            Union[
                Iterable[Union[int, float, datetime.timedelta]],
                int,
                float,
                datetime.timedelta,
            ]
        ] = None,
        cron: Optional[Union[Iterable[str], str]] = None,
        rrule: Optional[Union[Iterable[str], str]] = None,
        paused: Optional[bool] = None,
        schedule: Optional[Schedule] = None,
        schedules: Optional["FlexibleScheduleList"] = None,
        global_limit: Optional[Union[int, ConcurrencyLimitConfig, None]] = None,
        triggers: Optional[list[Union[DeploymentTriggerTypes, TriggerTypes]]] = None,
        parameters: Optional[dict[str, Any]] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        version: Optional[str] = None,
        enforce_parameter_schema: bool = True,
        pause_on_shutdown: bool = True,
        print_starting_message: bool = True,
        limit: Optional[int] = None,
        webserver: bool = False,
        entrypoint_type: EntrypointType = EntrypointType.FILE_PATH,
    ) -> None:
        """
        Creates a deployment for this flow and starts a runner to monitor for scheduled work.

        Args:
            name: The name to give the created deployment. Defaults to the name of the flow.
            interval: An interval on which to execute the deployment. Accepts a number or a
                timedelta object to create a single schedule. If a number is given, it will be
                interpreted as seconds. Also accepts an iterable of numbers or timedelta to create
                multiple schedules.
            cron: A cron schedule string of when to execute runs of this deployment.
                Also accepts an iterable of cron schedule strings to create multiple schedules.
            rrule: An rrule schedule string of when to execute runs of this deployment.
                Also accepts an iterable of rrule schedule strings to create multiple schedules.
            triggers: A list of triggers that will kick off runs of this deployment.
            paused: Whether or not to set this deployment as paused.
            schedule: A schedule object defining when to execute runs of this deployment.
                Used to provide additional scheduling options like `timezone` or `parameters`.
            schedules: A list of schedule objects defining when to execute runs of this deployment.
                Used to define multiple schedules or additional scheduling options like `timezone`.
            global_limit: The maximum number of concurrent runs allowed across all served flow instances associated with the same deployment.
            parameters: A dictionary of default parameter values to pass to runs of this deployment.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            enforce_parameter_schema: Whether or not the Prefect API should enforce the
                parameter schema for the created deployment.
            pause_on_shutdown: If True, provided schedule will be paused when the serve function is stopped.
                If False, the schedules will continue running.
            print_starting_message: Whether or not to print the starting message when flow is served.
            limit: The maximum number of runs that can be executed concurrently by the created runner; only applies to this served flow. To apply a limit across multiple served flows, use `global_limit`.
            webserver: Whether or not to start a monitoring webserver for this flow.
            entrypoint_type: Type of entrypoint to use for the deployment. When using a module path
                entrypoint, ensure that the module will be importable in the execution environment.

        Examples:
            Serve a flow:

            ```python
            from prefect import flow

            @flow
            def my_flow(name):
                print(f"hello {name}")

            if __name__ == "__main__":
                my_flow.serve("example-deployment")
            ```

            Serve a flow and run it every hour:

            ```python
            from prefect import flow

            @flow
            def my_flow(name):
                print(f"hello {name}")

            if __name__ == "__main__":
                my_flow.serve("example-deployment", interval=3600)
            ```
        """
        from prefect.runner import Runner

        if not name:
            name = self.name
        else:
            # Only strip extension if it is a file path
            if (p := Path(name)).is_file():
                name = p.stem

        runner = Runner(name=name, pause_on_shutdown=pause_on_shutdown, limit=limit)
        deployment_id = runner.add_flow(
            self,
            name=name,
            triggers=triggers,
            interval=interval,
            cron=cron,
            rrule=rrule,
            paused=paused,
            schedule=schedule,
            schedules=schedules,
            concurrency_limit=global_limit,
            parameters=parameters,
            description=description,
            tags=tags,
            version=version,
            enforce_parameter_schema=enforce_parameter_schema,
            entrypoint_type=entrypoint_type,
        )
        if print_starting_message:
            help_message = (
                f"[green]Your flow {self.name!r} is being served and polling for"
                " scheduled runs!\n[/]\nTo trigger a run for this flow, use the"
                " following command:\n[blue]\n\t$ prefect deployment run"
                f" '{self.name}/{name}'\n[/]"
            )
            if PREFECT_UI_URL:
                help_message += (
                    "\nYou can also run your flow via the Prefect UI:"
                    f" [blue]{PREFECT_UI_URL.value()}/deployments/deployment/{deployment_id}[/]\n"
                )

            console = Console()
            console.print(help_message, soft_wrap=True)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            if "no running event loop" in str(exc):
                loop = None
            else:
                raise

        try:
            if loop is not None:
                loop.run_until_complete(runner.start(webserver=webserver))
            else:
                asyncio.run(runner.start(webserver=webserver))
        except (KeyboardInterrupt, TerminationSignal) as exc:
            logger.info(f"Received {type(exc).__name__}, shutting down...")
            if loop is not None:
                loop.stop()

    @classmethod
    async def afrom_source(
        cls,
        source: Union[str, Path, "RunnerStorage", ReadableDeploymentStorage],
        entrypoint: str,
    ) -> "Flow[..., Any]":
        """
        Loads a flow from a remote source asynchronously.

        Args:
            source: Either a URL to a git repository or a storage object.
            entrypoint:  The path to a file containing a flow and the name of the flow function in
                the format `./path/to/file.py:flow_func_name`.

        Returns:
            A new `Flow` instance.

        Examples:
            Load a flow from a public git repository:


            ```python
            from prefect import flow
            from prefect.runner.storage import GitRepository
            from prefect.blocks.system import Secret

            my_flow = flow.from_source(
                source="https://github.com/org/repo.git",
                entrypoint="flows.py:my_flow",
            )

            my_flow()
            ```

            Load a flow from a private git repository using an access token stored in a `Secret` block:

            ```python
            from prefect import flow
            from prefect.runner.storage import GitRepository
            from prefect.blocks.system import Secret

            my_flow = flow.from_source(
                source=GitRepository(
                    url="https://github.com/org/repo.git",
                    credentials={"access_token": Secret.load("github-access-token")}
                ),
                entrypoint="flows.py:my_flow",
            )

            my_flow()
            ```

            Load a flow from a local directory:

            ``` python
            # from_local_source.py

            from pathlib import Path
            from prefect import flow

            @flow(log_prints=True)
            def my_flow(name: str = "world"):
                print(f"Hello {name}! I'm a flow from a Python script!")

            if __name__ == "__main__":
                my_flow.from_source(
                    source=str(Path(__file__).parent),
                    entrypoint="from_local_source.py:my_flow",
                ).deploy(
                    name="my-deployment",
                    parameters=dict(name="Marvin"),
                    work_pool_name="local",
                )
            ```
        """

        from prefect.runner.storage import (
            BlockStorageAdapter,
            LocalStorage,
            RunnerStorage,
            create_storage_from_source,
        )

        if isinstance(source, (Path, str)):
            if isinstance(source, Path):
                source = str(source)
            storage = create_storage_from_source(source)
        elif isinstance(source, RunnerStorage):
            storage = source
        elif hasattr(source, "get_directory"):
            storage = BlockStorageAdapter(source)
        else:
            raise TypeError(
                f"Unsupported source type {type(source).__name__!r}. Please provide a"
                " URL to remote storage or a storage object."
            )
        with tempfile.TemporaryDirectory() as tmpdir:
            if not isinstance(storage, LocalStorage):
                storage.set_base_path(Path(tmpdir))
                await storage.pull_code()

            full_entrypoint = str(storage.destination / entrypoint)
            flow = cast(
                "Flow[..., Any]",
                await from_async.wait_for_call_in_new_thread(
                    create_call(load_flow_from_entrypoint, full_entrypoint)
                ),
            )
            flow._storage = storage
            flow._entrypoint = entrypoint

        return flow

    @classmethod
    @async_dispatch(afrom_source)
    def from_source(
        cls,
        source: Union[str, Path, "RunnerStorage", ReadableDeploymentStorage],
        entrypoint: str,
    ) -> "Flow[..., Any]":
        """
        Loads a flow from a remote source.

        Args:
            source: Either a URL to a git repository or a storage object.
            entrypoint:  The path to a file containing a flow and the name of the flow function in
                the format `./path/to/file.py:flow_func_name`.

        Returns:
            A new `Flow` instance.

        Examples:
            Load a flow from a public git repository:


            ```python
            from prefect import flow
            from prefect.runner.storage import GitRepository
            from prefect.blocks.system import Secret

            my_flow = flow.from_source(
                source="https://github.com/org/repo.git",
                entrypoint="flows.py:my_flow",
            )

            my_flow()
            ```

            Load a flow from a private git repository using an access token stored in a `Secret` block:

            ```python
            from prefect import flow
            from prefect.runner.storage import GitRepository
            from prefect.blocks.system import Secret

            my_flow = flow.from_source(
                source=GitRepository(
                    url="https://github.com/org/repo.git",
                    credentials={"access_token": Secret.load("github-access-token")}
                ),
                entrypoint="flows.py:my_flow",
            )

            my_flow()
            ```

            Load a flow from a local directory:

            ``` python
            # from_local_source.py

            from pathlib import Path
            from prefect import flow

            @flow(log_prints=True)
            def my_flow(name: str = "world"):
                print(f"Hello {name}! I'm a flow from a Python script!")

            if __name__ == "__main__":
                my_flow.from_source(
                    source=str(Path(__file__).parent),
                    entrypoint="from_local_source.py:my_flow",
                ).deploy(
                    name="my-deployment",
                    parameters=dict(name="Marvin"),
                    work_pool_name="local",
                )
            ```
        """

        from prefect.runner.storage import (
            BlockStorageAdapter,
            LocalStorage,
            RunnerStorage,
            create_storage_from_source,
        )

        if isinstance(source, (Path, str)):
            if isinstance(source, Path):
                source = str(source)
            storage = create_storage_from_source(source)
        elif isinstance(source, RunnerStorage):
            storage = source
        elif hasattr(source, "get_directory"):
            storage = BlockStorageAdapter(source)
        else:
            raise TypeError(
                f"Unsupported source type {type(source).__name__!r}. Please provide a"
                " URL to remote storage or a storage object."
            )
        with tempfile.TemporaryDirectory() as tmpdir:
            if not isinstance(storage, LocalStorage):
                storage.set_base_path(Path(tmpdir))
                run_coro_as_sync(storage.pull_code())

            full_entrypoint = str(storage.destination / entrypoint)
            flow = load_flow_from_entrypoint(full_entrypoint)
            flow._storage = storage
            flow._entrypoint = entrypoint

        return flow

    @sync_compatible
    async def deploy(
        self,
        name: str,
        work_pool_name: Optional[str] = None,
        image: Optional[Union[str, DockerImage]] = None,
        build: bool = True,
        push: bool = True,
        work_queue_name: Optional[str] = None,
        job_variables: Optional[dict[str, Any]] = None,
        interval: Optional[Union[int, float, datetime.timedelta]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        paused: Optional[bool] = None,
        schedule: Optional[Schedule] = None,
        schedules: Optional[list[Schedule]] = None,
        concurrency_limit: Optional[Union[int, ConcurrencyLimitConfig, None]] = None,
        triggers: Optional[list[Union[DeploymentTriggerTypes, TriggerTypes]]] = None,
        parameters: Optional[dict[str, Any]] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        version: Optional[str] = None,
        version_type: Optional[VersionType] = None,
        enforce_parameter_schema: bool = True,
        entrypoint_type: EntrypointType = EntrypointType.FILE_PATH,
        print_next_steps: bool = True,
        ignore_warnings: bool = False,
        _sla: Optional[Union[SlaTypes, list[SlaTypes]]] = None,
    ) -> UUID:
        """
        Deploys a flow to run on dynamic infrastructure via a work pool.

        By default, calling this method will build a Docker image for the flow, push it to a registry,
        and create a deployment via the Prefect API that will run the flow on the given schedule.

        If you want to use an existing image, you can pass `build=False` to skip building and pushing
        an image.

        Args:
            name: The name to give the created deployment.
            work_pool_name: The name of the work pool to use for this deployment. Defaults to
                the value of `PREFECT_DEFAULT_WORK_POOL_NAME`.
            image: The name of the Docker image to build, including the registry and
                repository. Pass a DockerImage instance to customize the Dockerfile used
                and build arguments.
            build: Whether or not to build a new image for the flow. If False, the provided
                image will be used as-is and pulled at runtime.
            push: Whether or not to skip pushing the built image to a registry.
            work_queue_name: The name of the work queue to use for this deployment's scheduled runs.
                If not provided the default work queue for the work pool will be used.
            job_variables: Settings used to override the values specified default base job template
                of the chosen work pool. Refer to the base job template of the chosen work pool for
                available settings.
            interval: An interval on which to execute the deployment. Accepts a number or a
                timedelta object to create a single schedule. If a number is given, it will be
                interpreted as seconds. Also accepts an iterable of numbers or timedelta to create
                multiple schedules.
            cron: A cron schedule string of when to execute runs of this deployment.
                Also accepts an iterable of cron schedule strings to create multiple schedules.
            rrule: An rrule schedule string of when to execute runs of this deployment.
                Also accepts an iterable of rrule schedule strings to create multiple schedules.
            triggers: A list of triggers that will kick off runs of this deployment.
            paused: Whether or not to set this deployment as paused.
            schedule: A schedule object defining when to execute runs of this deployment.
                Used to provide additional scheduling options like `timezone` or `parameters`.
            schedules: A list of schedule objects defining when to execute runs of this deployment.
                Used to define multiple schedules or additional scheduling options like `timezone`.
            concurrency_limit: The maximum number of runs that can be executed concurrently.
            parameters: A dictionary of default parameter values to pass to runs of this deployment.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            version_type: The type of version to use for the created deployment. The version type
                will be inferred if not provided.
            enforce_parameter_schema: Whether or not the Prefect API should enforce the
                parameter schema for the created deployment.
            entrypoint_type: Type of entrypoint to use for the deployment. When using a module path
                entrypoint, ensure that the module will be importable in the execution environment.
            print_next_steps_message: Whether or not to print a message with next steps
                after deploying the deployments.
            ignore_warnings: Whether or not to ignore warnings about the work pool type.
            _sla: (Experimental) SLA configuration for the deployment. May be removed or modified at any time. Currently only supported on Prefect Cloud.
        Returns:
            The ID of the created/updated deployment.

        Examples:
            Deploy a local flow to a work pool:

            ```python
            from prefect import flow

            @flow
            def my_flow(name):
                print(f"hello {name}")

            if __name__ == "__main__":
                my_flow.deploy(
                    "example-deployment",
                    work_pool_name="my-work-pool",
                    image="my-repository/my-image:dev",
                )
            ```

            Deploy a remotely stored flow to a work pool:

            ```python
            from prefect import flow

            if __name__ == "__main__":
                flow.from_source(
                    source="https://github.com/org/repo.git",
                    entrypoint="flows.py:my_flow",
                ).deploy(
                    "example-deployment",
                    work_pool_name="my-work-pool",
                    image="my-repository/my-image:dev",
                )
            ```
        """
        if not (
            work_pool_name := work_pool_name or PREFECT_DEFAULT_WORK_POOL_NAME.value()
        ):
            raise ValueError(
                "No work pool name provided. Please provide a `work_pool_name` or set the"
                " `PREFECT_DEFAULT_WORK_POOL_NAME` environment variable."
            )

        from prefect.client.orchestration import get_client

        try:
            async with get_client() as client:
                work_pool = await client.read_work_pool(work_pool_name)
                active_workers = await client.read_workers_for_work_pool(
                    work_pool_name,
                    worker_filter=WorkerFilter(
                        status=WorkerFilterStatus(any_=["ONLINE"])
                    ),
                )
        except ObjectNotFound as exc:
            raise ValueError(
                f"Could not find work pool {work_pool_name!r}. Please create it before"
                " deploying this flow."
            ) from exc

        to_deployment_coro = self.to_deployment(
            name=name,
            interval=interval,
            cron=cron,
            rrule=rrule,
            schedule=schedule,
            schedules=schedules,
            concurrency_limit=concurrency_limit,
            paused=paused,
            triggers=triggers,
            parameters=parameters,
            description=description,
            tags=tags,
            version=version,
            version_type=version_type,
            enforce_parameter_schema=enforce_parameter_schema,
            work_queue_name=work_queue_name,
            job_variables=job_variables,
            entrypoint_type=entrypoint_type,
            _sla=_sla,
        )

        if inspect.isawaitable(to_deployment_coro):
            deployment = await to_deployment_coro
        else:
            deployment = to_deployment_coro

        from prefect.deployments.runner import deploy

        deploy_coro = deploy(
            deployment,
            work_pool_name=work_pool_name,
            image=image,
            build=build,
            push=push,
            print_next_steps_message=False,
            ignore_warnings=ignore_warnings,
        )
        if TYPE_CHECKING:
            assert inspect.isawaitable(deploy_coro)

        deployment_ids = await deploy_coro

        if print_next_steps:
            console = Console()
            if (
                not work_pool.is_push_pool
                and not work_pool.is_managed_pool
                and not active_workers
            ):
                console.print(
                    "\nTo execute flow runs from this deployment, start a worker in a"
                    " separate terminal that pulls work from the"
                    f" {work_pool_name!r} work pool:"
                )
                console.print(
                    f"\n\t$ prefect worker start --pool {work_pool_name!r}",
                    style="blue",
                )
            console.print(
                "\nTo schedule a run for this deployment, use the following command:"
            )
            console.print(
                f"\n\t$ prefect deployment run '{self.name}/{name}'\n",
                style="blue",
            )
            if PREFECT_UI_URL:
                message = (
                    "\nYou can also run your flow via the Prefect UI:"
                    f" [blue]{PREFECT_UI_URL.value()}/deployments/deployment/{deployment_ids[0]}[/]\n"
                )
                console.print(message, soft_wrap=True)

        return deployment_ids[0]

    @overload
    def __call__(self: "Flow[P, NoReturn]", *args: P.args, **kwargs: P.kwargs) -> None:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]", *args: P.args, **kwargs: P.kwargs
    ) -> Coroutine[Any, Any, T]: ...

    @overload
    def __call__(
        self: "Flow[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T: ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> Awaitable[State[T]]: ...

    @overload
    def __call__(
        self: "Flow[P, T]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> State[T]: ...

    def __call__(
        self,
        *args: "P.args",
        return_state: bool = False,
        wait_for: Optional[Iterable[PrefectFuture[Any]]] = None,
        **kwargs: "P.kwargs",
    ):
        """
        Run the flow and return its result.


        Flow parameter values must be serializable by Pydantic.

        If writing an async flow, this call must be awaited.

        This will create a new flow run in the API.

        Args:
            *args: Arguments to run the flow with.
            return_state: Return a Prefect State containing the result of the
                flow run.
            wait_for: Upstream task futures to wait for before starting the flow if called as a subflow
            **kwargs: Keyword arguments to run the flow with.

        Returns:
            If `return_state` is False, returns the result of the flow run.
            If `return_state` is True, returns the result of the flow run
                wrapped in a Prefect State which provides error handling.

        Examples:

            Define a flow

            >>> @flow
            >>> def my_flow(name):
            >>>     print(f"hello {name}")
            >>>     return f"goodbye {name}"

            Run a flow

            >>> my_flow("marvin")
            hello marvin
            "goodbye marvin"

            Run a flow with additional tags

            >>> from prefect import tags
            >>> with tags("db", "blue"):
            >>>     my_flow("foo")
        """
        from prefect.utilities.visualization import (
            get_task_viz_tracker,
            track_viz_task,
        )

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return_type = "state" if return_state else "result"

        task_viz_tracker = get_task_viz_tracker()
        if task_viz_tracker:
            # this is a subflow, for now return a single task and do not go further
            # we can add support for exploring subflows for tasks in the future.
            return track_viz_task(self.isasync, self.name, parameters)

        from prefect.flow_engine import run_flow

        return run_flow(
            flow=self,
            parameters=parameters,
            wait_for=wait_for,
            return_type=return_type,
        )

    @sync_compatible
    async def visualize(self, *args: "P.args", **kwargs: "P.kwargs"):
        """
        Generates a graphviz object representing the current flow. In IPython notebooks,
        it's rendered inline, otherwise in a new window as a PNG.

        Raises:
            - ImportError: If `graphviz` isn't installed.
            - GraphvizExecutableNotFoundError: If the `dot` executable isn't found.
            - FlowVisualizationError: If the flow can't be visualized for any other reason.
        """
        from prefect.utilities.visualization import (
            FlowVisualizationError,
            GraphvizExecutableNotFoundError,
            GraphvizImportError,
            TaskVizTracker,
            VisualizationUnsupportedError,
            build_task_dependencies,
            visualize_task_dependencies,
        )

        if not PREFECT_TESTING_UNIT_TEST_MODE:
            warnings.warn(
                "`flow.visualize()` will execute code inside of your flow that is not"
                " decorated with `@task` or `@flow`."
            )

        try:
            with TaskVizTracker() as tracker:
                if self.isasync:
                    await self.fn(*args, **kwargs)  # type: ignore[reportGeneralTypeIssues]
                else:
                    self.fn(*args, **kwargs)

                graph = build_task_dependencies(tracker)

                visualize_task_dependencies(graph, self.name)

        except GraphvizImportError:
            raise
        except GraphvizExecutableNotFoundError:
            raise
        except VisualizationUnsupportedError:
            raise
        except FlowVisualizationError:
            raise
        except Exception as e:
            msg = (
                "It's possible you are trying to visualize a flow that contains "
                "code that directly interacts with the result of a task"
                " inside of the flow. \nTry passing a `viz_return_value` "
                "to the task decorator, e.g. `@task(viz_return_value=[1, 2, 3]).`"
            )

            new_exception = type(e)(str(e) + "\n" + msg)
            # Copy traceback information from the original exception
            new_exception.__traceback__ = e.__traceback__
            raise new_exception


class FlowDecorator:
    @overload
    def __call__(self, __fn: Callable[P, R]) -> Flow[P, R]: ...

    @overload
    def __call__(
        self,
        __fn: None = None,
        *,
        name: Optional[str] = None,
        version: Optional[str] = None,
        flow_run_name: Optional[Union[Callable[[], str], str]] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[Union[int, float]] = None,
        task_runner: None = None,
        description: Optional[str] = None,
        timeout_seconds: Union[int, float, None] = None,
        validate_parameters: bool = True,
        persist_result: Optional[bool] = None,
        result_storage: Optional[ResultStorage] = None,
        result_serializer: Optional[ResultSerializer] = None,
        cache_result_in_memory: bool = True,
        log_prints: Optional[bool] = None,
        on_completion: Optional[list[FlowStateHook[..., Any]]] = None,
        on_failure: Optional[list[FlowStateHook[..., Any]]] = None,
        on_cancellation: Optional[list[FlowStateHook[..., Any]]] = None,
        on_crashed: Optional[list[FlowStateHook[..., Any]]] = None,
        on_running: Optional[list[FlowStateHook[..., Any]]] = None,
    ) -> Callable[[Callable[P, R]], Flow[P, R]]: ...

    @overload
    def __call__(
        self,
        __fn: None = None,
        *,
        name: Optional[str] = None,
        version: Optional[str] = None,
        flow_run_name: Optional[Union[Callable[[], str], str]] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[Union[int, float]] = None,
        task_runner: Optional[TaskRunner[PrefectFuture[R]]] = None,
        description: Optional[str] = None,
        timeout_seconds: Union[int, float, None] = None,
        validate_parameters: bool = True,
        persist_result: Optional[bool] = None,
        result_storage: Optional[ResultStorage] = None,
        result_serializer: Optional[ResultSerializer] = None,
        cache_result_in_memory: bool = True,
        log_prints: Optional[bool] = None,
        on_completion: Optional[list[FlowStateHook[..., Any]]] = None,
        on_failure: Optional[list[FlowStateHook[..., Any]]] = None,
        on_cancellation: Optional[list[FlowStateHook[..., Any]]] = None,
        on_crashed: Optional[list[FlowStateHook[..., Any]]] = None,
        on_running: Optional[list[FlowStateHook[..., Any]]] = None,
    ) -> Callable[[Callable[P, R]], Flow[P, R]]: ...

    def __call__(
        self,
        __fn: Optional[Callable[P, R]] = None,
        *,
        name: Optional[str] = None,
        version: Optional[str] = None,
        flow_run_name: Optional[Union[Callable[[], str], str]] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Union[int, float, None] = None,
        task_runner: Optional[TaskRunner[PrefectFuture[R]]] = None,
        description: Optional[str] = None,
        timeout_seconds: Union[int, float, None] = None,
        validate_parameters: bool = True,
        persist_result: Optional[bool] = None,
        result_storage: Optional[ResultStorage] = None,
        result_serializer: Optional[ResultSerializer] = None,
        cache_result_in_memory: bool = True,
        log_prints: Optional[bool] = None,
        on_completion: Optional[list[FlowStateHook[..., Any]]] = None,
        on_failure: Optional[list[FlowStateHook[..., Any]]] = None,
        on_cancellation: Optional[list[FlowStateHook[..., Any]]] = None,
        on_crashed: Optional[list[FlowStateHook[..., Any]]] = None,
        on_running: Optional[list[FlowStateHook[..., Any]]] = None,
    ) -> Union[Flow[P, R], Callable[[Callable[P, R]], Flow[P, R]]]:
        """
        Decorator to designate a function as a Prefect workflow.

        This decorator may be used for asynchronous or synchronous functions.

        Flow parameters must be serializable by Pydantic.

        Args:
            name: An optional name for the flow; if not provided, the name will be inferred
                from the given function.
            version: An optional version string for the flow; if not provided, we will
                attempt to create a version string as a hash of the file containing the
                wrapped function; if the file cannot be located, the version will be null.
            flow_run_name: An optional name to distinguish runs of this flow; this name can
                be provided as a string template with the flow's parameters as variables,
                or a function that returns a string.
            retries: An optional number of times to retry on flow run failure.
            retry_delay_seconds: An optional number of seconds to wait before retrying the
                flow after failure. This is only applicable if `retries` is nonzero.
            task_runner: An optional task runner to use for task execution within the flow; if
                not provided, a `ConcurrentTaskRunner` will be instantiated.
            description: An optional string description for the flow; if not provided, the
                description will be pulled from the docstring for the decorated function.
            timeout_seconds: An optional number of seconds indicating a maximum runtime for
                the flow. If the flow exceeds this runtime, it will be marked as failed.
                Flow execution may continue until the next task is called.
            validate_parameters: By default, parameters passed to flows are validated by
                Pydantic. This will check that input values conform to the annotated types
                on the function. Where possible, values will be coerced into the correct
                type; for example, if a parameter is defined as `x: int` and "5" is passed,
                it will be resolved to `5`. If set to `False`, no validation will be
                performed on flow parameters.
            persist_result: An optional toggle indicating whether the result of this flow
                should be persisted to result storage. Defaults to `None`, which indicates
                that Prefect should choose whether the result should be persisted depending on
                the features being used.
            result_storage: An optional block to use to persist the result of this flow.
                This value will be used as the default for any tasks in this flow.
                If not provided, the local file system will be used unless called as
                a subflow, at which point the default will be loaded from the parent flow.
            result_serializer: An optional serializer to use to serialize the result of this
                flow for persistence. This value will be used as the default for any tasks
                in this flow. If not provided, the value of `PREFECT_RESULTS_DEFAULT_SERIALIZER`
                will be used unless called as a subflow, at which point the default will be
                loaded from the parent flow.
            cache_result_in_memory: An optional toggle indicating whether the cached result of
                a running the flow should be stored in memory. Defaults to `True`.
            log_prints: If set, `print` statements in the flow will be redirected to the
                Prefect logger for the flow run. Defaults to `None`, which indicates that
                the value from the parent flow should be used. If this is a parent flow,
                the default is pulled from the `PREFECT_LOGGING_LOG_PRINTS` setting.
            on_completion: An optional list of functions to call when the flow run is
                completed. Each function should accept three arguments: the flow, the flow
                run, and the final state of the flow run.
            on_failure: An optional list of functions to call when the flow run fails. Each
                function should accept three arguments: the flow, the flow run, and the
                final state of the flow run.
            on_cancellation: An optional list of functions to call when the flow run is
                cancelled. These functions will be passed the flow, flow run, and final state.
            on_crashed: An optional list of functions to call when the flow run crashes. Each
                function should accept three arguments: the flow, the flow run, and the
                final state of the flow run.
            on_running: An optional list of functions to call when the flow run is started. Each
                function should accept three arguments: the flow, the flow run, and the current state

        Returns:
            A callable `Flow` object which, when called, will run the flow and return its
            final state.

        Examples:
            Define a simple flow

            >>> from prefect import flow
            >>> @flow
            >>> def add(x, y):
            >>>     return x + y

            Define an async flow

            >>> @flow
            >>> async def add(x, y):
            >>>     return x + y

            Define a flow with a version and description

            >>> @flow(version="first-flow", description="This flow is empty!")
            >>> def my_flow():
            >>>     pass

            Define a flow with a custom name

            >>> @flow(name="The Ultimate Flow")
            >>> def my_flow():
            >>>     pass

            Define a flow that submits its tasks to dask

            >>> from prefect_dask.task_runners import DaskTaskRunner
            >>>
            >>> @flow(task_runner=DaskTaskRunner)
            >>> def my_flow():
            >>>     pass
        """
        if __fn:
            return Flow(
                fn=__fn,
                name=name,
                version=version,
                flow_run_name=flow_run_name,
                task_runner=task_runner,
                description=description,
                timeout_seconds=timeout_seconds,
                validate_parameters=validate_parameters,
                retries=retries,
                retry_delay_seconds=retry_delay_seconds,
                persist_result=persist_result,
                result_storage=result_storage,
                result_serializer=result_serializer,
                cache_result_in_memory=cache_result_in_memory,
                log_prints=log_prints,
                on_completion=on_completion,
                on_failure=on_failure,
                on_cancellation=on_cancellation,
                on_crashed=on_crashed,
                on_running=on_running,
            )
        else:
            return cast(
                Callable[[Callable[P, R]], Flow[P, R]],
                partial(
                    flow,
                    name=name,
                    version=version,
                    flow_run_name=flow_run_name,
                    task_runner=task_runner,
                    description=description,
                    timeout_seconds=timeout_seconds,
                    validate_parameters=validate_parameters,
                    retries=retries,
                    retry_delay_seconds=retry_delay_seconds,
                    persist_result=persist_result,
                    result_storage=result_storage,
                    result_serializer=result_serializer,
                    cache_result_in_memory=cache_result_in_memory,
                    log_prints=log_prints,
                    on_completion=on_completion,
                    on_failure=on_failure,
                    on_cancellation=on_cancellation,
                    on_crashed=on_crashed,
                    on_running=on_running,
                ),
            )

    if not TYPE_CHECKING:
        # Add from_source so it is available on the flow function we all know and love
        from_source = staticmethod(Flow.from_source)
    else:
        # Mypy loses the plot somewhere along the line, so the annotation is reconstructed
        # manually here.
        @staticmethod
        def from_source(
            source: Union[str, Path, "RunnerStorage", ReadableDeploymentStorage],
            entrypoint: str,
        ) -> Union["Flow[..., Any]", Coroutine[Any, Any, "Flow[..., Any]"]]: ...


flow: FlowDecorator = FlowDecorator()


class InfrastructureBoundFlow(Flow[P, R]):
    """
    EXPERIMENTAL: This class is experimental and may be removed or changed in future
        releases.

    A flow that is bound to running on a specific infrastructure.

    Attributes:
        work_pool: The name of the work pool to run the flow on. The base job
            configuration of the work pool will determine the configuration of the
            infrastructure the flow will run on.
        job_variables: Infrastructure configuration that will override the base job
            configuration of the work pool.
        worker_cls: The class of the worker to use to spin up infrastructure and submit
            the flow to it.
    """

    def __init__(
        self,
        *args: Any,
        work_pool: str,
        job_variables: dict[str, Any],
        worker_cls: type["BaseWorker[Any, Any, Any]"],
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self.work_pool = work_pool
        self.job_variables = job_variables
        self.worker_cls = worker_cls

    @overload
    def __call__(self: "Flow[P, NoReturn]", *args: P.args, **kwargs: P.kwargs) -> None:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Coroutine[Any, Any, T]: ...

    @overload
    def __call__(
        self: "Flow[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T: ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> Awaitable[State[T]]: ...

    @overload
    def __call__(
        self: "Flow[P, T]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> State[T]: ...

    def __call__(
        self,
        *args: "P.args",
        return_state: bool = False,
        wait_for: Optional[Iterable[PrefectFuture[Any]]] = None,
        **kwargs: "P.kwargs",
    ):
        async def modified_call(
            *args: P.args,
            return_state: bool = False,
            # TODO: Handle wait_for once we have an asynchronous way to wait for futures
            # We should wait locally for futures to resolve before spinning up
            # infrastructure.
            wait_for: Optional[Iterable[PrefectFuture[Any]]] = None,
            **kwargs: P.kwargs,
        ) -> R | State[R]:
            try:
                async with self.worker_cls(work_pool_name=self.work_pool) as worker:
                    parameters = get_call_parameters(self, args, kwargs)
                    future = await worker.submit(
                        flow=self,
                        parameters=parameters,
                        job_variables=self.job_variables,
                    )
                    if return_state:
                        await future.wait_async()
                        return future.state
                    return await future.aresult()
            except (ExceptionGroup, BaseExceptionGroup) as exc:
                # For less verbose tracebacks
                exceptions = exc.exceptions
                if len(exceptions) == 1:
                    raise exceptions[0] from None
                else:
                    raise

        if inspect.iscoroutinefunction(self.fn):
            return modified_call(
                *args, return_state=return_state, wait_for=wait_for, **kwargs
            )
        else:
            return run_coro_as_sync(
                modified_call(
                    *args,
                    return_state=return_state,
                    wait_for=wait_for,
                    **kwargs,
                )
            )

    def submit(self, *args: P.args, **kwargs: P.kwargs) -> PrefectFlowRunFuture[R]:
        """
        EXPERIMENTAL: This method is experimental and may be removed or changed in future
            releases.

        Submit the flow to run on remote infrastructure.

        Args:
            *args: Positional arguments to pass to the flow.
            **kwargs: Keyword arguments to pass to the flow.

        Returns:
            A `PrefectFlowRunFuture` that can be used to retrieve the result of the flow run.

        Examples:
            Submit a flow to run on Kubernetes:

            ```python
            from prefect import flow
            from prefect_kubernetes.experimental import kubernetes

            @kubernetes(work_pool="my-kubernetes-work-pool")
            @flow
            def my_flow(x: int, y: int):
                return x + y

            future = my_flow.submit(x=1, y=2)
            result = future.result()
            print(result)
            ```
        """

        async def submit_func():
            async with self.worker_cls(work_pool_name=self.work_pool) as worker:
                parameters = get_call_parameters(self, args, kwargs)
                return await worker.submit(
                    flow=self,
                    parameters=parameters,
                    job_variables=self.job_variables,
                )

        return run_coro_as_sync(submit_func())

    def with_options(
        self,
        *,
        name: Optional[str] = None,
        version: Optional[str] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[Union[int, float]] = None,
        description: Optional[str] = None,
        flow_run_name: Optional[Union[Callable[[], str], str]] = None,
        task_runner: Union[
            Type[TaskRunner[PrefectFuture[Any]]], TaskRunner[PrefectFuture[Any]], None
        ] = None,
        timeout_seconds: Union[int, float, None] = None,
        validate_parameters: Optional[bool] = None,
        persist_result: Optional[bool] = NotSet,  # type: ignore
        result_storage: Optional[ResultStorage] = NotSet,  # type: ignore
        result_serializer: Optional[ResultSerializer] = NotSet,  # type: ignore
        cache_result_in_memory: Optional[bool] = None,
        log_prints: Optional[bool] = NotSet,  # type: ignore
        on_completion: Optional[list[FlowStateHook[P, R]]] = None,
        on_failure: Optional[list[FlowStateHook[P, R]]] = None,
        on_cancellation: Optional[list[FlowStateHook[P, R]]] = None,
        on_crashed: Optional[list[FlowStateHook[P, R]]] = None,
        on_running: Optional[list[FlowStateHook[P, R]]] = None,
        job_variables: Optional[dict[str, Any]] = None,
    ) -> "InfrastructureBoundFlow[P, R]":
        new_flow = super().with_options(
            name=name,
            version=version,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
            description=description,
            flow_run_name=flow_run_name,
            task_runner=task_runner,
            timeout_seconds=timeout_seconds,
            validate_parameters=validate_parameters,
            persist_result=persist_result,
            result_storage=result_storage,
            result_serializer=result_serializer,
            cache_result_in_memory=cache_result_in_memory,
            log_prints=log_prints,
            on_completion=on_completion,
            on_failure=on_failure,
            on_cancellation=on_cancellation,
            on_crashed=on_crashed,
            on_running=on_running,
        )
        new_infrastructure_bound_flow = bind_flow_to_infrastructure(
            new_flow,
            self.work_pool,
            self.worker_cls,
            job_variables=job_variables
            if job_variables is not None
            else self.job_variables,
        )
        return new_infrastructure_bound_flow


def bind_flow_to_infrastructure(
    flow: Flow[P, R],
    work_pool: str,
    worker_cls: type["BaseWorker[Any, Any, Any]"],
    job_variables: dict[str, Any] | None = None,
) -> InfrastructureBoundFlow[P, R]:
    new = InfrastructureBoundFlow[P, R](
        flow.fn,
        work_pool=work_pool,
        job_variables=job_variables or {},
        worker_cls=worker_cls,
    )
    # Copy all attributes from the original flow
    for attr, value in flow.__dict__.items():
        setattr(new, attr, value)
    return new


def _raise_on_name_with_banned_characters(name: Optional[str]) -> Optional[str]:
    """
    Raise an InvalidNameError if the given name contains any invalid
    characters.
    """
    if name is None:
        return name

    if not re.match(WITHOUT_BANNED_CHARACTERS, name):
        raise InvalidNameError(
            f"Name {name!r} contains an invalid character. "
            f"Must not contain any of: {BANNED_CHARACTERS}."
        )

    return name


def select_flow(
    flows: Iterable[Flow[P, R]],
    flow_name: Optional[str] = None,
    from_message: Optional[str] = None,
) -> Flow[P, R]:
    """
    Select the only flow in an iterable or a flow specified by name.

    Returns
        A single flow object

    Raises:
        MissingFlowError: If no flows exist in the iterable
        MissingFlowError: If a flow name is provided and that flow does not exist
        UnspecifiedFlowError: If multiple flows exist but no flow name was provided
    """
    # Convert to flows by name
    flows_dict = {f.name: f for f in flows}

    # Add a leading space if given, otherwise use an empty string
    from_message = (" " + from_message) if from_message else ""
    if not Optional:
        raise MissingFlowError(f"No flows found{from_message}.")

    elif flow_name and flow_name not in flows_dict:
        raise MissingFlowError(
            f"Flow {flow_name!r} not found{from_message}. "
            f"Found the following flows: {listrepr(flows_dict.keys())}. "
            "Check to make sure that your flow function is decorated with `@flow`."
        )

    elif not flow_name and len(flows_dict) > 1:
        raise UnspecifiedFlowError(
            (
                f"Found {len(flows_dict)} flows{from_message}:"
                f" {listrepr(sorted(flows_dict.keys()))}. Specify a flow name to select a"
                " flow."
            ),
        )

    if flow_name:
        return flows_dict[flow_name]
    else:
        return list(flows_dict.values())[0]


def load_flow_from_entrypoint(
    entrypoint: str,
    use_placeholder_flow: bool = True,
) -> Flow[P, Any]:
    """
    Extract a flow object from a script at an entrypoint by running all of the code in the file.

    Args:
        entrypoint: a string in the format `<path_to_script>:<flow_func_name>`
            or a string in the format `<path_to_script>:<class_name>.<flow_method_name>`
            or a module path to a flow function
        use_placeholder_flow: if True, use a placeholder Flow object if the actual flow object
            cannot be loaded from the entrypoint (e.g. dependencies are missing)

    Returns:
        The flow object from the script

    Raises:
        ScriptError: If an exception is encountered while running the script
        MissingFlowError: If the flow function specified in the entrypoint does not exist
    """

    if ":" in entrypoint:
        # split by the last colon once to handle Windows paths with drive letters i.e C:\path\to\file.py:do_stuff
        path, func_name = entrypoint.rsplit(":", maxsplit=1)
    else:
        path, func_name = entrypoint.rsplit(".", maxsplit=1)
    try:
        flow: Flow[P, Any] = import_object(entrypoint)  # pyright: ignore[reportRedeclaration]
    except AttributeError as exc:
        raise MissingFlowError(
            f"Flow function with name {func_name!r} not found in {path!r}. "
        ) from exc
    except ScriptError:
        # If the flow has dependencies that are not installed in the current
        # environment, fallback to loading the flow via AST parsing.
        if use_placeholder_flow:
            flow: Optional[Flow[P, Any]] = safe_load_flow_from_entrypoint(entrypoint)
            if flow is None:
                raise
        else:
            raise

    if not isinstance(flow, Flow):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise MissingFlowError(
            f"Function with name {func_name!r} is not a flow. Make sure that it is "
            "decorated with '@flow'."
        )

    return flow


def load_function_and_convert_to_flow(entrypoint: str) -> Flow[P, Any]:
    """
    Loads a function from an entrypoint and converts it to a flow if it is not already a flow.
    """

    if ":" in entrypoint:
        # split by the last colon once to handle Windows paths with drive letters i.e C:\path\to\file.py:do_stuff
        path, func_name = entrypoint.rsplit(":", maxsplit=1)
    else:
        path, func_name = entrypoint.rsplit(".", maxsplit=1)
    try:
        func = import_object(entrypoint)  # pyright: ignore[reportRedeclaration]
    except AttributeError as exc:
        raise RuntimeError(
            f"Function with name {func_name!r} not found in {path!r}."
        ) from exc

    if isinstance(func, Flow):
        return func
    else:
        return Flow(func, log_prints=True)


def serve(
    *args: "RunnerDeployment",
    pause_on_shutdown: bool = True,
    print_starting_message: bool = True,
    limit: Optional[int] = None,
    **kwargs: Any,
) -> None:
    """
    Serve the provided list of deployments.

    Args:
        *args: A list of deployments to serve.
        pause_on_shutdown: A boolean for whether or not to automatically pause
            deployment schedules on shutdown.
        print_starting_message: Whether or not to print message to the console
            on startup.
        limit: The maximum number of runs that can be executed concurrently.
        **kwargs: Additional keyword arguments to pass to the runner.

    Examples:
        Prepare two deployments and serve them:

        ```python
        import datetime

        from prefect import flow, serve

        @flow
        def my_flow(name):
            print(f"hello {name}")

        @flow
        def my_other_flow(name):
            print(f"goodbye {name}")

        if __name__ == "__main__":
            # Run once a day
            hello_deploy = my_flow.to_deployment(
                "hello", tags=["dev"], interval=datetime.timedelta(days=1)
            )

            # Run every Sunday at 4:00 AM
            bye_deploy = my_other_flow.to_deployment(
                "goodbye", tags=["dev"], cron="0 4 * * sun"
            )

            serve(hello_deploy, bye_deploy)
        ```
    """

    from prefect.runner import Runner

    if is_in_async_context():
        raise RuntimeError(
            "Cannot call `serve` in an asynchronous context. Use `aserve` instead."
        )

    runner = Runner(pause_on_shutdown=pause_on_shutdown, limit=limit, **kwargs)
    for deployment in args:
        if deployment.work_pool_name:
            warnings.warn(
                "Work pools are not necessary for served deployments - "
                "the `work_pool_name` argument will be ignored. Omit the "
                f"`work_pool_name` argument from `to_deployment` for {deployment.name!r}.",
                UserWarning,
            )
            deployment.work_pool_name = None
        runner.add_deployment(deployment)

    if print_starting_message:
        _display_serve_start_message(*args)

    try:
        asyncio.run(runner.start())
    except (KeyboardInterrupt, TerminationSignal) as exc:
        logger.info(f"Received {type(exc).__name__}, shutting down...")


async def aserve(
    *args: "RunnerDeployment",
    pause_on_shutdown: bool = True,
    print_starting_message: bool = True,
    limit: Optional[int] = None,
    **kwargs: Any,
) -> None:
    """
    Asynchronously serve the provided list of deployments.

    Use `serve` instead if calling from a synchronous context.

    Args:
        *args: A list of deployments to serve.
        pause_on_shutdown: A boolean for whether or not to automatically pause
            deployment schedules on shutdown.
        print_starting_message: Whether or not to print message to the console
            on startup.
        limit: The maximum number of runs that can be executed concurrently.
        **kwargs: Additional keyword arguments to pass to the runner.

    Examples:
        Prepare deployment and asynchronous initialization function and serve them:

        ```python
        import asyncio
        import datetime

        from prefect import flow, aserve, get_client


        async def init():
            await set_concurrency_limit()


        async def set_concurrency_limit():
            async with get_client() as client:
                await client.create_concurrency_limit(tag='dev', concurrency_limit=3)


        @flow
        async def my_flow(name):
            print(f"hello {name}")


        async def main():
            # Initialization function
            await init()

            # Run once a day
            hello_deploy = await my_flow.to_deployment(
                "hello", tags=["dev"], interval=datetime.timedelta(days=1)
            )

            await aserve(hello_deploy)


        if __name__ == "__main__":
            asyncio.run(main())
    """

    from prefect.runner import Runner

    runner = Runner(pause_on_shutdown=pause_on_shutdown, limit=limit, **kwargs)
    for deployment in args:
        add_deployment_coro = runner.add_deployment(deployment)
        if TYPE_CHECKING:
            assert inspect.isawaitable(add_deployment_coro)

        await add_deployment_coro

    if print_starting_message:
        _display_serve_start_message(*args)

    await runner.start()


def _display_serve_start_message(*args: "RunnerDeployment"):
    from rich.console import Console, Group
    from rich.table import Table

    help_message_top = (
        "[green]Your deployments are being served and polling for scheduled runs!\n[/]"
    )

    table = Table(title="Deployments", show_header=False)

    table.add_column(style="blue", no_wrap=True)

    for deployment in args:
        table.add_row(f"{deployment.flow_name}/{deployment.name}")

    help_message_bottom = (
        "\nTo trigger any of these deployments, use the"
        " following command:\n[blue]\n\t$ prefect deployment run"
        " [DEPLOYMENT_NAME]\n[/]"
    )
    if PREFECT_UI_URL:
        help_message_bottom += (
            "\nYou can also trigger your deployments via the Prefect UI:"
            f" [blue]{PREFECT_UI_URL.value()}/deployments[/]\n"
        )

    console = Console()
    console.print(Group(help_message_top, table, help_message_bottom), soft_wrap=True)


@client_injector
async def load_flow_from_flow_run(
    client: "PrefectClient",
    flow_run: "FlowRun",
    ignore_storage: bool = False,
    storage_base_path: Optional[str] = None,
    use_placeholder_flow: bool = True,
) -> Flow[..., Any]:
    """
    Load a flow from the location/script provided in a deployment's storage document.

    If `ignore_storage=True` is provided, no pull from remote storage occurs.  This flag
    is largely for testing, and assumes the flow is already available locally.
    """
    if flow_run.deployment_id is None:
        raise ValueError("Flow run does not have an associated deployment")

    deployment = await client.read_deployment(flow_run.deployment_id)

    if deployment.entrypoint is None:
        raise ValueError(
            f"Deployment {deployment.id} does not have an entrypoint and can not be run."
        )

    run_logger = flow_run_logger(flow_run)

    runner_storage_base_path = storage_base_path or os.environ.get(
        "PREFECT__STORAGE_BASE_PATH"
    )

    # If there's no colon, assume it's a module path
    if ":" not in deployment.entrypoint:
        run_logger.debug(
            f"Importing flow code from module path {deployment.entrypoint}"
        )
        flow = await run_sync_in_worker_thread(
            load_flow_from_entrypoint,
            deployment.entrypoint,
            use_placeholder_flow=use_placeholder_flow,
        )
        return flow

    if not ignore_storage and not deployment.pull_steps:
        sys.path.insert(0, ".")
        if deployment.storage_document_id:
            storage_document = await client.read_block_document(
                deployment.storage_document_id
            )
            storage_block = Block._from_block_document(storage_document)
        else:
            basepath = deployment.path
            if runner_storage_base_path:
                basepath = str(basepath).replace(
                    "$STORAGE_BASE_PATH", runner_storage_base_path
                )
            storage_block = LocalFileSystem(basepath=basepath)

        from_path = (
            str(deployment.path).replace("$STORAGE_BASE_PATH", runner_storage_base_path)
            if runner_storage_base_path and deployment.path
            else deployment.path
        )
        run_logger.info(f"Downloading flow code from storage at {from_path!r}")
        await storage_block.get_directory(from_path=from_path, local_path=".")

    if deployment.pull_steps:
        run_logger.debug(
            f"Running {len(deployment.pull_steps)} deployment pull step(s)"
        )

        from prefect.deployments.steps.core import StepExecutionError, run_steps

        try:
            output = await run_steps(
                deployment.pull_steps, print_function=run_logger.info
            )
        except StepExecutionError as e:
            e = e.__cause__ or e
            run_logger.error(str(e))
            raise

        if output.get("directory"):
            run_logger.debug(f"Changing working directory to {output['directory']!r}")
            os.chdir(output["directory"])

    import_path = relative_path_to_current_platform(deployment.entrypoint)
    run_logger.debug(f"Importing flow code from '{import_path}'")

    try:
        flow = await run_sync_in_worker_thread(
            load_flow_from_entrypoint,
            str(import_path),
            use_placeholder_flow=use_placeholder_flow,
        )
    except MissingFlowError:
        flow = await run_sync_in_worker_thread(
            load_function_and_convert_to_flow,
            str(import_path),
        )

    return flow


def load_placeholder_flow(entrypoint: str, raises: Exception) -> Flow[P, Any]:
    """
    Load a placeholder flow that is initialized with the same arguments as the
    flow specified in the entrypoint. If called the flow will raise `raises`.

    This is useful when a flow can't be loaded due to missing dependencies or
    other issues but the base metadata defining the flow is still needed.

    Args:
        entrypoint: a string in the format `<path_to_script>:<flow_func_name>`
          or a module path to a flow function
        raises: an exception to raise when the flow is called
    """

    def _base_placeholder():
        raise raises

    def sync_placeholder_flow(*args: "P.args", **kwargs: "P.kwargs"):
        _base_placeholder()

    async def async_placeholder_flow(*args: "P.args", **kwargs: "P.kwargs"):
        _base_placeholder()

    placeholder_flow = (
        async_placeholder_flow
        if is_entrypoint_async(entrypoint)
        else sync_placeholder_flow
    )

    arguments = load_flow_arguments_from_entrypoint(entrypoint)
    arguments["fn"] = placeholder_flow

    return Flow(**arguments)


def safe_load_flow_from_entrypoint(entrypoint: str) -> Optional[Flow[P, Any]]:
    """
    Safely load a Prefect flow from an entrypoint string. Returns None if loading fails.

    Args:
        entrypoint (str): A string identifying the flow to load. Can be in one of the following formats:
            - `<path_to_script>:<flow_func_name>`
            - `<path_to_script>:<class_name>.<flow_method_name>`
            - `<module_path>.<flow_func_name>`

    Returns:
        Optional[Flow]: The loaded Prefect flow object, or None if loading fails due to errors
        (e.g. unresolved dependencies, syntax errors, or missing objects).
    """
    func_or_cls_def, source_code, parts = _entrypoint_definition_and_source(entrypoint)

    path = entrypoint.rsplit(":", maxsplit=1)[0] if ":" in entrypoint else None
    namespace = safe_load_namespace(source_code, filepath=path)

    if parts[0] not in namespace:
        # If the object is not in the namespace, it may be due to missing dependencies
        # in annotations or default values. We will attempt to sanitize them by removing
        # anything that cannot be compiled, and then recompile the function or class.
        if isinstance(func_or_cls_def, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return _sanitize_and_load_flow(func_or_cls_def, namespace)
        elif (
            isinstance(func_or_cls_def, ast.ClassDef)
            and len(parts) >= 2
            and func_or_cls_def.name == parts[0]
        ):
            method_name = parts[1]
            method_def = next(
                (
                    stmt
                    for stmt in func_or_cls_def.body
                    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and stmt.name == method_name
                ),
                None,
            )
            if method_def is not None:
                return _sanitize_and_load_flow(method_def, namespace)
        else:
            return None

    obj = namespace.get(parts[0])
    for part in parts[1:]:
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def _sanitize_and_load_flow(
    func_def: Union[ast.FunctionDef, ast.AsyncFunctionDef], namespace: dict[str, Any]
) -> Optional[Flow[P, Any]]:
    """
    Attempt to load a flow from the function definition after sanitizing the annotations
    and defaults that can't be compiled.

    Args:
        func_def: the function definition
        namespace: the namespace to load the function into

    Returns:
        The loaded function or None if the function can't be loaded
        after sanitizing the annotations and defaults.
    """
    args = func_def.args.posonlyargs + func_def.args.args + func_def.args.kwonlyargs
    if func_def.args.vararg:
        args.append(func_def.args.vararg)
    if func_def.args.kwarg:
        args.append(func_def.args.kwarg)
    # Remove annotations that can't be compiled
    for arg in args:
        if arg.annotation is not None:
            try:
                code = compile(
                    ast.Expression(arg.annotation),
                    filename="<ast>",
                    mode="eval",
                )
                exec(code, namespace)
            except Exception as e:
                logger.debug(
                    "Failed to evaluate annotation for argument %s due to the following error. Ignoring annotation.",
                    arg.arg,
                    exc_info=e,
                )
                arg.annotation = None

    # Remove defaults that can't be compiled
    new_defaults: list[Any] = []
    for default in func_def.args.defaults:
        try:
            code = compile(ast.Expression(default), "<ast>", "eval")
            exec(code, namespace)
            new_defaults.append(default)
        except Exception as e:
            logger.debug(
                "Failed to evaluate default value %s due to the following error. Ignoring default.",
                default,
                exc_info=e,
            )
            new_defaults.append(
                ast.Constant(
                    value=None, lineno=default.lineno, col_offset=default.col_offset
                )
            )
    func_def.args.defaults = new_defaults

    # Remove kw_defaults that can't be compiled
    new_kw_defaults: list[Any] = []
    for default in func_def.args.kw_defaults:
        if default is not None:
            try:
                code = compile(ast.Expression(default), "<ast>", "eval")
                exec(code, namespace)
                new_kw_defaults.append(default)
            except Exception as e:
                logger.debug(
                    "Failed to evaluate default value %s due to the following error. Ignoring default.",
                    default,
                    exc_info=e,
                )
                new_kw_defaults.append(
                    ast.Constant(
                        value=None,
                        lineno=default.lineno,
                        col_offset=default.col_offset,
                    )
                )
        else:
            new_kw_defaults.append(
                ast.Constant(
                    value=None,
                    lineno=func_def.lineno,
                    col_offset=func_def.col_offset,
                )
            )
    func_def.args.kw_defaults = new_kw_defaults

    if func_def.returns is not None:
        try:
            code = compile(
                ast.Expression(func_def.returns), filename="<ast>", mode="eval"
            )
            exec(code, namespace)
        except Exception as e:
            logger.debug(
                "Failed to evaluate return annotation due to the following error. Ignoring annotation.",
                exc_info=e,
            )
            func_def.returns = None

    # Attempt to compile the function without annotations and defaults that
    # can't be compiled
    try:
        code = compile(
            ast.Module(body=[func_def], type_ignores=[]),
            filename="<ast>",
            mode="exec",
        )
        exec(code, namespace)
    except Exception as e:
        logger.debug("Failed to compile: %s", e)
    else:
        return namespace.get(func_def.name)


def load_flow_arguments_from_entrypoint(
    entrypoint: str, arguments: Optional[Union[list[str], set[str]]] = None
) -> dict[str, Any]:
    """
    Extract flow arguments from an entrypoint string.

    Loads the source code of the entrypoint and extracts the flow arguments
    from the `flow` decorator.

    Args:
        entrypoint: a string in the format `<path_to_script>:<flow_func_name>`
          or a module path to a flow function
    """

    func_def, source_code, _ = _entrypoint_definition_and_source(entrypoint)
    path = None
    if ":" in entrypoint:
        path = entrypoint.rsplit(":")[0]

    if arguments is None:
        # If no arguments are provided default to known arguments that are of
        # built-in types.
        arguments = {
            "name",
            "version",
            "retries",
            "retry_delay_seconds",
            "description",
            "timeout_seconds",
            "validate_parameters",
            "persist_result",
            "cache_result_in_memory",
            "log_prints",
        }

    result: dict[str, Any] = {}

    for decorator in func_def.decorator_list:
        if (
            isinstance(decorator, ast.Call)
            and getattr(decorator.func, "id", "") == "flow"
        ):
            for keyword in decorator.keywords:
                if keyword.arg not in arguments:
                    continue

                if isinstance(keyword.value, ast.Constant):
                    # Use the string value of the argument
                    result[cast(str, keyword.arg)] = str(keyword.value.value)
                    continue

                # if the arg value is not a raw str (i.e. a variable or expression),
                # then attempt to evaluate it
                namespace = safe_load_namespace(source_code, filepath=path)
                literal_arg_value = ast.get_source_segment(source_code, keyword.value)
                cleaned_value = (
                    literal_arg_value.replace("\n", "") if literal_arg_value else ""
                )

                try:
                    evaluated_value = eval(cleaned_value, namespace)  # type: ignore
                    result[cast(str, keyword.arg)] = str(evaluated_value)
                except Exception as e:
                    logger.info(
                        "Failed to parse @flow argument: `%s=%s` due to the following error. Ignoring and falling back to default behavior.",
                        keyword.arg,
                        literal_arg_value,
                        exc_info=e,
                    )
                    # ignore the decorator arg and fallback to default behavior
                    continue

    if "name" in arguments and "name" not in result:
        # If no matching decorator or keyword argument for `name' is found
        # fallback to the function name.
        result["name"] = func_def.name.replace("_", "-")

    return result


def is_entrypoint_async(entrypoint: str) -> bool:
    """
    Determine if the function specified in the entrypoint is asynchronous.

    Args:
        entrypoint: A string in the format `<path_to_script>:<func_name>` or
          a module path to a function.

    Returns:
        True if the function is asynchronous, False otherwise.
    """
    func_def, _, _ = _entrypoint_definition_and_source(entrypoint)
    return isinstance(func_def, ast.AsyncFunctionDef)


def _entrypoint_definition_and_source(
    entrypoint: str,
) -> Tuple[Union[ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef], str, List[str]]:
    """
    Resolves and parses the source definition of a given entrypoint.

    The entrypoint can be provided in one of the following formats:
        - '<path_to_script>:<flow_func_name>'
        - '<path_to_script>:<class_name>.<flow_method_name>'
        - '<module_path.to.flow_function>'

    Returns:
        A tuple containing:
        - The AST node (FunctionDef, AsyncFunctionDef, or ClassDef) of the base object.
        - The full source code of the file or module as a string.
        - A list of attribute access parts from the object path (e.g., ['MyFlowClass', 'run']).

    Raises:
        ValueError: If the module or target object cannot be found.
    """
    if ":" in entrypoint:
        path, object_path = entrypoint.rsplit(":", maxsplit=1)
        source_code = Path(path).read_text()
    else:
        path, object_path = entrypoint.rsplit(".", maxsplit=1)
        spec = importlib.util.find_spec(path)
        if not spec or not spec.origin:
            raise ValueError(f"Could not find module {path!r}")
        source_code = Path(spec.origin).read_text()

    parsed_code = ast.parse(source_code)
    parts = object_path.split(".")
    base_name = parts[0]

    base_def = next(
        (
            node
            for node in ast.walk(parsed_code)
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,  # flow can be staticmethod/classmethod
                ),
            )
            and node.name == base_name
        ),
        None,
    )

    if not base_def:
        raise ValueError(f"Could not find object {base_name!r} in {path!r}")

    return base_def, source_code, parts

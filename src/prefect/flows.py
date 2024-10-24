"""
Module containing the base workflow class and decorator - for most use cases, using the [`@flow` decorator][prefect.flows.flow] is preferred.
"""

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
    Dict,
    Generic,
    Iterable,
    List,
    NoReturn,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import UUID

import pydantic
from fastapi.encoders import jsonable_encoder
from pydantic.v1 import BaseModel as V1BaseModel
from pydantic.v1.decorator import ValidatedFunction as V1ValidatedFunction
from pydantic.v1.errors import ConfigError  # TODO
from rich.console import Console
from typing_extensions import Literal, ParamSpec, Self

from prefect._internal.concurrency.api import create_call, from_async
from prefect.blocks.core import Block
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.filters import WorkerFilter
from prefect.client.schemas.objects import ConcurrencyLimitConfig, FlowRun
from prefect.client.schemas.objects import Flow as FlowSchema
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
from prefect.futures import PrefectFuture
from prefect.logging import get_logger
from prefect.logging.loggers import flow_run_logger
from prefect.results import ResultSerializer, ResultStorage
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
    run_sync_in_worker_thread,
    sync_compatible,
)
from prefect.utilities.callables import (
    get_call_parameters,
    parameter_schema,
    parameters_to_args_kwargs,
    raise_for_reserved_arguments,
)
from prefect.utilities.collections import listrepr, visit_collection
from prefect.utilities.filesystem import relative_path_to_current_platform
from prefect.utilities.hashing import file_hash
from prefect.utilities.importtools import import_object, safe_load_namespace

from ._internal.pydantic.v2_schema import is_v2_type
from ._internal.pydantic.v2_validated_func import V2ValidatedFunction
from ._internal.pydantic.v2_validated_func import (
    V2ValidatedFunction as ValidatedFunction,
)

T = TypeVar("T")  # Generic type var for capturing the inner return type of async funcs
R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")  # The parameters of the flow
F = TypeVar("F", bound="Flow")  # The type of the flow

logger = get_logger("flows")

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient
    from prefect.client.types.flexible_schedule_list import FlexibleScheduleList
    from prefect.deployments.runner import RunnerDeployment
    from prefect.flows import FlowRun
    from prefect.runner.storage import RunnerStorage


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
        fn: Callable[P, R],
        name: Optional[str] = None,
        version: Optional[str] = None,
        flow_run_name: Optional[Union[Callable[[], str], str]] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[Union[int, float]] = None,
        task_runner: Union[Type[TaskRunner], TaskRunner, None] = None,
        description: Optional[str] = None,
        timeout_seconds: Union[int, float, None] = None,
        validate_parameters: bool = True,
        persist_result: Optional[bool] = None,
        result_storage: Optional[Union[ResultStorage, str]] = None,
        result_serializer: Optional[ResultSerializer] = None,
        cache_result_in_memory: bool = True,
        log_prints: Optional[bool] = None,
        on_completion: Optional[
            List[Callable[[FlowSchema, FlowRun, State], None]]
        ] = None,
        on_failure: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
        on_cancellation: Optional[
            List[Callable[[FlowSchema, FlowRun, State], None]]
        ] = None,
        on_crashed: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
        on_running: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
    ):
        if name is not None and not isinstance(name, str):
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

        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__.replace("_", "-").replace(
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

        default_task_runner = ThreadPoolTaskRunner()
        task_runner = task_runner or default_task_runner
        self.task_runner = (
            task_runner() if isinstance(task_runner, type) else task_runner
        )

        self.log_prints = log_prints

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn

        # the flow is considered async if its function is async or an async
        # generator
        self.isasync = asyncio.iscoroutinefunction(
            self.fn
        ) or inspect.isasyncgenfunction(self.fn)

        # the flow is considered a generator if its function is a generator or
        # an async generator
        self.isgenerator = inspect.isgeneratorfunction(
            self.fn
        ) or inspect.isasyncgenfunction(self.fn)

        raise_for_reserved_arguments(self.fn, ["return_state", "wait_for"])

        # Version defaults to a hash of the function's file
        flow_file = inspect.getsourcefile(self.fn)
        if not version:
            try:
                version = file_hash(flow_file)
            except (FileNotFoundError, TypeError, OSError):
                pass  # `getsourcefile` can return null values and "<stdin>" for objects in repls
        self.version = version

        self.timeout_seconds = float(timeout_seconds) if timeout_seconds else None

        # FlowRunPolicy settings
        # TODO: We can instantiate a `FlowRunPolicy` and add Pydantic bound checks to
        #       validate that the user passes positive numbers here
        self.retries = (
            retries if retries is not None else PREFECT_FLOW_DEFAULT_RETRIES.value()
        )

        self.retry_delay_seconds = (
            retry_delay_seconds
            if retry_delay_seconds is not None
            else PREFECT_FLOW_DEFAULT_RETRY_DELAY_SECONDS.value()
        )

        self.parameters = parameter_schema(self.fn)
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
        self.on_completion_hooks = on_completion or []
        self.on_failure_hooks = on_failure or []
        self.on_cancellation_hooks = on_cancellation or []
        self.on_crashed_hooks = on_crashed or []
        self.on_running_hooks = on_running or []

        # Used for flows loaded from remote storage
        self._storage: Optional["RunnerStorage"] = None
        self._entrypoint: Optional[str] = None

        module = fn.__module__
        if module in ("__main__", "__prefect_loader__"):
            module_name = inspect.getfile(fn)
            module = module_name if module_name != "__main__" else module

        self._entrypoint = f"{module}:{fn.__name__}"

    @property
    def ismethod(self) -> bool:
        return hasattr(self.fn, "__prefect_self__")

    def __get__(self, instance, owner):
        """
        Implement the descriptor protocol so that the flow can be used as an instance method.
        When an instance method is loaded, this method is called with the "self" instance as
        an argument. We return a copy of the flow with that instance bound to the flow's function.
        """

        # if no instance is provided, it's being accessed on the class
        if instance is None:
            return self

        # if the flow is being accessed on an instance, bind the instance to the __prefect_self__ attribute
        # of the flow's function. This will allow it to be automatically added to the flow's parameters
        else:
            bound_flow = copy(self)
            bound_flow.fn.__prefect_self__ = instance
            return bound_flow

    def with_options(
        self,
        *,
        name: Optional[str] = None,
        version: Optional[str] = None,
        retries: Optional[int] = None,
        retry_delay_seconds: Optional[Union[int, float]] = None,
        description: Optional[str] = None,
        flow_run_name: Optional[Union[Callable[[], str], str]] = None,
        task_runner: Union[Type[TaskRunner], TaskRunner, None] = None,
        timeout_seconds: Union[int, float, None] = None,
        validate_parameters: Optional[bool] = None,
        persist_result: Optional[bool] = NotSet,  # type: ignore
        result_storage: Optional[ResultStorage] = NotSet,  # type: ignore
        result_serializer: Optional[ResultSerializer] = NotSet,  # type: ignore
        cache_result_in_memory: Optional[bool] = None,
        log_prints: Optional[bool] = NotSet,  # type: ignore
        on_completion: Optional[
            List[Callable[[FlowSchema, FlowRun, State], None]]
        ] = None,
        on_failure: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
        on_cancellation: Optional[
            List[Callable[[FlowSchema, FlowRun, State], None]]
        ] = None,
        on_crashed: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
        on_running: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
    ) -> Self:
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
        new_flow = Flow(
            fn=self.fn,
            name=name or self.name,
            description=description or self.description,
            flow_run_name=flow_run_name or self.flow_run_name,
            version=version or self.version,
            task_runner=task_runner or self.task_runner,
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

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters for compatibility with the flow by attempting to cast the inputs to the
        associated types specified by the function's type annotations.

        Returns:
            A new dict of parameters that have been cast to the appropriate types

        Raises:
            ParameterTypeError: if the provided parameters are not valid
        """

        def resolve_block_reference(data: Any) -> Any:
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

        if has_v1_models:
            validated_fn = V1ValidatedFunction(
                self.fn, config={"arbitrary_types_allowed": True}
            )
        else:
            validated_fn = V2ValidatedFunction(
                self.fn, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
            )

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
            if k in model.model_fields_set or model.model_fields[k].default_factory
        }
        return cast_parameters

    def serialize_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parameters to a serializable form.

        Uses FastAPI's `jsonable_encoder` to convert to JSON compatible objects without
        converting everything directly to a string. This maintains basic types like
        integers during API roundtrips.
        """
        serialized_parameters = {}
        for key, value in parameters.items():
            # do not serialize the bound self object
            if self.ismethod and value is self.fn.__prefect_self__:
                continue
            if isinstance(value, (PrefectFuture, State)):
                # Don't call jsonable_encoder() on a PrefectFuture or State to
                # avoid triggering a __getitem__ call
                serialized_parameters[key] = f"<{type(value).__name__}>"
                continue
            try:
                serialized_parameters[key] = jsonable_encoder(value)
            except (TypeError, ValueError):
                logger.debug(
                    f"Parameter {key!r} for flow {self.name!r} is unserializable. "
                    f"Type {type(value).__name__!r} and will not be stored "
                    "in the backend."
                )
                serialized_parameters[key] = f"<{type(value).__name__}>"
        return serialized_parameters

    @sync_compatible
    async def to_deployment(
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
        schedules: Optional["FlexibleScheduleList"] = None,
        concurrency_limit: Optional[Union[int, ConcurrencyLimitConfig, None]] = None,
        parameters: Optional[dict] = None,
        triggers: Optional[List[Union[DeploymentTriggerTypes, TriggerTypes]]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
        enforce_parameter_schema: bool = True,
        work_pool_name: Optional[str] = None,
        work_queue_name: Optional[str] = None,
        job_variables: Optional[Dict[str, Any]] = None,
        entrypoint_type: EntrypointType = EntrypointType.FILE_PATH,
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
            enforce_parameter_schema: Whether or not the Prefect API should enforce the
                parameter schema for the created deployment.
            work_pool_name: The name of the work pool to use for this deployment.
            work_queue_name: The name of the work queue to use for this deployment's scheduled runs.
                If not provided the default work queue for the work pool will be used.
            job_variables: Settings used to override the values specified default base job template
                of the chosen work pool. Refer to the base job template of the chosen work pool for
            entrypoint_type: Type of entrypoint to use for the deployment. When using a module path
                entrypoint, ensure that the module will be importable in the execution environment.

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
            return await RunnerDeployment.from_storage(
                storage=self._storage,
                entrypoint=self._entrypoint,
                name=name,
                flow_name=self.name,
                interval=interval,
                cron=cron,
                rrule=rrule,
                paused=paused,
                schedules=schedules,
                concurrency_limit=concurrency_limit,
                tags=tags,
                triggers=triggers,
                parameters=parameters or {},
                description=description,
                version=version,
                enforce_parameter_schema=enforce_parameter_schema,
                work_pool_name=work_pool_name,
                work_queue_name=work_queue_name,
                job_variables=job_variables,
            )  # type: ignore # TODO: remove sync_compatible
        else:
            return RunnerDeployment.from_flow(
                flow=self,
                name=name,
                interval=interval,
                cron=cron,
                rrule=rrule,
                paused=paused,
                schedules=schedules,
                concurrency_limit=concurrency_limit,
                tags=tags,
                triggers=triggers,
                parameters=parameters or {},
                description=description,
                version=version,
                enforce_parameter_schema=enforce_parameter_schema,
                work_pool_name=work_pool_name,
                work_queue_name=work_queue_name,
                job_variables=job_variables,
                entrypoint_type=entrypoint_type,
            )

    def on_completion(
        self, fn: Callable[["Flow", FlowRun, State], None]
    ) -> Callable[["Flow", FlowRun, State], None]:
        self.on_completion_hooks.append(fn)
        return fn

    def on_cancellation(
        self, fn: Callable[["Flow", FlowRun, State], None]
    ) -> Callable[["Flow", FlowRun, State], None]:
        self.on_cancellation_hooks.append(fn)
        return fn

    def on_crashed(
        self, fn: Callable[["Flow", FlowRun, State], None]
    ) -> Callable[["Flow", FlowRun, State], None]:
        self.on_crashed_hooks.append(fn)
        return fn

    def on_running(
        self, fn: Callable[["Flow", FlowRun, State], None]
    ) -> Callable[["Flow", FlowRun, State], None]:
        self.on_running_hooks.append(fn)
        return fn

    def on_failure(
        self, fn: Callable[["Flow", FlowRun, State], None]
    ) -> Callable[["Flow", FlowRun, State], None]:
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
        schedules: Optional["FlexibleScheduleList"] = None,
        global_limit: Optional[Union[int, ConcurrencyLimitConfig, None]] = None,
        triggers: Optional[List[Union[DeploymentTriggerTypes, TriggerTypes]]] = None,
        parameters: Optional[dict] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
        enforce_parameter_schema: bool = True,
        pause_on_shutdown: bool = True,
        print_starting_message: bool = True,
        limit: Optional[int] = None,
        webserver: bool = False,
        entrypoint_type: EntrypointType = EntrypointType.FILE_PATH,
    ):
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
            # Handling for my_flow.serve(__file__)
            # Will set name to name of file where my_flow.serve() without the extension
            # Non filepath strings will pass through unchanged
            name = Path(name).stem

        runner = Runner(name=name, pause_on_shutdown=pause_on_shutdown, limit=limit)
        deployment_id = runner.add_flow(
            self,
            name=name,
            triggers=triggers,
            interval=interval,
            cron=cron,
            rrule=rrule,
            paused=paused,
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
    @sync_compatible
    async def from_source(
        cls: Type["Flow[P, R]"],
        source: Union[str, "RunnerStorage", ReadableDeploymentStorage],
        entrypoint: str,
    ) -> "Flow[P, R]":
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
                await storage.pull_code()

            full_entrypoint = str(storage.destination / entrypoint)
            flow: Flow = await from_async.wait_for_call_in_new_thread(
                create_call(load_flow_from_entrypoint, full_entrypoint)
            )
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
        job_variables: Optional[dict] = None,
        interval: Optional[Union[int, float, datetime.timedelta]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        paused: Optional[bool] = None,
        schedules: Optional[List[DeploymentScheduleCreate]] = None,
        concurrency_limit: Optional[Union[int, ConcurrencyLimitConfig, None]] = None,
        triggers: Optional[List[Union[DeploymentTriggerTypes, TriggerTypes]]] = None,
        parameters: Optional[dict] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
        enforce_parameter_schema: bool = True,
        entrypoint_type: EntrypointType = EntrypointType.FILE_PATH,
        print_next_steps: bool = True,
        ignore_warnings: bool = False,
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
            schedules: A list of schedule objects defining when to execute runs of this deployment.
                Used to define multiple schedules or additional scheduling options like `timezone`.
            concurrency_limit: The maximum number of runs that can be executed concurrently.
            parameters: A dictionary of default parameter values to pass to runs of this deployment.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            enforce_parameter_schema: Whether or not the Prefect API should enforce the
                parameter schema for the created deployment.
            entrypoint_type: Type of entrypoint to use for the deployment. When using a module path
                entrypoint, ensure that the module will be importable in the execution environment.
            print_next_steps_message: Whether or not to print a message with next steps
                after deploying the deployments.
            ignore_warnings: Whether or not to ignore warnings about the work pool type.

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
                    worker_filter=WorkerFilter(status={"any_": ["ONLINE"]}),
                )
        except ObjectNotFound as exc:
            raise ValueError(
                f"Could not find work pool {work_pool_name!r}. Please create it before"
                " deploying this flow."
            ) from exc

        deployment = await self.to_deployment(
            name=name,
            interval=interval,
            cron=cron,
            rrule=rrule,
            schedules=schedules,
            concurrency_limit=concurrency_limit,
            paused=paused,
            triggers=triggers,
            parameters=parameters,
            description=description,
            tags=tags,
            version=version,
            enforce_parameter_schema=enforce_parameter_schema,
            work_queue_name=work_queue_name,
            job_variables=job_variables,
            entrypoint_type=entrypoint_type,
        )

        from prefect.deployments.runner import deploy

        deployment_ids = await deploy(
            deployment,
            work_pool_name=work_pool_name,
            image=image,
            build=build,
            push=push,
            print_next_steps_message=False,
            ignore_warnings=ignore_warnings,
        )

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
    ) -> Coroutine[Any, Any, T]:
        ...

    @overload
    def __call__(
        self: "Flow[P, T]",
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> Awaitable[State[T]]:
        ...

    @overload
    def __call__(
        self: "Flow[P, T]",
        *args: P.args,
        return_state: Literal[True],
        **kwargs: P.kwargs,
    ) -> State[T]:
        ...

    def __call__(
        self,
        *args: "P.args",
        return_state: bool = False,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
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
    async def visualize(self, *args, **kwargs):
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
                    await self.fn(*args, **kwargs)
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


@overload
def flow(__fn: Callable[P, R]) -> Flow[P, R]:
    ...


@overload
def flow(
    *,
    name: Optional[str] = None,
    version: Optional[str] = None,
    flow_run_name: Optional[Union[Callable[[], str], str]] = None,
    retries: Optional[int] = None,
    retry_delay_seconds: Optional[Union[int, float]] = None,
    task_runner: Optional[TaskRunner] = None,
    description: Optional[str] = None,
    timeout_seconds: Union[int, float, None] = None,
    validate_parameters: bool = True,
    persist_result: Optional[bool] = None,
    result_storage: Optional[ResultStorage] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    log_prints: Optional[bool] = None,
    on_completion: Optional[
        List[Callable[[FlowSchema, FlowRun, State], Union[Awaitable[None], None]]]
    ] = None,
    on_failure: Optional[
        List[Callable[[FlowSchema, FlowRun, State], Union[Awaitable[None], None]]]
    ] = None,
    on_cancellation: Optional[
        List[Callable[[FlowSchema, FlowRun, State], None]]
    ] = None,
    on_crashed: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
    on_running: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
) -> Callable[[Callable[P, R]], Flow[P, R]]:
    ...


def flow(
    __fn=None,
    *,
    name: Optional[str] = None,
    version: Optional[str] = None,
    flow_run_name: Optional[Union[Callable[[], str], str]] = None,
    retries: Optional[int] = None,
    retry_delay_seconds: Union[int, float, None] = None,
    task_runner: Optional[TaskRunner] = None,
    description: Optional[str] = None,
    timeout_seconds: Union[int, float, None] = None,
    validate_parameters: bool = True,
    persist_result: Optional[bool] = None,
    result_storage: Optional[ResultStorage] = None,
    result_serializer: Optional[ResultSerializer] = None,
    cache_result_in_memory: bool = True,
    log_prints: Optional[bool] = None,
    on_completion: Optional[
        List[Callable[[FlowSchema, FlowRun, State], Union[Awaitable[None], None]]]
    ] = None,
    on_failure: Optional[
        List[Callable[[FlowSchema, FlowRun, State], Union[Awaitable[None], None]]]
    ] = None,
    on_cancellation: Optional[
        List[Callable[[FlowSchema, FlowRun, State], None]]
    ] = None,
    on_crashed: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
    on_running: Optional[List[Callable[[FlowSchema, FlowRun, State], None]]] = None,
):
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
        if isinstance(__fn, (classmethod, staticmethod)):
            method_decorator = type(__fn).__name__
            raise TypeError(f"@{method_decorator} should be applied on top of @flow")
        return cast(
            Flow[P, R],
            Flow(
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
            ),
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


# Add from_source so it is available on the flow function we all know and love
flow.from_source = Flow.from_source


def select_flow(
    flows: Iterable[Flow],
    flow_name: Optional[str] = None,
    from_message: Optional[str] = None,
) -> Flow:
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
) -> Flow:
    """
    Extract a flow object from a script at an entrypoint by running all of the code in the file.

    Args:
        entrypoint: a string in the format `<path_to_script>:<flow_func_name>` or a module path
            to a flow function
        use_placeholder_flow: if True, use a placeholder Flow object if the actual flow object
            cannot be loaded from the entrypoint (e.g. dependencies are missing)

    Returns:
        The flow object from the script

    Raises:
        FlowScriptError: If an exception is encountered while running the script
        MissingFlowError: If the flow function specified in the entrypoint does not exist
    """

    if ":" in entrypoint:
        # split by the last colon once to handle Windows paths with drive letters i.e C:\path\to\file.py:do_stuff
        path, func_name = entrypoint.rsplit(":", maxsplit=1)
    else:
        path, func_name = entrypoint.rsplit(".", maxsplit=1)
    try:
        flow = import_object(entrypoint)
    except AttributeError as exc:
        raise MissingFlowError(
            f"Flow function with name {func_name!r} not found in {path!r}. "
        ) from exc
    except ScriptError:
        # If the flow has dependencies that are not installed in the current
        # environment, fallback to loading the flow via AST parsing.
        if use_placeholder_flow:
            flow = safe_load_flow_from_entrypoint(entrypoint)
            if flow is None:
                raise
        else:
            raise

    if not isinstance(flow, Flow):
        raise MissingFlowError(
            f"Function with name {func_name!r} is not a flow. Make sure that it is "
            "decorated with '@flow'."
        )

    return flow


def serve(
    *args: "RunnerDeployment",
    pause_on_shutdown: bool = True,
    print_starting_message: bool = True,
    limit: Optional[int] = None,
    **kwargs,
):
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
    from rich.console import Console, Group
    from rich.table import Table

    from prefect.runner import Runner

    runner = Runner(pause_on_shutdown=pause_on_shutdown, limit=limit, **kwargs)
    for deployment in args:
        runner.add_deployment(deployment)

    if print_starting_message:
        help_message_top = (
            "[green]Your deployments are being served and polling for"
            " scheduled runs!\n[/]"
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
        console.print(
            Group(help_message_top, table, help_message_bottom), soft_wrap=True
        )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError as exc:
        if "no running event loop" in str(exc):
            loop = None
        else:
            raise

    try:
        if loop is not None:
            loop.run_until_complete(runner.start())
        else:
            asyncio.run(runner.start())
    except (KeyboardInterrupt, TerminationSignal) as exc:
        logger.info(f"Received {type(exc).__name__}, shutting down...")
        if loop is not None:
            loop.stop()


@client_injector
async def load_flow_from_flow_run(
    client: "PrefectClient",
    flow_run: "FlowRun",
    ignore_storage: bool = False,
    storage_base_path: Optional[str] = None,
    use_placeholder_flow: bool = True,
) -> Flow:
    """
    Load a flow from the location/script provided in a deployment's storage document.

    If `ignore_storage=True` is provided, no pull from remote storage occurs.  This flag
    is largely for testing, and assumes the flow is already available locally.
    """
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

        from prefect.deployments.steps.core import run_steps

        output = await run_steps(deployment.pull_steps)
        if output.get("directory"):
            run_logger.debug(f"Changing working directory to {output['directory']!r}")
            os.chdir(output["directory"])

    import_path = relative_path_to_current_platform(deployment.entrypoint)
    run_logger.debug(f"Importing flow code from '{import_path}'")

    flow = await run_sync_in_worker_thread(
        load_flow_from_entrypoint,
        str(import_path),
        use_placeholder_flow=use_placeholder_flow,
    )

    return flow


def load_placeholder_flow(entrypoint: str, raises: Exception):
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

    def sync_placeholder_flow(*args, **kwargs):
        _base_placeholder()

    async def async_placeholder_flow(*args, **kwargs):
        _base_placeholder()

    placeholder_flow = (
        async_placeholder_flow
        if is_entrypoint_async(entrypoint)
        else sync_placeholder_flow
    )

    arguments = load_flow_arguments_from_entrypoint(entrypoint)
    arguments["fn"] = placeholder_flow

    return Flow(**arguments)


def safe_load_flow_from_entrypoint(entrypoint: str) -> Optional[Flow]:
    """
    Load a flow from an entrypoint and return None if an exception is raised.

    Args:
        entrypoint: a string in the format `<path_to_script>:<flow_func_name>`
          or a module path to a flow function
    """
    func_def, source_code = _entrypoint_definition_and_source(entrypoint)
    path = None
    if ":" in entrypoint:
        path = entrypoint.rsplit(":")[0]
    namespace = safe_load_namespace(source_code, filepath=path)
    if func_def.name in namespace:
        return namespace[func_def.name]
    else:
        # If the function is not in the namespace, if may be due to missing dependencies
        # for the function. We will attempt to compile each annotation and default value
        # and remove them from the function definition to see if the function can be
        # compiled without them.

        return _sanitize_and_load_flow(func_def, namespace)


def _sanitize_and_load_flow(
    func_def: Union[ast.FunctionDef, ast.AsyncFunctionDef], namespace: Dict[str, Any]
) -> Optional[Flow]:
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
    new_defaults = []
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
    new_kw_defaults = []
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
    entrypoint: str, arguments: Optional[Union[List[str], Set[str]]] = None
) -> dict[str, Any]:
    """
    Extract flow arguments from an entrypoint string.

    Loads the source code of the entrypoint and extracts the flow arguments
    from the `flow` decorator.

    Args:
        entrypoint: a string in the format `<path_to_script>:<flow_func_name>`
          or a module path to a flow function
    """

    func_def, source_code = _entrypoint_definition_and_source(entrypoint)
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

    result = {}

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
                    result[keyword.arg] = str(keyword.value.value)
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
                    result[keyword.arg] = str(evaluated_value)
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
    func_def, _ = _entrypoint_definition_and_source(entrypoint)
    return isinstance(func_def, ast.AsyncFunctionDef)


def _entrypoint_definition_and_source(
    entrypoint: str,
) -> Tuple[Union[ast.FunctionDef, ast.AsyncFunctionDef], str]:
    if ":" in entrypoint:
        # Split by the last colon once to handle Windows paths with drive letters i.e C:\path\to\file.py:do_stuff
        path, func_name = entrypoint.rsplit(":", maxsplit=1)
        source_code = Path(path).read_text()
    else:
        path, func_name = entrypoint.rsplit(".", maxsplit=1)
        spec = importlib.util.find_spec(path)
        if not spec or not spec.origin:
            raise ValueError(f"Could not find module {path!r}")
        source_code = Path(spec.origin).read_text()

    parsed_code = ast.parse(source_code)
    func_def = next(
        (
            node
            for node in ast.walk(parsed_code)
            if isinstance(
                node,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            )
            and node.name == func_name
        ),
        None,
    )

    if not func_def:
        raise ValueError(f"Could not find flow {func_name!r} in {path!r}")

    return func_def, source_code

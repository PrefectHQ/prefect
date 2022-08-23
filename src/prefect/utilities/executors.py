import cloudpickle
import contextlib
import copy
import itertools
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from functools import wraps
from logging import Logger
from queue import Empty

import prefect
from prefect import config
from prefect.client import Client
from prefect.configuration import to_environment_variables
from prefect.exceptions import TaskTimeoutSignal, PrefectSignal
from prefect.utilities.logging import get_logger
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Union,
    Sequence,
    Mapping,
    Iterator,
)

if TYPE_CHECKING:
    import prefect.engine.runner
    import prefect.engine.state
    from prefect.core.edge import Edge
    from prefect.core.task import Task
    from prefect.engine.state import State


StateList = Union["State", List["State"]]

FLOWRUNNER_LOGGER = get_logger("FlowRunner")


def run_with_heartbeat(
    runner_method: Callable[..., "prefect.engine.state.State"]
) -> Callable[..., "prefect.engine.state.State"]:
    """
    Utility decorator for running class methods with a heartbeat.  The class should implement
    `self._heartbeat` with no arguments.
    """

    @wraps(runner_method)
    def inner(
        self: "prefect.engine.cloud.CloudFlowRunner", *args: Any, **kwargs: Any
    ) -> "prefect.engine.state.State":

        try:
            use_heartbeat = self._heartbeat()
        except Exception:
            use_heartbeat = False
            logger = self.logger
            logger.exception(
                "Heartbeat process is misconfigured.  This could result in a zombie run.",
                exc_info=True,
            )

        if not use_heartbeat or (prefect.context.config.cloud.heartbeat_mode == "off"):
            configured_heartbeat = no_heartbeat()
        elif prefect.context.config.cloud.heartbeat_mode == "thread":
            configured_heartbeat = threaded_heartbeat(self.flow_run_id)
        elif prefect.context.config.cloud.heartbeat_mode == "process":
            configured_heartbeat = subprocess_heartbeat(self.heartbeat_cmd, self.logger)
        # because the threaded heartbeat mode is experimental and may change in the future,
        # let's not catch configuration error with `else` -- stale configuration should break tests

        with configured_heartbeat:
            return runner_method(self, *args, **kwargs)

    return inner


@contextlib.contextmanager
def no_heartbeat() -> Iterator[None]:
    # contextlib.nullcontext was introduced in 3.7
    yield


@contextlib.contextmanager
def threaded_heartbeat(flow_run_id: str, num: int = None) -> Iterator[None]:
    try:
        HEARTBEAT_STOP_EVENT = threading.Event()
        heartbeat = HeartbeatThread(HEARTBEAT_STOP_EVENT, flow_run_id, num=None)
        heartbeat.start()
        yield
    finally:
        HEARTBEAT_STOP_EVENT.set()


@contextlib.contextmanager
def subprocess_heartbeat(heartbeat_cmd: List[str], logger: Logger) -> Iterator[None]:
    p = None
    try:
        # we use Popen + a prefect CLI for a few reasons:
        # - using threads would interfere with the task; for example, a task
        #   which does not release the GIL would prevent the heartbeat thread from
        #   firing
        # - using multiprocessing.Process would release the GIL but a subprocess
        #   cannot be spawned from a daemonic subprocess, and Dask sometimes will
        #   submit tasks to run within daemonic subprocesses
        current_env = dict(os.environ).copy()
        current_env.update(
            to_environment_variables(
                prefect.context.config,
                include={
                    "cloud.api_key",
                    "cloud.tenant_id",
                    "cloud.api",
                },
            )
        )
        clean_env = {k: v for k, v in current_env.items() if v is not None}
        p = subprocess.Popen(
            heartbeat_cmd,
            env=clean_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        yield

    except Exception:
        logger.exception(
            "Heartbeat process failed to start.  This could result in a zombie run."
        )

    finally:
        if p is not None:
            exit_code = p.poll()
            if exit_code is not None:
                logger.error(f"Heartbeat process died with exit code {exit_code}")
            p.kill()
            p.wait()


class HeartbeatThread(threading.Thread):
    def __init__(
        self: "HeartbeatThread",
        stop_event: "threading.Event",
        flow_run_id: str,
        num: int = None,
    ) -> None:
        threading.Thread.__init__(self)
        # 'daemonizes' the thread, so it will terminate when all non-daemonized threads have finished
        self.daemon = True
        self.flow_run_id = flow_run_id
        self.num = num
        self.stop_event = stop_event

    def run(self) -> None:
        logger = get_logger("threaded_heartbeat")
        client = Client()
        iter_count = 0
        with prefect.context(
            {"flow_run_id": self.flow_run_id, "running_with_backend": True}
        ):
            with log_heartbeat_failure(logger):
                while iter_count < (self.num or 1) and (
                    self.stop_event.is_set() is False
                ):
                    send_heartbeat(self.flow_run_id, client, logger)
                    iter_count += 1 if self.num else 0
                    self.stop_event.wait(timeout=config.cloud.heartbeat_interval)


def send_heartbeat(
    flow_run_id: str, client: "prefect.client.Client", logger: "logging.Logger"
) -> None:
    try:  # Ignore (but log) client exceptions
        client.update_flow_run_heartbeat(flow_run_id)
    except Exception as exc:
        logger.error(
            f"Failed to send heartbeat with exception: {exc!r}",
            exc_info=True,
        )


@contextmanager
def log_heartbeat_failure(
    logger: "logging.Logger",
) -> Iterator[None]:
    try:
        yield
    except BaseException as exc:
        logger.error(
            f"Heartbeat process encountered terminal exception: {exc!r}",
            exc_info=True,
        )
        raise


def run_with_thread_timeout(
    fn: Callable,
    args: Sequence = (),
    kwargs: Mapping = None,
    timeout: int = None,
    logger: Logger = None,
    name: str = None,
) -> Any:
    """
    Helper function for implementing timeouts on function executions.
    Implemented by setting a `signal` alarm on a timer. Must be run in the main thread.

    Args:
        - fn (callable): the function to execute
        - args (Sequence): arguments to pass to the function
        - kwargs (Mapping): keyword arguments to pass to the function
        - timeout (int): the length of time to allow for execution before raising a
            `TaskTimeoutSignal`, represented as an integer in seconds
        - logger (Logger): an optional logger to use. If not passed, a logger for the
            `prefect.executors.run_with_thread_timeout` namespace will be created.
        - name (str): an optional name to attach to logs for this function run, defaults
            to the name of the given function. Provides an interface for passing task
            names for logs.

    Returns:
        - the result of `fn(*args, **kwargs)`

    Raises:
        - TaskTimeoutSignal: if function execution exceeds the allowed timeout
        - ValueError: if run from outside the main thread
    """
    logger = logger or get_logger()
    name = name or f"Function '{fn.__name__}'"
    kwargs = kwargs or {}

    if timeout is None:
        return fn(*args, **kwargs)

    def error_handler(signum, frame):  # type: ignore
        raise TaskTimeoutSignal("Execution timed out.")

    try:
        # Set the signal handler for alarms
        signal.signal(signal.SIGALRM, error_handler)
        # Raise the alarm if `timeout` seconds pass
        logger.debug(f"{name}: Sending alarm with {timeout}s timeout...")
        signal.alarm(timeout)
        logger.debug(f"{name}: Executing function in main thread...")
        return fn(*args, **kwargs)
    finally:
        signal.alarm(0)


def multiprocessing_safe_run_and_retrieve(
    queue: multiprocessing.Queue,
    payload: bytes,
) -> None:
    """
    Gets the return value from a function and puts it in a multiprocessing-safe
    container. Helper function for `run_with_multiprocess_timeout`, must be defined
    top-level so it can be pickled and sent to `multiprocessing.Process`

    Passing the payload serialized allows us to escape the limitations of the python
    native pickler which will fail on tasks defined in scripts because of name
    mismatches. Whilst this particular example only affects the `func` arg, any of the
    others could be affected by other pickle limitations as well.

    Args:
        - queue (multiprocessing.Queue): The queue to pass the resulting payload to
        - payload (bytes): A serialized dictionary containing the data required to run
            the function. Should be serialized with `cloudpickle.dumps`
            Expects the following keys:
            - fn (Callable): The function to call
            - args (list): Positional argument values to call the function with
            - kwargs (Mapping): Keyword arguments to call the function with
            - context (dict): The prefect context dictionary to use during execution
            - name (str): an optional name to attach to logs for this function run,
                defaults to the name of the given function. Provides an interface for
                passing task names for logs.
            - logger (Logger): the logger to use
    """
    request = cloudpickle.loads(payload)

    fn: Callable = request["fn"]
    context: dict = request.get("context", {})
    args: Sequence = request.get("args", [])
    kwargs: Mapping = request.get("kwargs", {})
    name: str = request.get("name", f"Function '{fn.__name__}'")
    logger: Logger = request.get("logger") or get_logger()

    try:
        with prefect.context(context):
            logger.debug(f"{name}: Executing...")
            return_val = fn(*args, **kwargs)
            logger.debug(f"{name}: Execution successful.")
    except PrefectSignal as exc:
        # We need to ensure PrefectSignals are captured and put in the
        # queue correctly, otherwise no value is returned and
        # the task runner assumes execution has timed out
        return_val = exc
        logger.error(
            f"{name}: Encountered a PrefectSignal {type(exc).__name__}, "
            f"returning details as a result..."
        )
    except Exception as exc:
        return_val = exc
        logger.error(
            f"{name}: Encountered a {type(exc).__name__}, "
            f"returning details as a result..."
        )

    try:
        logger.debug(
            "%s: Pickling value of size %s...", name, sys.getsizeof(return_val, -1)
        )  # Only calculate the size if debug logs are enabled
        pickled_val = cloudpickle.dumps(return_val)
        logger.debug(f"{name}: Pickling successful!")
    except Exception as exc:
        err_msg = (
            f"Failed to pickle result of type {type(return_val).__name__!r} with "
            f'exception: "{type(exc).__name__}: {str(exc)}". This timeout handler "'
            "requires your function return value to be serializable with `cloudpickle`."
        )
        logger.error(f"{name}: {err_msg}")
        pickled_val = cloudpickle.dumps(RuntimeError(err_msg))

    logger.debug(f"{name}: Passing result back to main process...")

    try:
        queue.put(pickled_val)
    except Exception:
        logger.error(
            f"{name}: Failed to put result in queue to main process!",
            exc_info=True,
        )
        raise


def run_with_multiprocess_timeout(
    fn: Callable,
    args: Sequence = (),
    kwargs: Mapping = None,
    timeout: int = None,
    logger: Logger = None,
    name: str = None,
) -> Any:
    """
    Helper function for implementing timeouts on function executions.

    Implemented by spawning a new multiprocess.Process() and using a queue to pass
    the result back. The result is retrieved from the queue with a timeout.

    Args:
        - fn (callable): the function to execute
        - args (Sequence): arguments to pass to the function
        - kwargs (Mapping): keyword arguments to pass to the function
        - timeout (int): the length of time to allow for execution before raising a
            `TaskTimeoutSignal`, represented as an integer in seconds
        - logger (Logger): an optional logger to use. If not passed, a logger for the
            `prefect.` namespace will be created.
        - name (str): an optional name to attach to logs for this function run, defaults
            to the name of the given function. Provides an interface for passing task
            names for logs.

    Returns:
        - the result of `f(*args, **kwargs)`

    Raises:
        - Exception: Any user errors within the subprocess will be pickled and reraised
        - AssertionError: if run from a daemonic process
        - TaskTimeoutSignal: if function execution exceeds the allowed timeout
    """
    logger = logger or get_logger()
    name = name or f"Function '{fn.__name__}'"
    kwargs = kwargs or {}

    if timeout is None:
        return fn(*args, **kwargs)

    spawn_mp = multiprocessing.get_context("spawn")

    # Create a queue to pass the function return value back
    queue = spawn_mp.Queue()  # type: multiprocessing.Queue

    # Set internal kwargs for the helper function
    request = {
        "fn": fn,
        "args": args,
        "kwargs": kwargs,
        "context": prefect.context.to_dict(),
        "name": name,
        "logger": logger,
    }
    payload = cloudpickle.dumps(request)

    run_process = spawn_mp.Process(
        target=multiprocessing_safe_run_and_retrieve,
        args=(queue, payload),
    )
    logger.debug(f"{name}: Sending execution to a new process...")
    run_process.start()
    logger.debug(f"{name}: Waiting for process to return with {timeout}s timeout...")

    # Pull the data from the queue. If empty, the function did not finish before
    # the timeout
    try:
        pickled_result = queue.get(block=True, timeout=timeout)
        logger.debug(f"{name}: Result received from subprocess, unpickling...")
        result = cloudpickle.loads(pickled_result)
        if isinstance(result, (Exception, PrefectSignal)):
            raise result
        return result
    except Empty:
        logger.debug(f"{name}: No result returned within the timeout period!")
        raise TaskTimeoutSignal(f"Execution timed out for {name}.")
    finally:
        # Do not let the process dangle
        run_process.join(0.1)
        run_process.terminate()


def run_task_with_timeout(
    task: "Task",
    args: Sequence = (),
    kwargs: Mapping = None,
    logger: Logger = None,
) -> Any:
    """
    Helper function for implementing timeouts on task executions.

    The exact implementation varies depending on whether this function is being
    run in the main thread or a non-daemonic subprocess.  If this is run from a
    daemonic subprocess or on Windows, the task is run in a `ThreadPoolExecutor`
    and only a soft timeout is enforced, meaning a `TaskTimeoutSignal` is raised at the
    appropriate time but the task continues running in the background.

    The task is passed instead of a function so we can give better logs and messages.
    If you need to run generic functions with timeout handlers,
    `run_with_thread_timeout` or `run_with_multiprocess_timeout` can be called directly

    Args:
        - task (Task): the task to execute
            `task.timeout` specifies the number of seconds to allow `task.run` to run
            for before terminating
        - args (Sequence): arguments to pass to the function
        - kwargs (Mapping): keyword arguments to pass to the function
        - logger (Logger): an optional logger to use. If not passed, a logger for the
            `prefect.run_task_with_timeout_handler` namespace will be created.

    Returns:
        - the result of `f(*args, **kwargs)`

    Raises:
        - TaskTimeoutSignal: if function execution exceeds the allowed timeout
    """
    logger = logger or get_logger()
    name = prefect.context.get("task_full_name", task.name)
    kwargs = kwargs or {}

    # if no timeout, just run the function
    if task.timeout is None:
        return task.run(*args, **kwargs)  # type: ignore

    # if we are running the main thread, use a signal to stop execution at the
    # appropriate time; else if we are running in a non-daemonic process, spawn
    # a subprocess to kill at the appropriate time
    if not sys.platform.startswith("win"):

        if threading.current_thread() is threading.main_thread():
            # This case is typically encountered when using a non-parallel or local
            # multiprocess scheduler because then each worker is in the main
            # thread
            logger.debug(f"Task '{name}': Attaching thread based timeout handler...")
            return run_with_thread_timeout(
                task.run,
                args,
                kwargs,
                timeout=task.timeout,
                logger=logger,
                name=f"Task '{name}'",
            )

        elif multiprocessing.current_process().daemon is False:
            # This case is typically encountered when using a multithread distributed
            # executor
            logger.debug(f"Task '{name}': Attaching process based timeout handler...")
            return run_with_multiprocess_timeout(
                task.run,
                args,
                kwargs,
                timeout=task.timeout,
                logger=logger,
                name=f"Task '{name}'",
            )

        # We are in a daemonic process and cannot enforce a timeout
        # This case is typically encountered when using a multiprocess distributed
        # executor
        soft_timeout_reason = "in a daemonic subprocess"
    else:
        # We are in windows and cannot enforce a timeout
        soft_timeout_reason = "on Windows"

    msg = (
        f"This task is running {soft_timeout_reason}; "
        "consequently Prefect can only enforce a soft timeout limit, i.e., "
        "if your Task reaches its timeout limit it will enter a TimedOut state "
        "but continue running in the background."
    )

    logger.debug(
        f"Task '{name}': Falling back to daemonic soft limit timeout handler because "
        f"we are running {soft_timeout_reason}."
    )
    warnings.warn(msg, stacklevel=2)
    executor = ThreadPoolExecutor()

    def run_with_ctx(context: dict) -> Any:
        with prefect.context(context):
            return task.run(*args, **kwargs)  # type: ignore

    # Run the function in the background and then retrieve its result with a timeout
    fut = executor.submit(run_with_ctx, prefect.context.to_dict())

    try:
        return fut.result(timeout=task.timeout)
    except FutureTimeout as exc:
        raise TaskTimeoutSignal(
            f"Execution timed out but was executed {soft_timeout_reason} and will "
            "continue to run in the background."
        ) from exc


class RecursiveCall(Exception):
    def __init__(self, func: Callable, *args: Any, **kwargs: Any):
        self.func = func
        self.args = args
        self.kwargs = kwargs


def tail_recursive(func: Callable) -> Callable:
    """
    Helper function to facilitate tail recursion of the wrapped function.

    This allows for recursion with unlimited depth since a stack is not allocated for
    each "nested" call. Note: instead of calling the target function in question, a
    `RecursiveCall` exception must be raised instead.

    Args:
        - fn (callable): the function to execute

    Returns:
        - the result of `f(*args, **kwargs)`

    Raises:
        - RecursionError: if a recursive "call" (raised exception) is made with a function that is
            not decorated with `tail_recursive` decorator.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        while True:
            try:
                return func(*args, **kwargs)
            except RecursiveCall as exc:
                try:
                    call_func = getattr(exc.func, "__wrapped_func__")
                except AttributeError as attr_error:
                    raise RecursionError(
                        "function has not been wrapped to provide tail recursion (func={})".format(
                            exc.func
                        )
                    ) from attr_error

                # there may be multiple nested recursive calls, we should only
                # respond to calls for the wrapped function explicitly,
                # otherwise allow the call to continue to propagate
                if call_func != func:
                    raise exc
                args = exc.args
                kwargs = exc.kwargs
                continue

    setattr(wrapper, "__wrapped_func__", func)
    return wrapper


def prepare_upstream_states_for_mapping(
    state: "State",
    upstream_states: "Dict[Edge, State]",
    mapped_children: "Dict[Task, list]",
    executor: "prefect.executors.Executor",
) -> list:
    """
    If the task is being mapped, submits children tasks for execution. Returns a `Mapped` state.

    Args:
        - state (State): the parent task's current state
        - upstream_states (Dict[Edge, State]): the upstream states to this task
        - mapped_children (Dict[Task, List[State]]): any mapped children upstream of this task

    Returns:
        - List: a restructured list of upstream states correponding to each new mapped child task
    """

    # if the current state is failed / skipped or otherwise
    # in a state that signifies we should not continue with mapping,
    # we return an empty list
    if state.is_pending() or state.is_failed() or state.is_skipped():
        return []

    map_upstream_states = []

    # copy the mapped children dict to avoid mutating the global one
    # when we flatten mapped children
    mapped_children = mapped_children.copy()

    # we don't know how long the iterables are, but we want to iterate until we reach
    # the end of the shortest one
    counter = itertools.count()

    # preprocessing
    for edge, upstream_state in upstream_states.items():

        # ensure we are working with populated result objects
        if edge.key in state.cached_inputs:
            upstream_state._result = state.cached_inputs[edge.key]

        # if the upstream was mapped and the edge is flattened, we need
        # to process the mapped children (which could be futures) into a
        # flat structure
        if upstream_state.is_mapped() and edge.flattened:
            mapped_children[edge.upstream_task] = flatten_mapped_children(
                mapped_children=mapped_children[edge.upstream_task], executor=executor
            )

    # infinite loop, if upstream_states has any entries
    while True and upstream_states:
        i = next(counter)
        states = {}
        try:

            for edge, upstream_state in upstream_states.items():

                # if the edge is not mapped over, then we take its state
                if not edge.mapped:
                    states[edge] = upstream_state

                # if the edge is mapped and the upstream state is Mapped, then we are mapping
                # over a mapped task. In this case, we take the appropriately-indexed upstream
                # state from the upstream tasks's `Mapped.map_states` array.
                # Note that these "states" might actually be futures at this time; we aren't
                # blocking until they finish.
                elif edge.mapped and upstream_state.is_mapped():
                    states[edge] = mapped_children[edge.upstream_task][i]  # type: ignore

                # Otherwise, we are mapping over the result of a "vanilla" task. In this
                # case, we create a copy of the upstream state but set the result to the
                # appropriately-indexed item from the upstream task's `State.result`
                # array.
                else:
                    states[edge] = copy.copy(upstream_state)

                    # if the current state is already Mapped, then we might be executing
                    # a re-run of the mapping pipeline. In that case, the upstream states
                    # might not have `result` attributes.
                    # Therefore, we only try to get a result if EITHER this task's
                    # state is not already mapped OR the upstream result is not None.
                    if (
                        not state.is_mapped()
                        or upstream_state._result != prefect.engine.result.NoResult
                    ):
                        if not hasattr(upstream_state.result, "__getitem__"):
                            value = None
                        else:
                            value = upstream_state.result[i]
                        upstream_result = upstream_state._result.from_value(value)  # type: ignore
                        states[edge].result = upstream_result
                        if state.map_states and i >= len(state.map_states):  # type: ignore
                            raise IndexError()
                    elif state.is_mapped():
                        if i >= len(state.map_states):  # type: ignore
                            raise IndexError()

            # only add this iteration if we made it through all iterables
            map_upstream_states.append(states)

        # index error means we reached the end of the shortest iterable
        except IndexError:
            break

    return map_upstream_states


def _should_flatten(state: "State") -> bool:
    return state.is_successful() and not state.is_skipped()


def _can_flatten(state: "State") -> bool:
    return hasattr(state.result, "__len__") and hasattr(state.result, "__getitem__")


def _build_flattened_state(state: "State", index: int) -> "State":
    """Helper function for `flatten_upstream_state`"""
    if not _should_flatten(state):
        return state

    new_state = copy.copy(state)
    if not _can_flatten(state):
        message = (
            "`flatten` was used on upstream task that did not return an iterable. "
            "The value will be passed downstream unmodified."
        )
        FLOWRUNNER_LOGGER.warning(message)
        new_state.result = state._result.from_value(state.result)  # type: ignore
    else:
        new_state.result = state._result.from_value(state.result[index])  # type: ignore

    return new_state


def flatten_upstream_state(upstream_state: "State") -> "State":
    """
    Given an upstream state, returns its result as a flattened list. If
    flattening fails, the object is returned unmodified.
    """
    try:
        # attempt to unnest
        flattened_result = [y for x in upstream_state.result for y in x]
    except TypeError:
        return upstream_state

    new_state = copy.copy(upstream_state)
    new_state.result = new_state._result.from_value(flattened_result)  # type: ignore
    return new_state


def flatten_mapped_children(
    mapped_children: List["State"],
    executor: "prefect.executors.Executor",
) -> List["State"]:
    counts = executor.wait(
        [
            executor.submit(lambda c: len(c._result.value) if _can_flatten(c) else 1, c)
            for c in mapped_children
        ]
    )
    new_states = []

    for child, count in zip(mapped_children, counts):
        new_states.append(
            [executor.submit(_build_flattened_state, child, i) for i in range(count)]
        )

    flattened_states = [i for s in new_states for i in s]
    return flattened_states

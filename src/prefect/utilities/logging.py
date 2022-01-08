import atexit
import logging
import logging.config
import logging.handlers
import os
import queue
import re
import sys
import threading
import time
import traceback
from functools import lru_cache, partial
from pathlib import Path
from pprint import pformat
from typing import TYPE_CHECKING, List

import anyio
import pendulum
import yaml
from fastapi.encoders import jsonable_encoder

import prefect
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict
from prefect.utilities.settings import LoggingSettings, Settings

if TYPE_CHECKING:
    from prefect.context import RunContext
    from prefect.flows import Flow
    from prefect.orion.schemas.core import FlowRun, TaskRun
    from prefect.orion.schemas.actions import LogCreate
    from prefect.tasks import Task


# This path will be used if `LoggingSettings.settings_path` does not exist
DEFAULT_LOGGING_SETTINGS_PATH = Path(__file__).parent / "logging.yml"

# Regex call to replace non-alphanumeric characters to '_' to create a valid env var
to_envvar = partial(re.sub, re.compile(r"[^0-9a-zA-Z]+"), "_")
# Regex for detecting interpolated global settings
interpolated_settings = re.compile(r"^{{([\w\d_]+)}}$")


def load_logging_config(path: Path, settings: LoggingSettings) -> dict:
    """
    Loads logging configuration from a path allowing override from the environment
    """
    config = yaml.safe_load(path.read_text())

    # Load overrides from the environment
    flat_config = dict_to_flatdict(config)

    for key_tup, val in flat_config.items():

        # first check if the value was overriden via env var
        env_val = os.environ.get(
            # Generate a valid environment variable with nesting indicated with '_'
            to_envvar((settings.Config.env_prefix + "_".join(key_tup)).upper())
        )
        if env_val:
            val = env_val

        # next check if the value refers to a global setting
        # only perform this check if the value is a string beginning with '{{'
        if isinstance(val, str) and val.startswith(r"{{"):
            # this regex looks for `{{KEY}}`
            # and returns `KEY` as its first capture group
            matched_settings = interpolated_settings.match(val)
            if matched_settings:
                # retrieve the matched key
                matched_key = matched_settings.group(1)
                # retrieve the global logging setting corresponding to the key
                val = getattr(settings, matched_key, None)

        # reassign the updated value
        flat_config[key_tup] = val

    return flatdict_to_dict(flat_config)


def setup_logging(settings: Settings) -> None:

    # If the user has specified a logging path and it exists we will ignore the
    # default entirely rather than dealing with complex merging
    config = load_logging_config(
        (
            settings.logging.settings_path
            if settings.logging.settings_path.exists()
            else DEFAULT_LOGGING_SETTINGS_PATH
        ),
        settings.logging,
    )

    logging.config.dictConfig(config)


@lru_cache()
def get_logger(name: str = None) -> logging.Logger:
    """
    Get a `prefect` logger. For use within Prefect.
    """

    parent_logger = logging.getLogger("prefect")

    if name:
        # Append the name if given but allow explicit full names e.g. "prefect.test"
        # should not become "prefect.prefect.test"
        if not name.startswith(parent_logger.name + "."):
            logger = parent_logger.getChild(name)
        else:
            logger = logging.getLogger(name)
    else:
        logger = parent_logger

    return logger


def get_run_logger(context: "RunContext" = None, **kwargs: str) -> logging.Logger:
    """
    Get a Prefect logger for the current task run or flow run.

    The logger will be named either `prefect.task_runs` or `prefect.flow_runs`.
    Contextual data about the run will be attached to the log records.

    Arguments:
        context: A specific context may be provided as an override. By default, the
            context is inferred from global state and this should not be needed.
        **kwargs: Additional keyword arguments will be attached to the log records in
            addition to the run metadata

    Raises:
        RuntimeError: If no context can be found
    """
    # Check for existing contexts
    task_run_context = prefect.context.TaskRunContext.get()
    flow_run_context = prefect.context.FlowRunContext.get()

    # Apply the context override
    if context:
        if isinstance(context, prefect.context.FlowRunContext):
            flow_run_context = context
        elif isinstance(context, prefect.context.TaskRunContext):
            task_run_context = context

    # Determine if this is a task or flow run logger
    if task_run_context:
        logger = task_run_logger(
            task_run=task_run_context.task_run,
            task=task_run_context.task,
            flow_run=flow_run_context.flow_run if flow_run_context else None,
            flow=flow_run_context.flow if flow_run_context else None,
            **kwargs,
        )
    elif flow_run_context:
        logger = flow_run_logger(
            flow_run=flow_run_context.flow_run, flow=flow_run_context.flow, **kwargs
        )
    else:
        raise RuntimeError("There is no active flow or task run context.")

    return logger


def flow_run_logger(flow_run: "FlowRun", flow: "Flow" = None, **kwargs: str):
    """
    Create a flow run logger with the run's metadata attached.

    Additional keyword arguments can be provided to attach custom data to the log
    records.

    If the context is available, see `run_logger` instead.
    """
    return PrefectLogAdapter(
        get_logger("prefect.flow_runs"),
        extra={
            **{
                "flow_run_name": flow_run.name,
                "flow_run_id": str(flow_run.id),
                "flow_name": flow.name if flow else "<unknown>",
            },
            **kwargs,
        },
    )


def task_run_logger(
    task_run: "TaskRun",
    task: "Task" = None,
    flow_run: "FlowRun" = None,
    flow: "Flow" = None,
    **kwargs: str,
):
    """
    Create a task run logger with the run's metadata attached.

    Additional keyword arguments can be provided to attach custom data to the log
    records.

    If the context is available, see `run_logger` instead.
    """
    return PrefectLogAdapter(
        get_logger("prefect.task_runs"),
        extra={
            **{
                "task_run_id": str(task_run.id),
                "flow_run_id": str(task_run.flow_run_id),
                "task_run_name": task_run.name,
                "task_name": task.name if task else "<unknown>",
                "flow_run_name": flow_run.name if flow_run else "<unknown>",
                "flow_name": flow.name if flow else "<unknown>",
            },
            **kwargs,
        },
    )


class PrefectLogAdapter(logging.LoggerAdapter):
    """
    Adapter that ensures extra kwargs are passed through correctly; without this
    the `extra` fields set on the adapter would overshadow any provided on a
    log-by-log basis.
    """

    def process(self, msg, kwargs):
        kwargs["extra"] = {**self.extra, **(kwargs.get("extra") or {})}
        return (msg, kwargs)


class OrionLogWorker:
    """
    Manages the submission of logs to Orion.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[dict] = queue.Queue()
        self._send_thread = threading.Thread(
            target=self._send_logs_loop,
            name="orion-log-worker",
            daemon=True,
        )
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._started = False

        # Tracks logs that have been pulled from the queue but not sent successfully
        self._pending_logs: List[dict] = []
        self._pending_size: int = 0

        # We must defer this import to avoid circular imports
        from prefect.client import OrionClient

        self.client_cls = OrionClient

        # Ensure stop is called at exit
        if sys.version_info < (3, 9):
            atexit.register(self.stop)
        else:
            # See related issue at https://bugs.python.org/issue42647
            # The http client uses a thread pool executor to make requests and in 3.9+
            # new threads cannot be spawned after the interpreter finalizes threads
            # which happens _before_ the normal `atexit` hook is called resulting in
            # the failure to send logs.
            from threading import _register_atexit

            _register_atexit(self.stop)

    def _send_logs_loop(self):
        """
        Should only be the target of the `send_thread` as it creates a new event loop.

        Runs until the `stop_event` is set.
        """
        while not self._stop_event.wait(prefect.settings.logging.orion.batch_interval):
            anyio.run(self.send_logs)

        # After the stop event, we are exiting...
        # Try to send any remaining logs
        anyio.run(self.send_logs, True)

    async def send_logs(self, exiting: bool = False) -> None:
        """
        Send all logs in the queue in batches to avoid network limits.

        If a client error is encountered, the logs pulled from the queue are retained
        and will be sent on the next call.

        Note that if there is a single bad log in the queue, this will repeatedly
        fail as we do not ever drop logs. We may want to adjust this behavior in the
        future if there are issues.
        """
        done = False

        # Determine the batch size by removing the max size of a single log to avoid
        # exceeding the max size in normal operation. If the single log size is greater
        # than this difference, we use that instead so logs will still be sent.
        max_batch_size = max(
            prefect.settings.logging.orion.batch_size
            - prefect.settings.logging.orion.max_log_size,
            prefect.settings.logging.orion.max_log_size,
        )

        # Loop until the queue is empty or we encounter an error
        while not done:

            # Pull logs from the queue until it is empty or we reach the batch size
            try:
                while self._pending_size < max_batch_size:
                    log = self._queue.get_nowait()
                    self._pending_logs.append(log)
                    self._pending_size += sys.getsizeof(log)

                    # Ensure that we do not add another log if we have reached the max
                    # size already
                    if self._pending_size > max_batch_size:
                        break

            except queue.Empty:
                done = True

            if not self._pending_logs:
                continue

            async with self.client_cls() as client:
                try:
                    await client.create_logs(self._pending_logs)
                    self._pending_logs = []
                    self._pending_size = 0
                except Exception:
                    # Attempt to send these logs on the next call instead
                    done = True

                    # Roughly replicate the behavior of the stdlib logger error handling
                    if logging.raiseExceptions and sys.stderr:
                        sys.stderr.write("--- Orion logging error ---\n")
                        traceback.print_exc(file=sys.stderr)
                        sys.stderr.write(self.worker_info())
                        if exiting:
                            sys.stderr.write(
                                "The log worker is stopping and these logs will not be sent.\n"
                            )
                        else:
                            sys.stderr.write(
                                "The log worker will attempt to send these logs again in "
                                f"{prefect.settings.logging.orion.batch_interval}s\n"
                            )

    def worker_info(self) -> str:
        """Returns a debugging string with worker log stats"""
        return (
            "Worker information:\n"
            f"    Approximate queue length: {self._queue.qsize()}\n"
            f"    Pending log batch length: {len(self._pending_logs)}\n"
            f"    Pending log batch size: {self._pending_size}\n"
        )

    def enqueue(self, log: "LogCreate"):
        self._queue.put(log)

    def start(self) -> None:
        """Start the background thread"""
        with self._lock:
            if not self._started:
                self._send_thread.start()
                self._started = True

    def stop(self) -> None:
        """Flush all logs and stop the background thread"""
        with self._lock:
            if self._started:
                self._stop_event.set()
                self._send_thread.join()
                self._started = False


class OrionHandler(logging.Handler):
    worker: OrionLogWorker = None

    @classmethod
    def get_worker(cls) -> OrionLogWorker:
        if not cls.worker:
            cls.worker = OrionLogWorker()
            cls.worker.start()
        return cls.worker

    @classmethod
    def flush(cls):
        if cls.worker:
            cls.worker.stop()

    def emit(self, record: logging.LogRecord):
        try:
            if not prefect.settings.logging.orion.enabled:
                return  # Respect the global settings toggle
            if not getattr(record, "send_to_orion", True):
                return  # Do not send records that have opted out
            self.get_worker().enqueue(self.prepare(record))
        except Exception:
            self.handleError(record)

    def prepare(self, record: logging.LogRecord) -> "LogCreate":
        flow_run_id = getattr(record, "flow_run_id", None)
        task_run_id = getattr(record, "task_run_id", None)

        if not flow_run_id:
            try:
                context = prefect.context.get_run_context()
            except:
                raise RuntimeError(
                    "Attempted to send logs to Orion without a flow run id. The "
                    "Orion log handler must be attached to loggers used within flow "
                    "run contexts or the flow run id must be manually provided."
                )

            if hasattr(context, "flow_run"):
                flow_run_id = context.flow_run.id
            elif hasattr(context, "task_run"):
                flow_run_id = context.task_run.flow_run_id
                task_run_id = task_run_id or context.task_run.id
            else:
                raise ValueError(
                    "Encountered malformed run context. Does not contain flow or task "
                    "run information."
                )

        # Parsing to a `LogCreate` object here gives us nice parsing error messages
        # from the standard lib `handleError` method if something goes wrong and
        # prevents malformed logs from entering the queue
        from prefect.orion.schemas.actions import LogCreate

        log = LogCreate(
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
            name=record.name,
            level=record.levelno,
            timestamp=pendulum.from_timestamp(
                getattr(record, "created", None) or time.time()
            ),
            message=record.getMessage(),
        ).dict(json_compatible=True)

        log_size = sys.getsizeof(log)
        if log_size > prefect.settings.logging.orion.max_log_size:
            raise ValueError(
                f"Log of size {log_size} is greater than the max size of "
                f"{prefect.settings.logging.orion.max_log_size}"
            )

        return log

    def close(self) -> None:
        if self.worker:
            self.worker.stop()
        return super().close()


def safe_jsonable(obj):
    try:
        return jsonable_encoder(obj)
    except:
        return "<unserializable>"


class JsonFormatter(logging.Formatter):
    def __init__(self, fmt, dmft, style) -> None:
        if fmt not in ["pretty", "default"]:
            raise ValueError("Format must be either 'pretty' or 'default'.")
        self.fmt = fmt

    def format(self, record: logging.LogRecord):
        format_fn = pformat if self.fmt == "pretty" else str
        return format_fn(
            {key: safe_jsonable(val) for key, val in record.__dict__.items()}
        )

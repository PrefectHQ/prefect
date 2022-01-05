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
    from prefect.context import FlowRunContext, RunContext, TaskRunContext
    from prefect.flows import Flow
    from prefect.orion.schemas.core import FlowRun, TaskRun
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


def run_logger(context: "RunContext" = None, **kwargs: str) -> logging.Logger:
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
    return logging.LoggerAdapter(
        get_logger("prefect.flow_runs"),
        extra={
            **{
                "flow_run_name": flow_run.name,
                "flow_run_id": flow_run.id,
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
    return logging.LoggerAdapter(
        get_logger("prefect.task_runs"),
        extra={
            **{
                "task_run_name": task_run.name,
                "task_run_id": task_run.id,
                "task_name": task.name if task else "<unknown>",
                "flow_run_name": flow_run.name if flow_run else "<unknown>",
                "flow_run_id": flow_run.id if flow_run else "<unknown>",
                "flow_name": flow.name if flow else "<unknown>",
            },
            **kwargs,
        },
    )


class OrionLogWorker:
    """
    Manages the submission of logs to Orion.
    """

    def __init__(self) -> None:
        self.queue: queue.Queue[dict] = queue.Queue()
        self.send_thread = threading.Thread(
            target=self.send_logs_loop,
            name="orion-log-worker",
            daemon=True,
        )
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.started = False

        # Tracks logs that have been pulled from the queue but not sent successfully
        self.pending_logs: List[dict] = []
        self.pending_size: int = 0

        # We must defer this import to avoid circular imports
        from prefect.client import OrionClient

        self.client_cls = OrionClient

        self.logger = get_logger("logging")

        # Ensure stop is called at exit
        atexit.register(self.stop)

    def send_logs_loop(self):
        """
        Should only be the target of the `send_thread` as it creates a new event loop.

        Runs until the `stop_event` is set.
        """
        while not self.stop_event.wait(
            timeout=prefect.settings.logging.orion_log_interval
        ):
            anyio.run(self.send_logs)

        # After the stop event, we are exiting...
        # Try to send any remaining logs
        anyio.run(self.send_logs, True)

    async def send_logs(self, exiting: bool = False) -> None:
        """
        Send all logs in the queue in batches to avoid network limits.

        If a client error is encountered, the logs pulled from the queue are retained
        and will be sent on the next call.
        """
        done = False

        # Loop until the queue is empty or we encounter an error
        while not done:

            # Pull logs from the queue until it is empty or we reach the batch size
            try:
                while (
                    self.pending_size
                    < prefect.settings.logging.orion_max_batch_log_size
                ):
                    log = self.queue.get_nowait()
                    self.pending_logs.append(log)
                    self.pending_size += sys.getsizeof(log)
            except queue.Empty:
                done = True

            async with self.client_cls() as client:
                try:
                    await client.create_logs(self.pending_logs)
                    self.pending_logs = []
                    self.pending_size = 0
                except Exception as exc:
                    # Attempt to send these logs on the next call instead
                    done = True

                    # Roughly replicate the behavior of the stdlib logger error handling
                    if logging.raiseExceptions:
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
                                f"{prefect.settings.logging.orion_log_interval}s\n"
                            )

    def worker_info(self) -> str:
        """Returns a debugging string with worker log stats"""
        return (
            "Worker information:\n"
            f"    Approximate queue length: {self.queue.qsize()}\n"
            f"    Pending log batch length: {len(self.pending_logs)}\n"
            f"    Pending log batch size: {self.pending_size}\n"
        )

    def enqueue(self, log: dict):
        self.queue.put(log)

    def start(self) -> None:
        """Start the background thread"""
        with self.lock:
            if not self.started:
                self.send_thread.start()
                self.started = True

    def stop(self) -> None:
        """Flush all logs and stop the background thread"""
        with self.lock:
            if self.started:
                self.stop_event.set()
                self.send_thread.join()
                self.started = False


class OrionHandler(logging.Handler):
    worker: OrionLogWorker = None

    @classmethod
    def get_worker(cls) -> OrionLogWorker:
        if not cls.worker:
            cls.worker = OrionLogWorker()
            cls.worker.start()
        return cls.worker

    def emit(self, record):
        try:
            self.get_worker().enqueue(self.prepare(record))
        except:
            self.handleError(record)

    def prepare(self, record: logging.LogRecord) -> dict:
        flow_run_id = getattr(record, "flow_run_id", None)
        task_run_id = getattr(record, "task_run_id", None)

        if not flow_run_id:
            context = prefect.context.FlowRunContext.get()
            if not context:
                raise RuntimeError(
                    "Attempted to send logs to Orion without a flow run id. The "
                    "Orion log handler must be attached to loggers used within flow "
                    "run contexts or the flow run id must be manually provided."
                )
            if hasattr(context, "flow_run"):
                flow_run_id = context.flow_run.id
            elif hasattr(context, "task_run"):
                flow_run_id = context.task_run.flow_run_id

        if not task_run_id:
            context = prefect.context.TaskRunContext.get()
            if context and hasattr(context, "task_run"):
                task_run_id = context.task_run.id

        # TODO: We could consider parsing here with `LogCreate` which would raise nice
        #       logging errors that include the raw record on failure. We would then
        #       pass `LogCreate` throughout instead of dictionaries.
        return dict(
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
            name=record.name,
            level=record.levelno,
            timestamp=pendulum.from_timestamp(
                getattr(record, "created", None) or time.time()
            ).isoformat(),
            message=record.getMessage(),
        )

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

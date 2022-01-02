import logging
import logging.config
import os
import re
import warnings
from functools import partial, lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Mapping
import yaml

import prefect
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict
from prefect.utilities.settings import LoggingSettings, Settings
from contextlib import nullcontext

if TYPE_CHECKING:
    from prefect.context import RunContext, FlowRunContext, TaskRunContext

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


def run_logger(context: "RunContext" = None) -> logging.Logger:
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
        )
    elif flow_run_context:
        logger = flow_run_logger(
            flow_run=flow_run_context.flow_run,
            flow=flow_run_context.flow,
        )
    else:
        raise RuntimeError("There is no active flow or task run context.")

    return logger


def flow_run_logger(flow_run, flow=None, **kwargs: str):
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


def task_run_logger(task_run, task=None, flow_run=None, flow=None, **kwargs: str):
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


class RunContextLogger(logging.LoggerAdapter):
    def __init__(
        self,
        logger: logging.Logger,
        flow_run_context: "FlowRunContext" = None,
        task_run_context: "TaskRunContext" = None,
        extra: Mapping = None,
    ) -> None:
        self.flow_run_context = flow_run_context
        self.task_run_context = task_run_context
        super().__init__(logger, extra)

    def process(self, msg, kwargs):
        task_run_metadata = (
            self.task_run_context.templatable_metadata()
            if self.task_run_context
            else {}
        )
        flow_run_metadata = (
            self.flow_run_context.templatable_metadata()
            if self.flow_run_context
            else {}
        )

        kwargs["extra"] = {
            **flow_run_metadata,
            **task_run_metadata,
            **kwargs.get("extra", {}),
        }
        return msg, kwargs


class OrionHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        """
        Emit a logging record to Orion.

        This is not yet implemented. No logs are sent to the server.
        """
        # TODO: Implement a log handler that sends logs to Orion, Core uses a custom
        #       queue to batch messages but we may want to use the stdlib
        #       `MemoryHandler` as a base which implements queueing already
        #       https://docs.python.org/3/howto/logging-cookbook.html#buffering-logging-messages-and-outputting-them-conditionally
        # print(f"Sending {record.msg}")


from rich import get_console
from rich.text import Text
from rich.logging import RichHandler


class PrefectConsoleHandler(logging.Handler):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.console = get_console()

    def emit(self, record: logging.LogRecord):
        from rich.containers import Renderables
        from rich.table import Table

        message = self.format(record)
        parts = message.split("|")
        details = parts[:-1]
        message_renderable = Text(parts[-1])

        output = Table.grid(padding=(0, 1), expand=True)
        output.expand = True
        for _ in details[:-1]:
            output.add_column()
        output.add_column(width=40)

        output.add_column(ratio=1, overflow="fold")
        output.add_row(*details, message_renderable)
        # if self.show_level:
        #     output.add_column(style="log.level", width=8)

        try:
            self.console.print(output)
        except Exception:
            self.handleError(record)

        # def render(
        #     self,
        #     *,
        #     record: logging.LogRecord,
        #     traceback: Optional[Traceback],
        #     message_renderable: "ConsoleRenderable",
        # ) -> "ConsoleRenderable":
        #     """Render log for display.

        #     Args:
        #         record (logging.LogRecord): logging Record.
        #         traceback (Optional[Traceback]): Traceback instance or None for no Traceback.
        #         message_renderable (ConsoleRenderable): Renderable (typically Text) containing log message contents.

        #     Returns:
        #         ConsoleRenderable: Renderable to display log.
        #     """

        #     output.add_column(ratio=1, style="log.message", overflow="fold")
        #     if self.show_path and path:
        #         output.add_column(style="log.path")
        #     row: List["RenderableType"] = []
        #     if self.show_time:
        #         log_time = log_time or console.get_datetime()
        #         time_format = time_format or self.time_format
        #         if callable(time_format):
        #             log_time_display = time_format(log_time)
        #         else:
        #             log_time_display = Text(log_time.strftime(time_format))
        #         if log_time_display == self._last_time and self.omit_repeated_times:
        #             row.append(Text(" " * len(log_time_display)))
        #         else:
        #             row.append(log_time_display)
        #             self._last_time = log_time_display
        #     if self.show_level:
        #         row.append(level)

        #     row.append(message_renderable))
        #     output.add_row(*row)
        # return output


from fastapi.encoders import jsonable_encoder

from pprint import pformat


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


def exclude_engine_logs(record: logging.LogRecord):
    print(record)
    return False
    print(record.module)
    raise ValueError()
    return record.module != "engine"

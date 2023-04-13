import json
import logging
import sys
import time
import traceback
import warnings
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Type, Union

import pendulum
from rich.console import Console
from rich.highlighter import Highlighter, NullHighlighter
from rich.theme import Theme
from typing_extensions import Self

import prefect.context
from prefect._internal.compatibility.deprecated import deprecated_callable
from prefect._internal.concurrency.services import BatchedQueueService
from prefect.client.orchestration import get_client
from prefect.exceptions import MissingContextError
from prefect.logging.highlighters import PrefectConsoleHighlighter
from prefect.server.schemas.actions import LogCreate
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_LOGGING_COLORS,
    PREFECT_LOGGING_MARKUP,
    PREFECT_LOGGING_TO_API_BATCH_INTERVAL,
    PREFECT_LOGGING_TO_API_BATCH_SIZE,
    PREFECT_LOGGING_TO_API_ENABLED,
    PREFECT_LOGGING_TO_API_MAX_LOG_SIZE,
    PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW,
)


class APILogWorker(BatchedQueueService[Dict[str, Any]]):
    @property
    def _max_batch_size(self):
        return max(
            PREFECT_LOGGING_TO_API_BATCH_SIZE.value()
            - PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value(),
            PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value(),
        )

    @property
    def _min_interval(self):
        return PREFECT_LOGGING_TO_API_BATCH_INTERVAL.value()

    async def _handle_batch(self, items: List):
        try:
            await self._client.create_logs(items)
        except Exception:
            # Roughly replicate the behavior of the stdlib logger error handling
            if logging.raiseExceptions and sys.stderr:
                sys.stderr.write("--- Error logging to API ---\n")
                traceback.print_exc(file=sys.stderr)

    @asynccontextmanager
    async def _lifespan(self):
        async with get_client() as self._client:
            yield

    @classmethod
    def instance(cls: Type[Self]) -> Self:
        settings = (
            PREFECT_LOGGING_TO_API_BATCH_SIZE.value(),
            PREFECT_API_URL.value(),
            PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value(),
        )

        # Ensure a unique worker is retrieved per relevant logging settings
        return super().instance(*settings)

    def _get_size(self, item: Dict[str, Any]) -> int:
        return item.pop("__payload_size__", None) or len(json.dumps(item).encode())


class APILogHandler(logging.Handler):
    """
    A logging handler that sends logs to the Prefect API.

    Sends log records to the `APILogWorker` which manages sending batches of logs in
    the background.
    """

    @classmethod
    def flush(cls):
        """
        Tell the `APILogWorker` to send any currently enqueued logs and block until
        completion.

        Returns an awaitable if called from an async context.
        """
        return APILogWorker.drain_all()

    def emit(self, record: logging.LogRecord):
        """
        Send a log to the `APILogWorker`
        """
        try:
            profile = prefect.context.get_settings_context()

            if not PREFECT_LOGGING_TO_API_ENABLED.value_from(profile.settings):
                return  # Respect the global settings toggle
            if not getattr(record, "send_to_orion", True):
                return  # Do not send records that have opted out

            log = self.prepare(record)
            APILogWorker.instance().send(log)

        except Exception:
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        _, exc, _ = sys.exc_info()

        if isinstance(exc, MissingContextError):
            log_handling_when_missing_flow = (
                PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW.value()
            )
            if log_handling_when_missing_flow == "warn":
                # Warn when a logger is used outside of a run context, the stack level here
                # gets us to the user logging call
                warnings.warn(str(exc), stacklevel=8)
                return
            elif log_handling_when_missing_flow == "ignore":
                return
            else:
                raise exc

        # Display a longer traceback for other errors
        return super().handleError(record)

    def prepare(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Convert a `logging.LogRecord` to the API `LogCreate` schema and serialize.

        This infers the linked flow or task run from the log record or the current
        run context.

        If a flow run id cannot be found, the log will be dropped.

        Logs exceeding the maximum size will be dropped.
        """
        flow_run_id = getattr(record, "flow_run_id", None)
        task_run_id = getattr(record, "task_run_id", None)

        if not flow_run_id:
            try:
                context = prefect.context.get_run_context()
            except MissingContextError:
                raise MissingContextError(
                    f"Logger {record.name!r} attempted to send logs to the API without"
                    " a flow run id. The API log handler can only send logs within"
                    " flow run contexts unless the flow run id is manually provided."
                ) from None

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
        log = LogCreate(
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
            name=record.name,
            level=record.levelno,
            timestamp=pendulum.from_timestamp(
                getattr(record, "created", None) or time.time()
            ),
            message=self.format(record),
        ).dict(json_compatible=True)

        log_size = log["__payload_size__"] = self._get_payload_size(log)
        if log_size > PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value():
            raise ValueError(
                f"Log of size {log_size} is greater than the max size of "
                f"{PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value()}"
            )

        return log

    def _get_payload_size(self, log: Dict[str, Any]) -> int:
        return len(json.dumps(log).encode())

    def close(self):
        APILogWorker.drain_all()


class PrefectConsoleHandler(logging.StreamHandler):
    def __init__(
        self,
        stream=None,
        highlighter: Highlighter = PrefectConsoleHighlighter,
        styles: Dict[str, str] = None,
        level: Union[int, str] = logging.NOTSET,
    ):
        """
        The default console handler for Prefect, which highlights log levels,
        web and file URLs, flow and task (run) names, and state types in the
        local console (terminal).

        Highlighting can be toggled on/off with the PREFECT_LOGGING_COLORS setting.
        For finer control, use logging.yml to add or remove styles, and/or
        adjust colors.
        """
        super().__init__(stream=stream)

        styled_console = PREFECT_LOGGING_COLORS.value()
        markup_console = PREFECT_LOGGING_MARKUP.value()
        if styled_console:
            highlighter = highlighter()
            theme = Theme(styles, inherit=False)
        else:
            highlighter = NullHighlighter()
            theme = Theme(inherit=False)

        self.level = level
        self.console = Console(
            highlighter=highlighter,
            theme=theme,
            file=self.stream,
            markup=markup_console,
        )

    def emit(self, record: logging.LogRecord):
        try:
            message = self.format(record)
            self.console.print(message, soft_wrap=True)
        except RecursionError:
            # This was copied over from logging.StreamHandler().emit()
            # https://bugs.python.org/issue36272
            raise
        except Exception:
            self.handleError(record)


@deprecated_callable(start_date="Feb 2023", help="Use `APILogHandler` instead.")
class OrionHandler(APILogHandler):
    """
    Deprecated. Use `APILogHandler` instead.
    """


@deprecated_callable(start_date="Feb 2023", help="Use `APILogWorker` instead.")
class OrionLogWorker(APILogWorker):
    """
    Deprecated. Use `APILogWorker` instead.
    """

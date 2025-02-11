from __future__ import annotations

import json
import logging
import sys
import time
import traceback
import uuid
import warnings
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Dict, TextIO, Type

from rich.console import Console
from rich.highlighter import Highlighter, NullHighlighter
from rich.theme import Theme
from typing_extensions import Self

import prefect.context
from prefect._internal.concurrency.api import create_call, from_sync
from prefect._internal.concurrency.event_loop import get_running_loop
from prefect._internal.concurrency.services import BatchedQueueService
from prefect._internal.concurrency.threads import in_global_loop
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import LogCreate
from prefect.exceptions import MissingContextError
from prefect.logging.highlighters import PrefectConsoleHighlighter
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_LOGGING_COLORS,
    PREFECT_LOGGING_INTERNAL_LEVEL,
    PREFECT_LOGGING_MARKUP,
    PREFECT_LOGGING_TO_API_BATCH_INTERVAL,
    PREFECT_LOGGING_TO_API_BATCH_SIZE,
    PREFECT_LOGGING_TO_API_MAX_LOG_SIZE,
    PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW,
)
from prefect.types._datetime import from_timestamp

if sys.version_info >= (3, 12):
    StreamHandler = logging.StreamHandler[TextIO]
else:
    if TYPE_CHECKING:
        StreamHandler = logging.StreamHandler[TextIO]
    else:
        StreamHandler = logging.StreamHandler


class APILogWorker(BatchedQueueService[Dict[str, Any]]):
    @property
    def _max_batch_size(self) -> int:
        return max(
            PREFECT_LOGGING_TO_API_BATCH_SIZE.value()
            - PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value(),
            PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value(),
        )

    @property
    def _min_interval(self) -> float | None:
        return PREFECT_LOGGING_TO_API_BATCH_INTERVAL.value()

    async def _handle_batch(self, items: list[dict[str, Any]]):
        try:
            await self._client.create_logs(items)
        except Exception as e:
            # Roughly replicate the behavior of the stdlib logger error handling
            if logging.raiseExceptions and sys.stderr:
                sys.stderr.write("--- Error logging to API ---\n")
                if PREFECT_LOGGING_INTERNAL_LEVEL.value() == "DEBUG":
                    traceback.print_exc(file=sys.stderr)
                else:
                    # Only log the exception message in non-DEBUG mode
                    sys.stderr.write(str(e))

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
    def flush(cls) -> None:
        """
        Tell the `APILogWorker` to send any currently enqueued logs and block until
        completion.

        Use `aflush` from async contexts instead.
        """
        loop = get_running_loop()
        if loop:
            if in_global_loop():  # Guard against internal misuse
                raise RuntimeError(
                    "Cannot call `APILogWorker.flush` from the global event loop; it"
                    " would block the event loop and cause a deadlock. Use"
                    " `APILogWorker.aflush` instead."
                )

            # Not ideal, but this method is called by the stdlib and cannot return a
            # coroutine so we just schedule the drain in a new thread and continue
            from_sync.call_soon_in_new_thread(create_call(APILogWorker.drain_all))
            return None
        else:
            # We set a timeout of 5s because we don't want to block forever if the worker
            # is stuck. This can occur when the handler is being shutdown and the
            # `logging._lock` is held but the worker is attempting to emit logs resulting
            # in a deadlock.
            return APILogWorker.drain_all(timeout=5)

    @classmethod
    async def aflush(cls) -> bool:
        """
        Tell the `APILogWorker` to send any currently enqueued logs and block until
        completion.
        """

        return await APILogWorker.drain_all()

    def emit(self, record: logging.LogRecord) -> None:
        """
        Send a log to the `APILogWorker`
        """
        try:
            profile = prefect.context.get_settings_context()

            if not profile.settings.logging.to_api.enabled:
                return  # Respect the global settings toggle
            if not getattr(record, "send_to_api", True):
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
                warnings.warn(
                    f"{exc} Set PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW=ignore to suppress this warning.",
                    stacklevel=8,
                )
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
        worker_id = getattr(record, "worker_id", None)

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
        try:
            is_uuid_like = isinstance(flow_run_id, uuid.UUID) or (
                isinstance(flow_run_id, str) and uuid.UUID(flow_run_id)
            )
        except ValueError:
            is_uuid_like = False

        log = LogCreate(
            flow_run_id=flow_run_id if is_uuid_like else None,
            task_run_id=task_run_id,
            worker_id=worker_id,
            name=record.name,
            level=record.levelno,
            timestamp=from_timestamp(getattr(record, "created", None) or time.time()),
            message=self.format(record),
        ).model_dump(mode="json")

        log_size = log["__payload_size__"] = self._get_payload_size(log)
        if log_size > PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value():
            raise ValueError(
                f"Log of size {log_size} is greater than the max size of "
                f"{PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value()}"
            )

        return log

    def _get_payload_size(self, log: Dict[str, Any]) -> int:
        return len(json.dumps(log).encode())


class WorkerAPILogHandler(APILogHandler):
    def emit(self, record: logging.LogRecord) -> None:
        # Open-source API servers do not currently support worker logs, and
        # worker logs only have an associated worker ID when connected to Cloud,
        # so we won't send worker logs to the API unless they have a worker ID.
        if not getattr(record, "worker_id", None):
            return
        super().emit(record)

    def prepare(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Convert a `logging.LogRecord` to the API `LogCreate` schema and serialize.

        This will add in the worker id to the log.

        Logs exceeding the maximum size will be dropped.
        """

        worker_id = getattr(record, "worker_id", None)

        log = LogCreate(
            worker_id=worker_id,
            name=record.name,
            level=record.levelno,
            timestamp=from_timestamp(getattr(record, "created", None) or time.time()),
            message=self.format(record),
        ).model_dump(mode="json")

        log_size = log["__payload_size__"] = self._get_payload_size(log)
        if log_size > PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value():
            raise ValueError(
                f"Log of size {log_size} is greater than the max size of "
                f"{PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value()}"
            )

        return log


class PrefectConsoleHandler(StreamHandler):
    def __init__(
        self,
        stream: TextIO | None = None,
        highlighter: type[Highlighter] = PrefectConsoleHighlighter,
        styles: dict[str, str] | None = None,
        level: int | str = logging.NOTSET,
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
        self.console: Console = Console(
            highlighter=highlighter,
            theme=theme,
            file=self.stream,
            markup=markup_console,
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.console.print(message, soft_wrap=True)
        except RecursionError:
            # This was copied over from logging.StreamHandler().emit()
            # https://bugs.python.org/issue36272
            raise
        except Exception:
            self.handleError(record)

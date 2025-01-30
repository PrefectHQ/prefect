"""
The base class for all Prefect REST API loop services.
"""

from __future__ import annotations

import asyncio
import signal
from operator import methodcaller
from typing import TYPE_CHECKING, Any, List, NoReturn, Optional, overload

import anyio

from prefect.logging import get_logger
from prefect.server.services.base import Service
from prefect.settings import PREFECT_API_LOG_RETRYABLE_ERRORS
from prefect.types import DateTime
from prefect.utilities.processutils import (
    _register_signal,  # type: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    import logging


class LoopService(Service):
    """
    Loop services are relatively lightweight maintenance routines that need to run periodically.

    This class makes it straightforward to design and integrate them. Users only need to
    define the `run_once` coroutine to describe the behavior of the service on each loop.
    """

    loop_seconds = 60

    def __init__(
        self, loop_seconds: Optional[float] = None, handle_signals: bool = False
    ):
        """
        Args:
            loop_seconds (float): if provided, overrides the loop interval
                otherwise specified as a class variable
            handle_signals (bool): if True, SIGINT and SIGTERM are
                gracefully intercepted and shut down the running service.
        """
        if loop_seconds:
            self.loop_seconds: float = loop_seconds  # seconds between runs
        self._should_stop: bool = (
            False  # flag for whether the service should stop running
        )
        self._is_running: bool = False  # flag for whether the service is running
        self.name: str = type(self).__name__
        self.logger: "logging.Logger" = get_logger(
            f"server.services.{self.name.lower()}"
        )

        if handle_signals:
            _register_signal(signal.SIGINT, self._stop)
            _register_signal(signal.SIGTERM, self._stop)

    async def _on_start(self) -> None:
        """
        Called prior to running the service
        """
        self._should_stop = False
        self._is_running = True
        self.logger.debug(f"Starting {self.name}")

    async def _on_stop(self) -> None:
        """
        Called after running the service
        """
        self._is_running = False
        self.logger.debug(f"Stopped {self.name}")

    @overload
    async def start(self, loops: None = None) -> NoReturn:
        ...

    @overload
    async def start(self, loops: int) -> None:
        ...

    async def start(self, loops: int | None = None) -> None | NoReturn:
        """
        Run the service `loops` time. Pass loops=None to run forever.

        Args:
            loops (int, optional): the number of loops to run before exiting.
        """
        await self._on_start()

        i = 0
        while not self._should_stop:
            start_time = DateTime.now("UTC")

            try:
                self.logger.debug(f"About to run {self.name}...")
                await self.run_once()

            except NotImplementedError as exc:
                raise exc from None

            except asyncio.CancelledError:
                self.logger.info(f"Received cancellation signal for {self.name}")
                raise

            except Exception as exc:
                # avoid circular import
                from prefect.server.api.server import is_client_retryable_exception

                retryable_error = is_client_retryable_exception(exc)
                if not retryable_error or (
                    retryable_error and PREFECT_API_LOG_RETRYABLE_ERRORS.value()
                ):
                    self.logger.error(
                        f"Unexpected error in: {repr(exc)}", exc_info=True
                    )

            end_time = DateTime.now("UTC")

            # if service took longer than its loop interval, log a warning
            # that the interval might be too short
            if (end_time - start_time).total_seconds() > self.loop_seconds:
                self.logger.warning(
                    f"{self.name} took {(end_time - start_time).total_seconds()} seconds"
                    " to run, which is longer than its loop interval of"
                    f" {self.loop_seconds} seconds."
                )

            # check if early stopping was requested
            i += 1
            if loops is not None and i == loops:
                self.logger.debug(f"{self.name} exiting after {loops} loop(s).")
                await self.stop(block=False)

            # next run is every "loop seconds" after each previous run *started*.
            # note that if the loop took unexpectedly long, the "next_run" time
            # might be in the past, which will result in an instant start
            next_run = max(
                start_time.add(seconds=self.loop_seconds), DateTime.now("UTC")
            )
            self.logger.debug(f"Finished running {self.name}. Next run at {next_run}")

            # check the `_should_stop` flag every 1 seconds until the next run time is reached
            while DateTime.now("UTC") < next_run and not self._should_stop:
                await asyncio.sleep(
                    min(1, (next_run - DateTime.now("UTC")).total_seconds())
                )

        await self._on_stop()

    async def stop(self, block: bool = True) -> None:
        """
        Gracefully stops a running LoopService and optionally blocks until the
        service stops.

        Args:
            block (bool): if True, blocks until the service is
                finished running. Otherwise it requests a stop and returns but
                the service may still be running a final loop.

        """
        self.logger.debug(f"Stopping {self.name}...")
        self._stop()

        if block:
            # if block=True, sleep until the service stops running,
            # but no more than `loop_seconds` to avoid a deadlock
            with anyio.move_on_after(self.loop_seconds):
                while self._is_running:
                    await asyncio.sleep(0.1)

            # if the service is still running after `loop_seconds`, something's wrong
            if self._is_running:
                self.logger.warning(
                    f"`stop(block=True)` was called on {self.name} but more than one"
                    f" loop interval ({self.loop_seconds} seconds) has passed. This"
                    " usually means something is wrong. If `stop()` was called from"
                    " inside the loop service, use `stop(block=False)` instead."
                )

    def _stop(self, *_: Any) -> None:
        """
        Private, synchronous method for setting the `_should_stop` flag. Takes arbitrary
        arguments so it can be used as a signal handler.
        """
        self._should_stop = True

    async def run_once(self) -> None:
        """
        Represents one loop of the service.

        Users should override this method.

        To actually run the service once, call `LoopService().start(loops=1)`
        instead of `LoopService().run_once()`, because this method will not invoke setup
        and teardown methods properly.
        """
        raise NotImplementedError("LoopService subclasses must implement this method.")


async def run_multiple_services(loop_services: List[LoopService]) -> NoReturn:
    """
    Only one signal handler can be active at a time, so this function takes a list
    of loop services and runs all of them with a global signal handler.
    """

    def stop_all_services(*_: Any) -> None:
        for service in loop_services:
            stop = methodcaller("_stop")
            stop(service)

    signal.signal(signal.SIGINT, stop_all_services)
    signal.signal(signal.SIGTERM, stop_all_services)
    await asyncio.gather(*[service.start() for service in loop_services])

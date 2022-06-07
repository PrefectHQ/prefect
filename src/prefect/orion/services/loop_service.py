"""
The base class for all Orion loop services.
"""

import asyncio
import signal

import pendulum

from prefect.logging import get_logger
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface


class LoopService:
    """
    Loop services are relatively lightweight maintenance routines that need to run periodically.

    This class makes it straightforward to design and integrate them. Users only need to
    define the `run_once` coroutine to describe the behavior of the service on each loop.
    """

    loop_seconds = 60

    def __init__(self, loop_seconds: float = None, handle_signals: bool = True):
        """
        Args:
            loop_seconds (float): if provided, overrides the loop interval
                otherwise specified as a class variable
            handle_signals (bool): if True (default), SIGINT and SIGTERM are
                gracefully intercepted and shut down the running service.
        """
        if loop_seconds:
            self.loop_seconds = loop_seconds  # seconds between runs
        self.should_stop = False  # flag for whether the service should stop running
        self.name = type(self).__name__
        self.logger = get_logger(f"orion.services.{self.name.lower()}")

        if handle_signals:
            signal.signal(signal.SIGINT, self._stop)
            signal.signal(signal.SIGTERM, self._stop)

    @inject_db
    async def setup(self, db: OrionDBInterface) -> None:
        """
        Called prior to running the service
        """
        self.should_stop = False

    async def shutdown(self) -> None:
        """
        Called after running the service
        """
        # reset `should_stop` to False
        self.should_stop = False

    async def start(self, loops=None) -> None:
        """
        Run the service `loops` time. Pass loops=None to run forever.

        Args:
            loops (int, optional): the number of loops to run before exiting.
        """

        await self.setup()

        i = 0
        while not self.should_stop:
            start_time = pendulum.now("UTC")

            try:
                self.logger.debug(f"About to run {self.name}...")
                await self.run_once()

            except NotImplementedError as exc:
                raise exc from None

            # if an error is raised, log and continue
            except Exception as exc:
                self.logger.error(f"Unexpected error in: {repr(exc)}", exc_info=True)

            end_time = pendulum.now("UTC")

            # if service took longer than its loop interval, log a warning
            # that the interval might be too short
            if (end_time - start_time).total_seconds() > self.loop_seconds:
                self.logger.warning(
                    f"{self.name} took {(end_time-start_time).total_seconds()} seconds to run, "
                    f"which is longer than its loop interval of {self.loop_seconds} seconds."
                )

            # check if early stopping was requested
            i += 1
            if loops is not None and i == loops:
                self.logger.debug(f"{self.name} exiting after {loops} loop(s).")
                break

            # next run is every "loop seconds" after each previous run *started*.
            # note that if the loop took unexpectedly long, the "next_run" time
            # might be in the past, which will result in an instant start
            next_run = max(
                start_time.add(seconds=self.loop_seconds), pendulum.now("UTC")
            )
            self.logger.debug(f"Finished running {self.name}. Next run at {next_run}")

            # check the `should_stop` flag every 1 seconds until the next run time is reached
            while pendulum.now("UTC") < next_run and not self.should_stop:
                await asyncio.sleep(
                    min(1, (next_run - pendulum.now("UTC")).total_seconds())
                )

        await self.shutdown()

    async def stop(self) -> None:
        """
        Gracefully stops a running LoopService and blocks until the service
        stops (indicated by resetting the `should_stop` flag).
        """
        self._stop()

        while self.should_stop:
            await asyncio.sleep(0.1)

    def _stop(self, *_) -> None:
        """
        Private method for setting the `should_stop` flag. Takes arbitrary
        arguments so it can be used as a signal handler.
        """
        self.should_stop = True

    async def run_once(self) -> None:
        """
        Represents one loop of the service.

        Users should override this method.

        To actually run the service once, call `LoopService.start(loops=1)` instead
        of this method, in order to handle setup/shutdown properly.
        """
        raise NotImplementedError("LoopService subclasses must implement this method.")

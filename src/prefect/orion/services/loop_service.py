import sqlalchemy as sa
import prefect
import asyncio

import pendulum
from prefect.orion.utilities.database import get_engine, get_session_factory
from prefect.utilities.logging import get_logger
from typing import Optional


class LoopService:
    """
    Loop services are relatively lightweight maintenance routines that need to run periodically.

    This class makes it straightforward to design and integrate them. Users only need to
    define the `run_once` coroutine to describe the behavior of the service on each loop.
    """

    # The time between loops
    loop_seconds: float = 60

    # class-level flag for whether the service should stop running
    should_stop: bool = False

    # services may need different database timeouts than the rest of the application
    database_timeout: Optional[float] = prefect.settings.orion.database.services_timeout
    session_factory: sa.ext.asyncio.scoping.async_scoped_session = None

    def __init__(self, loop_seconds: float = None):
        if loop_seconds:
            self.loop_seconds = loop_seconds
        self.name = type(self).__name__
        self.logger = get_logger(f"orion.services.{self.name}")

    async def setup(self) -> None:
        """
        Called prior to running the service
        """
        # ensure the should_stop flag is False
        self.should_stop = False

        # prepare a database engine
        # this call is cached and shared across services if possible
        engine = await get_engine(timeout=self.database_timeout)
        self.session_factory = await get_session_factory(engine)

    async def shutdown(self) -> None:
        """
        Called after running the service
        """
        self.should_stop = False
        self.session_factory = None

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

            # if an error is raised, log and continue
            except Exception as exc:
                self.logger.error(f"Unexpected error in: {repr(exc)}", exc_info=True)

            end_time = pendulum.now("UTC")

            # if service took longer than its loop interval, log a warning
            # that the interval might be too short
            now = pendulum.now("UTC")
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
            await asyncio.sleep(max(0, (next_run - now).total_seconds()))

        await self.shutdown()

    def stop(self) -> None:
        """
        Gracefully stops a running LoopService. It may take until the end of its sleep time
        for it to exit.
        """
        self.should_stop = True

    async def run_once(self) -> None:
        """
        Represents one loop of the service.

        Users should override this method.

        To actually run the service once, call `LoopService.start(loops=1)` instead
        of this method, in order to handle setup/shutdown properly.
        """
        raise NotImplementedError()

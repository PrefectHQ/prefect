import asyncio

import pendulum

from prefect.utilities.logging import get_logger


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

    def __init__(self, loop_seconds: float = None):
        if loop_seconds:
            self.loop_seconds = loop_seconds
        self.name = type(self).__name__
        self.logger = get_logger(f"services.{self.name}")

    async def start(self) -> None:
        """
        Run the service forever.
        """

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

            # next run is every "loop seconds" after each previous run *started*.
            # note that if the loop took unexpectedly long, the "next_run" time
            # might be in the past, which will result in an instant start
            next_run = max(
                start_time.add(seconds=self.loop_seconds), pendulum.now("UTC")
            )

            self.logger.debug(f"Finished running {self.name}. Next run at {next_run}")

            await asyncio.sleep(max(0, (next_run - now).total_seconds()))

        self.should_stop = False

    @classmethod
    def stop(cls) -> None:
        """
        Stops a running LoopService. This is a classmethod, so it will affect
        all instances of the class.
        """
        cls.should_stop = True

    async def run_once(self) -> None:
        """
        Run the service once.

        Users should override this method.
        """
        raise NotImplementedError()

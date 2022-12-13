from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from prefect import get_run_logger
from prefect.blocks.core import Block
from prefect.exceptions import MissingContextError
from prefect.logging.loggers import get_logger

T = TypeVar("T")


class JobRun(ABC, Generic[T]):  # not a block
    """
    Represents a job run in an external system. Allows waiting
    for the job run's completion and fetching its results.
    """

    @property
    def logger(self):
        """
        Returns a logger based on whether the JobRun
        is called from within a flow or task run context.
        If a run context is present, the logger property returns a run logger.
        Else, it returns a default logger labeled with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    @abstractmethod
    async def wait_for_completion(self):
        """
        Wait for the job run to complete.
        """

    @abstractmethod
    async def fetch_result(self) -> T:
        """
        Retrieve the results of the job run and return them.
        """


class JobBlock(Block, ABC):
    """
    Block that represents an entity in an external service that can trigger a long running execution.
    """

    @property
    def logger(self):
        """
        Returns a logger based on whether the JobBlock
        is called from within a flow or task run context.
        If a run context is present, the logger property returns a run logger.
        Else, it returns a default logger labeled with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    @abstractmethod
    async def trigger(self) -> JobRun:
        """
        Triggers a job run in an external service and returns a JobRun object
        to track the execution of the run.
        """

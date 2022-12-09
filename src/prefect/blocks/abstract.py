from abc import ABC, abstractmethod
from typing import TypeVar

from prefect import get_run_logger
from prefect.blocks.core import Block
from prefect.exceptions import MissingContextError
from prefect.logging.loggers import get_logger

JobBlockType = TypeVar(
    "JobBlockType", bound=Block
)  # Generic type var for representing JobBlock


class JobRun(ABC):  # not a block
    """
    Represents a job run in an external system that can wait
    for the job run's completion and fetch its results.
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
    async def wait_for_completion(self, *args, **kwargs):
        """
        Wait for the job run to complete and check its status
        periodically using the interval_seconds attribute
        until the job run is complete or the timeout_seconds
        time limit is reached.
        """

    @abstractmethod
    async def fetch_results(self, *args, **kwargs):
        """
        Retrieve the results of the job run and return them.
        This will error if the job run is still running.
        """


class JobBlock(JobBlockType, ABC):
    """
    The JobBlock class represents a resource that can trigger a job
    in an external service, such as Airbyte, Databricks, or dbt Cloud.
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
    async def trigger(self, *args, **kwargs) -> JobRun:
        """
        Triggers a job run using the input job ID in the external
        service and returns a JobRun object.
        """

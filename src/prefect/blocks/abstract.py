from abc import ABC, abstractmethod
from typing import Any, List, Tuple

from prefect import get_run_logger
from prefect.blocks.core import Block
from prefect.exceptions import MissingContextError
from prefect.logging.loggers import get_logger


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


class JobBlock(Block, ABC):
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


class DatabaseBlock(Block, ABC):
    """
    The DatabaseBlock class represents a resource for interacting with a database.
    Heavily influenced by [PEP 249](https://peps.python.org/pep-0249/).
    Skewed towards RDBMS systems and a separate interface may be necessary
    for non relational databases.

    These blocks have the option to compose a credentials block or accept
    credentials directly. It depends on how tightly coupled the database
    configuration is to the credentials configuration.
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
    async def fetch_one(self, operation, parameters) -> Tuple[Any]:
        """
        Fetch a single result from the database.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.

        Returns:
            A list of tuples containing the data returned by the database,
                where each row is a tuple and each column is a value in the tuple.
        """

    @abstractmethod
    async def fetch_many(self, operation, parameters, limit) -> List[Tuple[Any]]:
        """
        Fetch a limited number of results from the database.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
            limit: The number of results to return.

        Returns:
            A list of tuples containing the data returned by the database,
                where each row is a tuple and each column is a value in the tuple.
        """

    @abstractmethod
    async def fetch_all(self, operation, parameters) -> List[Tuple[Any]]:
        """
        Fetch all results from the database.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.

        Returns:
            A list of tuples containing the data returned by the database,
                where each row is a tuple and each column is a value in the tuple.
        """

    @abstractmethod
    async def execute(self, operation, parameters) -> None:
        """
        Executes an operation on the database. This method is intended to be used
        for operations that do not return data, such as INSERT, UPDATE, or DELETE.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
        """

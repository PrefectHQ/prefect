from abc import ABC, abstractmethod
from logging import Logger
from typing import Any, Generic, List, Tuple, TypeVar

from typing_extensions import Self

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
    def logger(self) -> Logger:
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
    Block that represents an entity in an external service
    that can trigger a long running execution.
    """

    @property
    def logger(self) -> Logger:
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


# TODO: This interface is heavily influenced by
# [PEP 249](https://peps.python.org/pep-0249/)
# Primarily intended for use with relational databases.
# A separate interface may be necessary for
# non relational databases.
class DatabaseBlock(Block, ABC):
    """
    An abstract block type that represents a database and
    provides an interface for interacting with it.
    Blocks that implement this interface have the option to accept
    credentials directly via attributes or via a nested `CredentialsBlock`.
    Use of a nested credentials block is recommended unless credentials
    are tightly coupled to database connection configuration.
    Implementing either sync or async context management on `DatabaseBlock`
    implementations is recommended.
    """

    @property
    def logger(self) -> Logger:
        """
        Returns a logger based on whether the DatabaseBlock
        is called from within a flow or task run context.
        If a run context is present, the logger property returns a run logger.
        Else, it returns a default logger labeled with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    @abstractmethod
    async def fetch_one(
        self, operation, parameters=None, **execution_kwargs
    ) -> Tuple[Any]:
        """
        Fetch a single result from the database.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
            **execution_kwargs: Additional keyword arguments to pass to execute.

        Returns:
            A list of tuples containing the data returned by the database,
                where each row is a tuple and each column is a value in the tuple.
        """

    @abstractmethod
    async def fetch_many(
        self, operation, parameters=None, size=None, **execution_kwargs
    ) -> List[Tuple[Any]]:
        """
        Fetch a limited number of results from the database.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
            size: The number of results to return.
            **execution_kwargs: Additional keyword arguments to pass to execute.

        Returns:
            A list of tuples containing the data returned by the database,
                where each row is a tuple and each column is a value in the tuple.
        """

    @abstractmethod
    async def fetch_all(
        self, operation, parameters=None, **execution_kwargs
    ) -> List[Tuple[Any]]:
        """
        Fetch all results from the database.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
            **execution_kwargs: Additional keyword arguments to pass to execute.

        Returns:
            A list of tuples containing the data returned by the database,
                where each row is a tuple and each column is a value in the tuple.
        """

    @abstractmethod
    async def execute(self, operation, parameters=None, **execution_kwargs) -> None:
        """
        Executes an operation on the database. This method is intended to be used
        for operations that do not return data, such as INSERT, UPDATE, or DELETE.

        Args:
            operation: The SQL query or other operation to be executed.
            parameters: The parameters for the operation.
            **execution_kwargs: Additional keyword arguments to pass to execute.
        """

    @abstractmethod
    async def execute_many(
        self, operation, seq_of_parameters, **execution_kwargs
    ) -> None:
        """
        Executes multiple operations on the database. This method is intended to be used
        for operations that do not return data, such as INSERT, UPDATE, or DELETE.

        Args:
            operation: The SQL query or other operation to be executed.
            seq_of_parameters: The sequence of parameters for the operation.
            **execution_kwargs: Additional keyword arguments to pass to execute.
        """

    # context management methods are not abstract methods because
    # they are not supported by all database drivers
    async def __aenter__(self) -> Self:
        """
        Context management method for async databases.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support async context management."
        )

    async def __aexit__(self, *args) -> None:
        """
        Context management method for async databases.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support async context management."
        )

    def __enter__(self) -> Self:
        """
        Context management method for databases.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support context management."
        )

    def __exit__(self, *args) -> None:
        """
        Context management method for databases.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support context management."
        )

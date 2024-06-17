from abc import ABC, abstractmethod
from contextlib import contextmanager
from logging import Logger
from pathlib import Path
from typing import (
    Any,
    BinaryIO,
    Dict,
    Generator,
    Generic,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

from typing_extensions import Self

from prefect.blocks.core import Block
from prefect.exceptions import MissingContextError
from prefect.logging.loggers import get_logger, get_run_logger

T = TypeVar("T")


class CredentialsBlock(Block, ABC):
    """
    Stores credentials for an external system and exposes a client for interacting
    with that system. Can also hold config that is tightly coupled to credentials
    (domain, endpoint, account ID, etc.) Will often be composed with other blocks.
    Parent block should rely on the client provided by a credentials block for
    interacting with the corresponding external system.
    """

    @property
    def logger(self) -> Logger:
        """
        Returns a logger based on whether the CredentialsBlock
        is called from within a flow or task run context.
        If a run context is present, the logger property returns a run logger.
        Else, it returns a default logger labeled with the class's name.

        Returns:
            The run logger or a default logger with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    @abstractmethod
    def get_client(self, *args, **kwargs):
        """
        Returns a client for interacting with the external system.

        If a service offers various clients, this method can accept
        a `client_type` keyword argument to get the desired client
        within the service.
        """


class NotificationError(Exception):
    """Raised if a notification block fails to send a notification."""

    def __init__(self, log: str) -> None:
        self.log = log


class NotificationBlock(Block, ABC):
    """
    Block that represents a resource in an external system that is able to send notifications.
    """

    _block_schema_capabilities = ["notify"]
    _events_excluded_methods = Block._events_excluded_methods.default + ["notify"]

    @property
    def logger(self) -> Logger:
        """
        Returns a logger based on whether the NotificationBlock
        is called from within a flow or task run context.
        If a run context is present, the logger property returns a run logger.
        Else, it returns a default logger labeled with the class's name.

        Returns:
            The run logger or a default logger with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    @abstractmethod
    async def notify(self, body: str, subject: Optional[str] = None) -> None:
        """
        Send a notification.

        Args:
            body: The body of the notification.
            subject: The subject of the notification.
        """

    _raise_on_failure: bool = False

    @contextmanager
    def raise_on_failure(self) -> Generator[None, None, None]:
        """
        Context manager that, while active, causes the block to raise errors if it
        encounters a failure sending notifications.
        """
        self._raise_on_failure = True
        try:
            yield
        finally:
            self._raise_on_failure = False


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

        Returns:
            The run logger or a default logger with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    @abstractmethod
    async def wait_for_completion(self) -> Logger:
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

        Returns:
            The run logger or a default logger with the class's name.
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

        Returns:
            The run logger or a default logger with the class's name.
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


class ObjectStorageBlock(Block, ABC):
    """
    Block that represents a resource in an external service that can store
    objects.
    """

    @property
    def logger(self) -> Logger:
        """
        Returns a logger based on whether the ObjectStorageBlock
        is called from within a flow or task run context.
        If a run context is present, the logger property returns a run logger.
        Else, it returns a default logger labeled with the class's name.

        Returns:
            The run logger or a default logger with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    @abstractmethod
    async def download_object_to_path(
        self,
        from_path: str,
        to_path: Union[str, Path],
        **download_kwargs: Dict[str, Any],
    ) -> Path:
        """
        Downloads an object from the object storage service to a path.

        Args:
            from_path: The path to download from.
            to_path: The path to download to.
            **download_kwargs: Additional keyword arguments to pass to download.

        Returns:
            The path that the object was downloaded to.
        """

    @abstractmethod
    async def download_object_to_file_object(
        self,
        from_path: str,
        to_file_object: BinaryIO,
        **download_kwargs: Dict[str, Any],
    ) -> BinaryIO:
        """
        Downloads an object from the object storage service to a file-like object,
        which can be a BytesIO object or a BufferedWriter.

        Args:
            from_path: The path to download from.
            to_file_object: The file-like object to download to.
            **download_kwargs: Additional keyword arguments to pass to download.

        Returns:
            The file-like object that the object was downloaded to.
        """

    @abstractmethod
    async def download_folder_to_path(
        self,
        from_folder: str,
        to_folder: Union[str, Path],
        **download_kwargs: Dict[str, Any],
    ) -> Path:
        """
        Downloads a folder from the object storage service to a path.

        Args:
            from_folder: The path to the folder to download from.
            to_folder: The path to download the folder to.
            **download_kwargs: Additional keyword arguments to pass to download.

        Returns:
            The path that the folder was downloaded to.
        """

    @abstractmethod
    async def upload_from_path(
        self, from_path: Union[str, Path], to_path: str, **upload_kwargs: Dict[str, Any]
    ) -> str:
        """
        Uploads an object from a path to the object storage service.

        Args:
            from_path: The path to the file to upload from.
            to_path: The path to upload the file to.
            **upload_kwargs: Additional keyword arguments to pass to upload.

        Returns:
            The path that the object was uploaded to.
        """

    @abstractmethod
    async def upload_from_file_object(
        self, from_file_object: BinaryIO, to_path: str, **upload_kwargs: Dict[str, Any]
    ) -> str:
        """
        Uploads an object to the object storage service from a file-like object,
        which can be a BytesIO object or a BufferedReader.

        Args:
            from_file_object: The file-like object to upload from.
            to_path: The path to upload the object to.
            **upload_kwargs: Additional keyword arguments to pass to upload.

        Returns:
            The path that the object was uploaded to.
        """

    @abstractmethod
    async def upload_from_folder(
        self,
        from_folder: Union[str, Path],
        to_folder: str,
        **upload_kwargs: Dict[str, Any],
    ) -> str:
        """
        Uploads a folder to the object storage service from a path.

        Args:
            from_folder: The path to the folder to upload from.
            to_folder: The path to upload the folder to.
            **upload_kwargs: Additional keyword arguments to pass to upload.

        Returns:
            The path that the folder was uploaded to.
        """


class SecretBlock(Block, ABC):
    """
    Block that represents a resource that can store and retrieve secrets.
    """

    @property
    def logger(self) -> Logger:
        """
        Returns a logger based on whether the SecretBlock
        is called from within a flow or task run context.
        If a run context is present, the logger property returns a run logger.
        Else, it returns a default logger labeled with the class's name.

        Returns:
            The run logger or a default logger with the class's name.
        """
        try:
            return get_run_logger()
        except MissingContextError:
            return get_logger(self.__class__.__name__)

    @abstractmethod
    async def read_secret(self) -> bytes:
        """
        Reads the configured secret from the secret storage service.

        Returns:
            The secret data.
        """

    @abstractmethod
    async def write_secret(self, secret_data) -> str:
        """
        Writes secret data to the configured secret in the secret storage service.

        Args:
            secret_data: The secret data to write.

        Returns:
            The key of the secret that can be used for retrieval.
        """

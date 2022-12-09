from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from prefect import get_run_logger
from prefect.blocks.core import Block
from prefect.logging import MissingContextError, get_logger


class JobRun(ABC):  # not a block
    """
    Represents a job run in an external system that can wait
    for the job run's completion and fetch its results
    """

    run_id: int
    timeout: int
    poll_frequency_seconds: int

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
            return get_logger(f"prefect.block.{self.__class__.__name__}")

    @abstractmethod
    async def wait_for_completion(self, *args, **kwargs):
        """
        Wait for the job run to complete and check its status
        periodically using the poll_frequency_seconds attribute
        until the job run is complete or the timeout
        time limit is reached.
        """

    @abstractmethod
    async def fetch_results(self, *args, **kwargs):
        """
        Retrieve the results of the job run and return them.
        This will error if the job run is still running.
        """
        ...


class JobBlock(Block, ABC):
    """
    The JobBlock class represents a resource that can trigger a job
    in an external service, such as Airbyte, Databricks, or dbt Cloud.
    """

    job_id: int
    timeout: int
    poll_frequency_seconds: int

    @abstractmethod
    async def trigger(self, *args, **kwargs) -> JobRun:
        """
        Triggers a job run using the input job ID in the external
        service and returns a JobRun object.
        """
        ...


class DatabaseBlock(Block, ABC):
    @abstractmethod
    async def fetch_one(self, operation, parameters) -> Tuple[Any]:
        ...

    @abstractmethod
    async def fetch_many(
        self, operation, parameters, limit, offset
    ) -> List[Tuple[Any]]:
        ...

    @abstractmethod
    async def fetch_all(self, operation, parameters) -> List[Tuple[Any]]:
        ...

    @abstractmethod
    async def execute(self, operation, parameters):
        ...


class ObjectStorageBlock(Block, ABC):
    @abstractmethod
    async def download_object_to_file(self, *args, **kwargs):
        ...

    @abstractmethod
    async def download_object_to_bytes(self, *args, **kwargs):
        ...

    @abstractmethod
    async def upload_file(self, *args, **kwargs):
        ...

    @abstractmethod
    async def upload_data(self, *args, **kwargs):
        ...

    @abstractmethod
    async def download_folder(self, *args, **kwargs):
        ...

    @abstractmethod
    async def upload_folder(self, *args, **kwargs):
        ...


class SecretBlock(Block, ABC):
    _block_schema_capabilities = ["read-secret-value", "write-secret-value"]

    @abstractmethod
    async def read_secret(self) -> Dict[str, str]:
        ...

    @abstractmethod
    async def write_secret(self, secret_value: Dict[str, str]):
        ...


class DataValidationBlock(Block, ABC):
    _block_schema_capabilities = ["validate-data"]

    @abstractmethod
    async def validate_data(data) -> bool:
        ...

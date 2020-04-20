import os
from typing import Any, Callable, List, Type

import cloudpickle
from distributed.deploy.cluster import Cluster
import prefect
from prefect import config
from prefect.environments.execution.remote import RemoteEnvironment


class DaskCloudProviderEnvironment(RemoteEnvironment):
    """
    DaskCloudProviderEnvironment creates a new Dask cluster using the Dask Cloud Provider
    project. For each flow run, a new Dask cluster will be dynamically created and the
    flow will run using a `RemoteEnvironment` with the `DaskExecutor` using the Dask
    scheduler address from the newly created Dask cluster. You can specify the number
    of Dask workers manually (for example, passing the kwarg `n_workers`) or enable
    adaptive mode by passing `adaptive_min_workers` and, optionally,
    `adaptive_max_workers`. This environment aims to provide a very easy path to
    Dask scalability for users of cloud platforms, like AWS.

    (Dask Cloud Provider currently only supports AWS using either Fargate or ECS.
    Support for AzureML is coming soon.)

    *IMPORTANT* As of April 19, 2020 the Dask Cloud Provider project contains some
    security limitations that make it inappropriate for use with sensitive data.
    Until those security items are addressed, this environment should only be used
    for prototyping and testing.

    Args:
        - provider_class (class): Class of a provider from the Dask Cloud Provider
            projects. Current supported options are `ECSCluster` and `FargateCluster`.
        - adaptive_min_workers (int, optional): Minimum number of workers for adaptive
            mode. If this value is None, then adaptive mode will not be used and you
            should pass `n_workers` or the appropriate kwarg for the provider class you
            are using.
        - adaptive_max_workers (int, optional): Maximum number of workers for adaptive
            mode.
        - aws_access_key_id (str, optional): AWS access key id for connecting the boto3
            client. Defaults to the value set in the environment variable
            `AWS_ACCESS_KEY_ID` or `None`
        - aws_secret_access_key (str, optional): AWS secret access key for connecting
            the boto3 client. Defaults to the value set in the environment variable
            `AWS_SECRET_ACCESS_KEY` or `None`
        - aws_session_token (str, optional): AWS session key for connecting the boto3
            client. Defaults to the value set in the environment variable
            `AWS_SESSION_TOKEN` or `None`
        - region_name (str, optional): AWS region name for connecting the boto3 client.
            Defaults to the value set in the environment variable `REGION_NAME` or `None`
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
        - **kwargs (dict, optional): additional keyword arguments to pass to boto3 for
            `register_task_definition` and `run_task`
    """

    def __init__(  # type: ignore
        self,
        provider_class: Type[Cluster],
        adaptive_min_workers: int = None,
        adaptive_max_workers: int = None,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        aws_session_token: str = None,
        region_name: str = None,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        **kwargs
    ) -> None:
        self._provider_class = provider_class
        self._adaptive_min_workers = adaptive_min_workers
        self._adaptive_max_workers = adaptive_max_workers

        # Not serialized, only stored on the object
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        self.aws_session_token = aws_session_token or os.getenv("AWS_SESSION_TOKEN")
        self.region_name = region_name or os.getenv("REGION_NAME")

        self.cluster = None

        self.kwargs = kwargs
        super().__init__(
            labels=labels,
            on_start=on_start,
            on_exit=on_exit,
            executor="prefect.engine.executors.DaskExecutor",
        )

    @property
    def dependencies(self) -> list:
        return ["boto3", "botocore", "dask_cloudprovider"]

    def setup(self, storage: "Docker") -> None:  # type: ignore
        self.logger.info("Creating Dask cluster using {}".format(self._provider_class))
        self.cluster = self._provider_class(**self.kwargs)
        if self.cluster and self.cluster.scheduler and self.cluster.scheduler.address:
            self.logger.info(
                "Dask cluster created. Sheduler address: {}".format(
                    self.cluster.scheduler.address
                )
            )
        if self._adaptive_min_workers:
            self.logger.info(
                "Enabling adaptive mode with min_workers={} max_workers={}".format(
                    self._adaptive_min_workers, self._adaptive_max_workers
                )
            )
            self.cluster.adapt(
                minimum=self._adaptive_min_workers, maximum=self._adaptive_max_workers
            )

    def execute(  # type: ignore
        self, storage: "Storage", flow_location: str, **kwargs: Any
    ) -> None:
        self.executor_kwargs["address"] = self.cluster.scheduler.address
        self.logger.info(
            "Executing on Dask Cluster with scheduler address: {}".format(
                self.executor_kwargs["address"]
            )
        )
        super().execute(storage, flow_location, **kwargs)

from typing import Any, Callable, List, Type

from distributed.deploy.cluster import Cluster
from distributed.security import Security

from prefect.environments.execution import RemoteDaskEnvironment


class DaskCloudProviderEnvironment(RemoteDaskEnvironment):
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
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
        - security (Type[Security], optional): a Dask Security object from `distributed.security.Security`.
            Use this to connect to a Dask cluster that is enabled with TLS encryption. Fill out the Security
            object like this:
            ```
                security = Security(tls_ca_file='cluster_ca.pem',
                                    tls_client_cert='cli_cert.pem',
                                    tls_client_key='cli_key.pem',
                                    require_encryption=True)
            ```
            For more on using TLS with Dask see https://distributed.dask.org/en/latest/tls.html
        - **kwargs (dict, optional): additional keyword arguments to pass to boto3 for
            `register_task_definition` and `run_task`
    """

    def __init__(  # type: ignore
        self,
        provider_class: Type[Cluster],
        adaptive_min_workers: int = None,
        adaptive_max_workers: int = None,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        security: Security = None,
        **kwargs
    ) -> None:
        self._provider_class = provider_class
        self._adaptive_min_workers = adaptive_min_workers
        self._adaptive_max_workers = adaptive_max_workers
        self._security = security

        self.cluster = None

        self.kwargs = kwargs
        if self._security:
            # We'll use the security config object both for our Dask Client connection *and*
            # for the particular Dask Cloud Provider (e.g. Fargate) to use with its Dask
            # Client connection when it connects to the scheduler after cluster creation so we
            # need to put it in kwargs that get passed to the Dask Cloud Provider's __init()__
            self.kwargs["security"] = self._security
        super().__init__(
            address="",  # The scheduler address will be set later
            labels=labels,
            on_start=on_start,
            on_exit=on_exit,
            security=self._security,
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
            self.executor_kwargs["address"] = self.cluster.scheduler.address  # type: ignore
        else:
            if self.cluster:
                self.cluster.close()
            raise Exception(
                "Unable to determine the Dask scheduler address after cluster creation. "
                "Tearting down cluster and terminating setup."
            )
        if self._adaptive_min_workers:
            self.logger.info(
                "Enabling adaptive mode with min_workers={} max_workers={}".format(
                    self._adaptive_min_workers, self._adaptive_max_workers
                )
            )
            self.cluster.adapt(  # type: ignore
                minimum=self._adaptive_min_workers, maximum=self._adaptive_max_workers
            )

    def execute(  # type: ignore
        self, storage: "Storage", flow_location: str, **kwargs: Any  # type: ignore
    ) -> None:
        self.logger.info(
            "Executing on Dask Cluster with scheduler address: {}".format(
                self.executor_kwargs["address"]
            )
        )
        super().execute(storage, flow_location, **kwargs)

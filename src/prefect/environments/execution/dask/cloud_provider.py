from typing import Any, Callable, List, Type, Dict
from urllib.parse import urlparse

from distributed.deploy.cluster import Cluster
from distributed.security import Security

import prefect
from prefect import Client
from prefect.environments.execution.dask.remote import RemoteDaskEnvironment


class DaskCloudProviderEnvironment(RemoteDaskEnvironment):
    """
    DaskCloudProviderEnvironment creates Dask clusters using the Dask Cloud Provider
    project. For each flow run, a new Dask cluster will be dynamically created and the
    flow will run using a `RemoteDaskEnvironment` with the Dask scheduler address
    from the newly created Dask cluster. You can specify the number of Dask workers
    manually (for example, passing the kwarg `n_workers`) or enable adaptive mode by
    passing `adaptive_min_workers` and, optionally, `adaptive_max_workers`. This
    environment aims to provide a very easy path to Dask scalability for users of
    cloud platforms, like AWS.

    NOTE: AWS Fargate Task (not Prefect Task) startup time can be slow, depending
    on docker image size. Total startup time for a Dask scheduler and workers can
    be several minutes. This environment is a much better fit for production
    deployments of scheduled Flows where there's little sensitivity to startup
    time. DaskCloudProviderEnvironment` is a particularly good fit for automated
    deployment of Flows in a CI/CD pipeline where the infrastructure for each Flow
    should be as independent as possible, e.g. each Flow could have its own docker
    image, dynamically create the Dask cluster to run on, etc. However, for
    development and interactive testing, creating a Dask cluster manually with Dask
    Cloud Provider and then using `RemoteDaskEnvironment` or just ` DaskExecutor`
    with your flows will result in a much better development experience.

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
        - on_start (Callable[[Dict[str, Any], Dict[str, Any]], None], optional): a function callback which will
            be called before the flow begins to run. The callback function can examine the Flow run
            parameters and modify  kwargs to be passed to the Dask Cloud Provider class's constructor prior
            to launching the Dask cluster for the Flow run. This allows for dynamically sizing the cluster based
            on the Flow run parameters, e.g. settings n_workers. The callback function's signature should be:
                `def on_start(parameters: Dict[str, Any], provider_kwargs: Dict[str, Any]) -> None:`
            The callback function may modify provider_kwargs (e.g. `provider_kwargs["n_workers"] = 3`) and any
            relevant changes will be used when creating the Dask cluster via a Dask Cloud Provider class.
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
        - security (Type[Security], optional): a Dask Security object from `distributed.security.Security`.
            Use this to connect to a Dask cluster that is enabled with TLS encryption.
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
        on_start: Callable[[Dict[str, Any], Dict[str, Any]], None] = None,
        on_exit: Callable = None,
        security: Security = None,
        **kwargs
    ) -> None:
        self._provider_class = provider_class
        self._adaptive_min_workers = adaptive_min_workers
        self._adaptive_max_workers = adaptive_max_workers
        self._on_start = on_start
        self._security = security
        self._provider_kwargs = kwargs
        if self._security:
            # We'll use the security config object both for our Dask Client connection *and*
            # for the particular Dask Cloud Provider (e.g. Fargate) to use with *its* Dask
            # Client when it connects to the scheduler after cluster creation. So we
            # put it in _provider_kwargs so it gets passed to the Dask Cloud Provider's constructor
            self._provider_kwargs["security"] = self._security
        self.cluster = None
        super().__init__(
            address="",  # The scheduler address will be set after cluster creation
            labels=labels,
            on_start=None,  # Disable on_start in base classes since we'll call our own
            on_exit=on_exit,
            security=self._security,
        )

    @property
    def dependencies(self) -> list:
        return ["boto3", "botocore", "dask_cloudprovider"]

    def _create_dask_cluster(self) -> None:
        self.logger.info("Creating Dask cluster using {}".format(self._provider_class))
        self.cluster = self._provider_class(**self._provider_kwargs)
        if self.cluster and self.cluster.scheduler and self.cluster.scheduler.address:
            self.logger.info(
                "Dask cluster created. Sheduler address: {} Dashboard: http://{}:8787 "
                "(unless port was changed from default of 8787)".format(
                    self.cluster.scheduler.address,
                    urlparse(self.cluster.scheduler.address).hostname,
                )  # TODO submit PR to Dask Cloud Provider allowing discovery of dashboard port
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
        if self._on_start:
            # If an on_start Callable has been provided, retrieve the flow run parameters
            # and then allow the Callable a chance to update _provider_kwargs. This allows
            # better sizing of the cluster resources based on parameters for this Flow run.
            flow_run_id = prefect.context.get("flow_run_id")
            try:
                client = Client()
                flow_run_info = client.get_flow_run_info(flow_run_id)
                parameters = flow_run_info.parameters or {}  # type: ignore
                self._on_start(parameters, self._provider_kwargs)
            except Exception as exc:
                self.logger.info(
                    "Failed to retrieve flow run info with error: {}".format(repr(exc))
                )
        if "image" not in self._provider_kwargs or not self._provider_kwargs.get(
            "image"
        ):
            # If image is not specified, use the Flow's image so that dependencies are
            # identical on all containers: Flow runner, Dask scheduler, and Dask workers
            flow_id = prefect.context.get("flow_id")
            try:
                client = Client()
                flow_info = client.graphql(
                    """query {
                  flow(where: {id: {_eq: "%s"}}) {
                    storage
                  }
                }"""
                    % flow_id
                )
                storage_info = flow_info["data"]["flow"][0]["storage"]
                image = "{}/{}:{}".format(
                    storage_info["registry_url"],
                    storage_info["image_name"],
                    storage_info["image_tag"],
                )
                self.logger.info(
                    "Using Flow's Docker image for Dask scheduler & workers: {}".format(
                        image
                    )
                )
                self._provider_kwargs["image"] = image
            except Exception as exc:
                self.logger.info(
                    "Failed to retrieve flow info with error: {}".format(repr(exc))
                )

        self._create_dask_cluster()

        self.logger.info(
            "Executing on dynamically created Dask Cluster with scheduler address: {}".format(
                self.executor_kwargs["address"]
            )
        )
        super().execute(storage, flow_location, **kwargs)

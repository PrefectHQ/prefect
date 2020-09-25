from typing import Any, Callable, Dict, List, Type, TYPE_CHECKING
from urllib.parse import urlparse

import prefect
from distributed.deploy.cluster import Cluster
from distributed.security import Security
from prefect import Client
from prefect.environments.execution.dask.remote import RemoteDaskEnvironment

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


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

    **NOTE:** AWS Fargate Task (not Prefect Task) startup time can be slow, depending
    on docker image size. Total startup time for a Dask scheduler and workers can
    be several minutes. This environment is a much better fit for production
    deployments of scheduled Flows where there's little sensitivity to startup
    time. `DaskCloudProviderEnvironment` is a particularly good fit for automated
    deployment of Flows in a CI/CD pipeline where the infrastructure for each Flow
    should be as independent as possible, e.g. each Flow could have its own docker
    image, dynamically create the Dask cluster to run on, etc. However, for
    development and interactive testing, creating a Dask cluster manually with Dask
    Cloud Provider and then using `LocalEnvironment` with a `DaskExecutor`
    will result in a much better development experience.

    (Dask Cloud Provider currently only supports AWS using either Fargate or ECS.
    Support for AzureML is coming soon.)

    *IMPORTANT* By default, Dask Cloud Provider may create a Dask cluster in some
    environments (e.g. Fargate) that is accessible via a public IP, without any
    authentication, and configured to NOT encrypt network traffic. Please be
    conscious of security issues if you test this environment. (Also see pull
    requests [85](https://github.com/dask/dask-cloudprovider/pull/85) and
    [91](https://github.com/dask/dask-cloudprovider/pull/91) in the Dask Cloud
    Provider project.)

    Args:
        - provider_class (class): Class of a provider from the Dask Cloud Provider
            projects. Current supported options are `ECSCluster` and `FargateCluster`.
        - adaptive_min_workers (int, optional): Minimum number of workers for adaptive
            mode. If this value is None, then adaptive mode will not be used and you
            should pass `n_workers` or the appropriate kwarg for the provider class you
            are using.
        - adaptive_max_workers (int, optional): Maximum number of workers for adaptive
            mode.
        - security (Type[Security], optional): a Dask Security object from
            `distributed.security.Security`.  Use this to connect to a Dask cluster that is
            enabled with TLS encryption.  For more on using TLS with Dask see
            https://distributed.dask.org/en/latest/tls.html
        - executor_kwargs (dict, optional): a dictionary of kwargs to be passed to
            the executor; defaults to an empty dictionary
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
        - on_execute (Callable[[Dict[str, Any], Dict[str, Any]], None], optional): a function
            callback which will be called before the flow begins to run. The callback function
            can examine the Flow run parameters and modify  kwargs to be passed to the Dask
            Cloud Provider class's constructor prior to launching the Dask cluster for the Flow
            run.  This allows for dynamically sizing the cluster based on the Flow run
            parameters, e.g.  settings n_workers. The callback function's signature should be:
            `on_execute(parameters: Dict[str, Any], provider_kwargs: Dict[str, Any]) -> None`
            The callback function may modify provider_kwargs
            (e.g.  `provider_kwargs["n_workers"] = 3`) and any relevant changes will be used when
            creating the Dask cluster via a Dask Cloud Provider class.
        - on_start (Callable, optional): a function callback which will be called before the
            flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow
            finishes its run
        - metadata (dict, optional): extra metadata to be set and serialized on this environment
        - **kwargs (dict, optional): additional keyword arguments to pass to boto3 for
            `register_task_definition` and `run_task`
    """

    def __init__(  # type: ignore
        self,
        provider_class: Type[Cluster],
        adaptive_min_workers: int = None,
        adaptive_max_workers: int = None,
        security: Security = None,
        executor_kwargs: Dict[str, Any] = None,
        labels: List[str] = None,
        on_execute: Callable[[Dict[str, Any], Dict[str, Any]], None] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        metadata: dict = None,
        **kwargs
    ) -> None:
        self._provider_class = provider_class
        self._adaptive_min_workers = adaptive_min_workers
        self._adaptive_max_workers = adaptive_max_workers
        self._on_execute = on_execute
        self._provider_kwargs = kwargs
        if "skip_cleanup" not in self._provider_kwargs:
            # Prefer this default (if not provided) to avoid deregistering task definitions See
            # this issue in Dask Cloud Provider:
            # https://github.com/dask/dask-cloudprovider/issues/94
            self._provider_kwargs["skip_cleanup"] = True
        self._security = security
        if self._security:
            # We'll use the security config object both for our Dask Client connection *and*
            # for the particular Dask Cloud Provider (e.g. Fargate) to use with *its* Dask
            # Client when it connects to the scheduler after cluster creation. So we
            # put it in _provider_kwargs so it gets passed to the Dask Cloud Provider's constructor
            self._provider_kwargs["security"] = self._security
        self.cluster = None
        super().__init__(
            address="",  # The scheduler address will be set after cluster creation
            executor_kwargs=executor_kwargs,
            labels=labels,
            on_start=on_start,
            on_exit=on_exit,
            metadata=metadata,
            security=self._security,
        )

    @property
    def dependencies(self) -> list:
        return ["dask_cloudprovider"]

    def _create_dask_cluster(self) -> None:
        self.logger.info("Creating Dask cluster using {}".format(self._provider_class))
        self.cluster = self._provider_class(**self._provider_kwargs)
        if self.cluster and self.cluster.scheduler and self.cluster.scheduler.address:
            self.logger.info(
                "Dask cluster created. Scheduler address: {} Dashboard: http://{}:8787 "
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
        self, flow: "Flow", **kwargs: Any  # type: ignore
    ) -> None:
        flow_run_info = None
        flow_run_id = prefect.context.get("flow_run_id")
        if self._on_execute:
            # If an on_execute Callable has been provided, retrieve the flow run parameters
            # and then allow the Callable a chance to update _provider_kwargs. This allows
            # better sizing of the cluster resources based on parameters for this Flow run.
            try:
                client = Client()
                flow_run_info = client.get_flow_run_info(flow_run_id)
                parameters = flow_run_info.parameters or {}  # type: ignore
                self._on_execute(parameters, self._provider_kwargs)
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
                if not flow_id:  # We've observed cases where flow_id is None
                    if not flow_run_info:
                        flow_run_info = client.get_flow_run_info(flow_run_id)
                    flow_id = flow_run_info.flow_id
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
        super().execute(flow, **kwargs)

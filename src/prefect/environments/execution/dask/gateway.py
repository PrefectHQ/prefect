""" This class borrows heavily from the DaskCloudProviderEnvironment in this PR -> https://github.com/PrefectHQ/prefect/pull/2360/files#diff-03e026e9e7da65aac3aa27acb35b8520 """
from typing import Any, Callable, Dict, List

import prefect
from dask_gateway import Gateway
from dask_gateway.auth import BasicAuth
from prefect import Client
from prefect.environments.execution.dask.remote import RemoteDaskEnvironment


class DaskGatewayEnvironment(RemoteDaskEnvironment):
    """
    The DaskGatewayEnvironment dynamically creates Dask clusters via a Dask Gateway instance. 
    For each flow run, a new Dask cluster will be created and the
    flow will run using a `RemoteDaskEnvironment` with the Dask scheduler address
    from the newly created Dask cluster. You can specify the number of Dask workers
    manually (for example, passing the kwarg `n_workers`) or enable adaptive mode by
    passing `adaptive_min_workers` and, optionally, `adaptive_max_workers`. This
    environment aims to provide a very easy path to Dask scalability for users of Dask Gateway.
    **NOTE:** Cluster startup time can be slow, depending
    on docker image size and the possibility of having to wait for a new node to spin up
    if using auto-scaling. Total startup time for a Dask scheduler and workers can
    be several minutes. This environment is a much better fit for production
    deployments of scheduled Flows where there's little sensitivity to startup
    time. `DaskGatewayEnvironment` is a particularly good fit for automated
    deployment of Flows in a CI/CD pipeline where the infrastructure for each Flow
    should be as independent as possible, e.g. each Flow could have its own docker
    image, dynamically create the Dask cluster to run on, etc. However, for
    development and interactive testing, creating a Dask cluster manually with Dask Gateway and then using `DaskExecutor`
    with your flows will result in a much better development experience.
    **NOTE**: This environment will leave the cluster up if something on the Dask side
    breaks to assist in debugging (this is NOT the case if it is just a Prefect task failure).
    Args:
        - gateway_address (str): The hostname for the Dask Gateway instance
        - auth (BasicAuth, optional): a Dask Gateway authentication object. Currently only supports the BasicAuth method.
        - adaptive_min_workers (int, optional): Minimum number of workers for adaptive
            mode. If this value is None, then adaptive mode will not be used and you
            should pass `n_workers` or the appropriate kwarg for the provider class you
            are using.
        - adaptive_max_workers (int, optional): Maximum number of workers for adaptive
            mode.
        - executor_kwargs (dict, optional): a dictionary of kwargs to be passed to
            the executor; defaults to an empty dictionary
        - image: (str, optional): the Docker image to be used when creating the scheduler + workers. If this value
            none, then the image will be set based on the storage metadata of the Flow.
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_execute (Callable[[Dict[str, Any], Dict[str, Any]], None], optional): a function callback which will
            be called before the flow begins to run. The callback function can examine the Flow run
            parameters and modify  kwargs to be passed to the Dask Cloud Provider class's constructor prior
            to launching the Dask cluster for the Flow run. This allows for dynamically sizing the cluster based
            on the Flow run parameters, e.g. settings n_workers. The callback function's signature should be:
                `def on_execute(parameters: Dict[str, Any], provider_kwargs: Dict[str, Any]) -> None:`
            The callback function may modify provider_kwargs (e.g. `provider_kwargs["n_workers"] = 3`) and any
            relevant changes will be used when creating the Dask cluster via a Dask Cloud Provider class.
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
    """

    def __init__(  # type: ignore
        self,
        gateway_address: str,
        auth: BasicAuth = None,
        adaptive_min_workers: int = None,
        adaptive_max_workers: int = None,
        executor_kwargs: Dict[str, Any] = None,
        image: str = None,
        labels: List[str] = None,
        on_execute: Callable[[Dict[str, Any], Dict[str, Any]], None] = None,
        on_exit: Callable = None,
        on_start: Callable = None,
    ) -> None:
        self._gateway_address = gateway_address
        self._auth = auth
        self._adaptive_min_workers = adaptive_min_workers
        self._adaptive_max_workers = adaptive_max_workers
        self._image = image
        self._on_execute = on_execute
        self.cluster = None
        self.gateway = None
        super().__init__(
            address="",  # The scheduler address will be set after cluster creation
            executor_kwargs=executor_kwargs,
            labels=labels,
            on_start=on_start,
            on_exit=on_exit,
        )

    @property
    def dependencies(self) -> list:
        return ["dask_gateway"]

    def _create_dask_cluster(self) -> None:
        self.logger.info("Creating Dask cluster using Dask Gateway")
        self.logger.info(self._gateway_address)
        self.gateway = Gateway(address=self._gateway_address, auth=self._auth)
        self.cluster = self.gateway.new_cluster(
            image=self._image, shutdown_on_close=False
        )
        if self.cluster and self.cluster.scheduler_address:
            self.logger.info(
                f"Dask cluster created. Scheduler address: {self.cluster.scheduler_address}"
            )

            self.executor_kwargs["address"] = self.cluster.scheduler_address  # type: ignore
            self.executor_kwargs["security"] = self.cluster.security  # type: ignore
        else:
            if self.cluster:
                self.cluster.shutdown()
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
        self.logger.info("yeet")
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
                self._on_execute(parameters)
            except Exception as exc:
                self.logger.info(
                    "Failed to retrieve flow run info with error: {}".format(repr(exc))
                )
        if not self._image:
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
                self._image = image
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
        self.cluster.shutdown()

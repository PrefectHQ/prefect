import os
import uuid
import warnings
from typing import Any, Callable, List, TYPE_CHECKING

import yaml

import prefect
from prefect.environments.execution.base import Environment, _RunMixin
from prefect.utilities.storage import get_flow_image

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


class KubernetesJobEnvironment(Environment, _RunMixin):
    """
    KubernetesJobEnvironment is an environment which deploys your flow as a Kubernetes
    job. This environment allows (and requires) a custom job YAML spec to be provided.

    When providing a custom YAML job spec the first container in the spec must be the
    container that the flow runner will be executed on.

    The following environment variables, required for cloud, do not need to be
    included––they are automatically added and populated during execution:

    - `PREFECT__CLOUD__GRAPHQL`
    - `PREFECT__CLOUD__AUTH_TOKEN`
    - `PREFECT__CONTEXT__FLOW_RUN_ID`
    - `PREFECT__CONTEXT__NAMESPACE`
    - `PREFECT__CONTEXT__IMAGE`
    - `PREFECT__CLOUD__USE_LOCAL_SECRETS`
    - `PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS`
    - `PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS`
    - `PREFECT__LOGGING__LOG_TO_CLOUD`
    - `PREFECT__LOGGING__EXTRA_LOGGERS`

    Additionally, the following command will be applied to the first container:
    `$ /bin/sh -c "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'"`

    Args:
        - job_spec_file (str, optional): Path to a job spec YAML file
        - unique_job_name (bool, optional): whether to use a unique name for each job created with this environment. Defaults
            to `False`
        - executor (Executor, optional): the executor to run the flow with. If not provided, the
            default executor will be used.
        - executor_kwargs (dict, optional): DEPRECATED
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
        - metadata (dict, optional): extra metadata to be set and serialized on this environment
    """

    def __init__(
        self,
        job_spec_file: str = None,
        unique_job_name: bool = False,
        executor: "prefect.engine.executors.Executor" = None,
        executor_kwargs: dict = None,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        metadata: dict = None,
    ) -> None:
        self.job_spec_file = os.path.abspath(job_spec_file) if job_spec_file else None
        self.unique_job_name = unique_job_name

        if executor_kwargs is not None:
            warnings.warn("`executor_kwargs` is deprecated, use `executor` instead")
        if executor is None:
            executor = prefect.engine.get_default_executor_class()(
                **(executor_kwargs or {})
            )
        elif not isinstance(executor, prefect.engine.executors.Executor):
            raise TypeError(
                f"`executor` must be an `Executor` or `None`, got `{executor}`"
            )
        self.executor = executor

        # Load specs from file if path given, store on object
        self._job_spec = self._load_spec_from_file()

        self._identifier_label = ""

        super().__init__(
            labels=labels, on_start=on_start, on_exit=on_exit, metadata=metadata
        )

    @property
    def dependencies(self) -> list:
        return ["kubernetes"]

    @property
    def identifier_label(self) -> str:
        if not hasattr(self, "_identifier_label") or not self._identifier_label:
            self._identifier_label = str(uuid.uuid4())
        return self._identifier_label

    def __getstate__(self) -> dict:
        state = self.__dict__.copy()
        # Ensure _identifier_label is not persisted
        if "_identifier_label" in state:
            del state["_identifier_label"]
        return state

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)

    def execute(  # type: ignore
        self, flow: "Flow", **kwargs: Any
    ) -> None:
        """
        Create a single Kubernetes job that runs the flow.

        Args:
            - flow (Flow): the Flow object
            - **kwargs (Any): additional keyword arguments to pass to the runner

        Raises:
            - Exception: if the environment is unable to create the Kubernetes job
        """
        docker_name = get_flow_image(flow)

        from kubernetes import client, config

        # Verify environment is running in cluster
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            self.logger.error("Environment not currently running inside a cluster")
            raise EnvironmentError("Environment not currently inside a cluster")

        batch_client = client.BatchV1Api()

        job = self._populate_job_spec_yaml(
            yaml_obj=self._job_spec, docker_name=docker_name,
        )

        # Create Job
        try:
            batch_client.create_namespaced_job(
                namespace=prefect.context.get("namespace"), body=job
            )
        except Exception as exc:
            self.logger.critical("Failed to create Kubernetes job: {}".format(exc))
            raise exc

    ###############################
    # Custom YAML Spec Manipulation
    ###############################

    def _populate_job_spec_yaml(self, yaml_obj: dict, docker_name: str,) -> dict:
        """
        Populate the custom execution job yaml object used in this environment with the proper values

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml
            - docker_name (str): the full path to the docker image

        Returns:
            - dict: a dictionary with the yaml values replaced
        """
        flow_run_id = prefect.context.get("flow_run_id", "unknown")

        # Create metadata label fields if they do not exist
        if not yaml_obj.get("metadata"):
            yaml_obj["metadata"] = {}

        if self.unique_job_name:
            yaml_obj["metadata"][
                "name"
            ] = f"{yaml_obj['metadata']['name']}-{str(uuid.uuid4())[:8]}"

        if not yaml_obj["metadata"].get("labels"):
            yaml_obj["metadata"]["labels"] = {}

        if not yaml_obj["spec"]["template"].get("metadata"):
            yaml_obj["spec"]["template"]["metadata"] = {}

        if not yaml_obj["spec"]["template"]["metadata"].get("labels"):
            yaml_obj["spec"]["template"]["metadata"]["labels"] = {}

        # Populate metadata label fields
        k8s_labels = {
            "prefect.io/identifier": self.identifier_label,
            "prefect.io/flow_run_id": flow_run_id,
        }
        yaml_obj["metadata"]["labels"].update(k8s_labels)
        yaml_obj["spec"]["template"]["metadata"]["labels"].update(k8s_labels)

        # Required Cloud environment variables
        env_values = [
            {"name": "PREFECT__CLOUD__GRAPHQL", "value": prefect.config.cloud.graphql},
            {
                "name": "PREFECT__CLOUD__AUTH_TOKEN",
                "value": prefect.config.cloud.auth_token,
            },
            {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": flow_run_id},
            {
                "name": "PREFECT__CONTEXT__NAMESPACE",
                "value": prefect.context.get("namespace", ""),
            },
            {"name": "PREFECT__CONTEXT__IMAGE", "value": docker_name},
            {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
            {
                "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                "value": "prefect.engine.cloud.CloudFlowRunner",
            },
            {
                "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                "value": "prefect.engine.cloud.CloudTaskRunner",
            },
            {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "true"},
            {
                "name": "PREFECT__LOGGING__EXTRA_LOGGERS",
                "value": str(prefect.config.logging.extra_loggers),
            },
        ]

        # set environment variables on all containers
        for container in yaml_obj["spec"]["template"]["spec"]["containers"]:
            if not container.get("env"):
                container["env"] = []
            container["env"].extend(env_values)

        # set image on first container
        if not yaml_obj["spec"]["template"]["spec"]["containers"][0].get("image"):
            yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"] = ""

        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"] = docker_name

        # set command on first container
        if not yaml_obj["spec"]["template"]["spec"]["containers"][0].get("command"):
            yaml_obj["spec"]["template"]["spec"]["containers"][0]["command"] = []

        yaml_obj["spec"]["template"]["spec"]["containers"][0]["command"] = [
            "/bin/sh",
            "-c",
        ]

        # set args on first container
        if not yaml_obj["spec"]["template"]["spec"]["containers"][0].get("args"):
            yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"] = []

        yaml_obj["spec"]["template"]["spec"]["containers"][0]["args"] = [
            "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'"
        ]

        return yaml_obj

    def _load_spec_from_file(self) -> dict:
        """
        Load job spec from provided file path

        Returns:
            - dict: job spec dictionary
        """
        job = dict()  # type: ignore

        if self.job_spec_file:
            with open(self.job_spec_file) as job_spec_file:
                job = yaml.safe_load(job_spec_file)

        return job

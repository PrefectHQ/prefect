import os
import uuid
from typing import Any, Callable, List

import cloudpickle
import yaml

import prefect
from prefect.environments.execution import Environment
from prefect.environments.storage import Docker


class KubernetesJobEnvironment(Environment):
    """
    KubernetesJobEnvironment is an environment which deploys your flow (stored in a Docker image)
    as a Kubernetes job. This environment allows (and requires) a custom job YAML spec to be
    provided.

    When providing a custom YAML job spec the first container in the spec must be the
    container that the flow runner will be executed on.

    These environment variables are required for cloud do not need to be included because
    they are instead automatically added and populated during execution:

    - `PREFECT__CLOUD__GRAPHQL`
    - `PREFECT__CLOUD__AUTH_TOKEN`
    - `PREFECT__CONTEXT__FLOW_RUN_ID`
    - `PREFECT__CONTEXT__NAMESPACE`
    - `PREFECT__CONTEXT__IMAGE`
    - `PREFECT__CONTEXT__FLOW_FILE_PATH`
    - `PREFECT__CLOUD__USE_LOCAL_SECRETS`
    - `PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS`
    - `PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS`
    - `PREFECT__LOGGING__LOG_TO_CLOUD`

    Additionally, the following command will be applied to the first container:
    `$ /bin/sh -c "python -c 'import prefect; prefect.Flow.load(prefect.context.flow_file_path).environment.run_flow()'"`

    Args:
        - job_spec_file (str, optional): Path to a job spec YAML file
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow finishes its run
    """

    def __init__(
        self,
        job_spec_file: str = None,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
    ) -> None:
        self.job_spec_file = os.path.abspath(job_spec_file) if job_spec_file else None

        # Load specs from file if path given, store on object
        self._job_spec = self._load_spec_from_file()

        self._identifier_label = ""

        super().__init__(labels=labels, on_start=on_start, on_exit=on_exit)

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
        self, storage: "Docker", flow_location: str, **kwargs: Any
    ) -> None:
        """
        Create a single Kubernetes job that runs the flow.

        Args:
            - storage (Docker): the Docker storage object that contains information relating
                to the image which houses the flow
            - flow_location (str): the location of the Flow to execute
            - **kwargs (Any): additional keyword arguments to pass to the runner

        Raises:
            - TypeError: if the storage is not `Docker`
        """
        if not isinstance(storage, Docker):
            raise TypeError("CloudEnvironment requires a Docker storage option")

        self.create_flow_run_job(docker_name=storage.name, flow_file_path=flow_location)

    def create_flow_run_job(self, docker_name: str, flow_file_path: str) -> None:
        """
        Creates a Kubernetes job to run the flow using the information stored on the
        Docker storage object.

        Args:
            - docker_name (str): the full name of the docker image (registry/name:tag)
            - flow_file_path (str): location of the flow file in the image
        """
        from kubernetes import client, config

        # Verify environment is running in cluster
        try:
            config.load_incluster_config()
        except config.config_exception.ConfigException:
            self.logger.error("Environment not currently running inside a cluster")
            raise EnvironmentError("Environment not currently inside a cluster")

        batch_client = client.BatchV1Api()

        job = self._populate_job_spec_yaml(
            yaml_obj=self._job_spec,
            docker_name=docker_name,
            flow_file_path=flow_file_path,
        )

        # Create Job
        try:
            batch_client.create_namespaced_job(
                namespace=prefect.context.get("namespace"), body=job
            )
        except Exception as exc:
            self.logger.critical("Failed to create Kubernetes job: {}".format(exc))
            raise exc

    def run_flow(self) -> None:
        """
        Run the flow from specified flow_file_path location using the default executor
        """

        # Call on_start callback if specified
        if self.on_start:
            self.on_start()

        try:
            from prefect.engine import (
                get_default_flow_runner_class,
                get_default_executor_class,
            )

            # Load serialized flow from file and run it with the executor
            with open(
                prefect.context.get(
                    "flow_file_path", "/root/.prefect/flow_env.prefect"
                ),
                "rb",
            ) as f:
                flow = cloudpickle.load(f)

                runner_cls = get_default_flow_runner_class()
                executor_cls = get_default_executor_class()()
                runner_cls(flow=flow).run(executor=executor_cls)
        except Exception as exc:
            self.logger.exception(
                "Unexpected error raised during flow run: {}".format(exc)
            )
            raise exc
        finally:
            # Call on_exit callback if specified
            if self.on_exit:
                self.on_exit()

    ###############################
    # Custom YAML Spec Manipulation
    ###############################

    def _populate_job_spec_yaml(
        self, yaml_obj: dict, docker_name: str, flow_file_path: str
    ) -> dict:
        """
        Populate the custom execution job yaml object used in this environment with the proper values

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml
            - docker_name (str): the full path to the docker image
            - flow_file_path (str): the location of the flow within the docker container

        Returns:
            - dict: a dictionary with the yaml values replaced
        """
        flow_run_id = prefect.context.get("flow_run_id", "unknown")

        # Create metadata label fields if they do not exist
        if not yaml_obj.get("metadata"):
            yaml_obj["metadata"] = {}

        if not yaml_obj["metadata"].get("labels"):
            yaml_obj["metadata"]["labels"] = {}

        if not yaml_obj["spec"]["template"].get("metadata"):
            yaml_obj["spec"]["template"]["metadata"] = {}

        if not yaml_obj["spec"]["template"]["metadata"].get("labels"):
            yaml_obj["spec"]["template"]["metadata"]["labels"] = {}

        # Populate metadata label fields
        yaml_obj["metadata"]["labels"]["identifier"] = self.identifier_label
        yaml_obj["metadata"]["labels"]["flow_run_id"] = flow_run_id
        yaml_obj["spec"]["template"]["metadata"]["labels"][
            "identifier"
        ] = self.identifier_label

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
            {"name": "PREFECT__CONTEXT__FLOW_FILE_PATH", "value": flow_file_path},
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
            "python -c 'import prefect; prefect.Flow.load(prefect.context.flow_file_path).environment.run_flow()'"
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

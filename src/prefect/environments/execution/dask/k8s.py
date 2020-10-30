import base64
import json
import uuid
from os import path
from typing import Callable, List, TYPE_CHECKING
import warnings

import yaml

import prefect
from prefect.client import Secret
from prefect.environments.execution import Environment
from prefect.utilities.storage import get_flow_image

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611


class DaskKubernetesEnvironment(Environment):
    """
    DaskKubernetesEnvironment is an environment which deploys your flow on Kubernetes by
    spinning up a temporary Dask Cluster (using
    [dask-kubernetes](https://kubernetes.dask.org/en/latest/)) and running the Prefect
    `DaskExecutor` on this cluster.

    When running your flows that are registered with a private container registry, you should
    either specify the name of an `image_pull_secret` on the flow's `DaskKubernetesEnvironment`
    or directly set the `imagePullSecrets` on your custom worker/scheduler specs.

    It is possible to provide a custom scheduler and worker spec YAML files through the
    `scheduler_spec_file` and `worker_spec_file` arguments. These specs (if provided) will be
    used in place of the defaults. Your spec files should be modeled after the job.yaml and
    worker_pod.yaml found
    [here](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/environments/execution/dask).
    The main aspects to be aware of are the `command` and `args` on the container. The
    following environment variables, required for cloud, do not need to be included––they are
    automatically added and populated during execution:

    - `PREFECT__CLOUD__GRAPHQL`
    - `PREFECT__CLOUD__AUTH_TOKEN`
    - `PREFECT__CONTEXT__FLOW_RUN_ID`
    - `PREFECT__CONTEXT__NAMESPACE`
    - `PREFECT__CONTEXT__IMAGE`
    - `PREFECT__CLOUD__USE_LOCAL_SECRETS`
    - `PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS`
    - `PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS`
    - `PREFECT__ENGINE__EXECUTOR__DEFAULT_CLASS`
    - `PREFECT__LOGGING__LEVEL`
    - `PREFECT__LOGGING__LOG_TO_CLOUD`
    - `PREFECT__LOGGING__EXTRA_LOGGERS`

    Note: the logging attributes are only populated if they are not already provided.

    Args:
        - min_workers (int, optional): the minimum allowed number of Dask worker pods; defaults to 1
        - max_workers (int, optional): the maximum allowed number of Dask worker pods; defaults to 1
        - work_stealing (bool, optional): toggle Dask Distributed scheduler work stealing;
            defaults to False Only used when a custom scheduler spec is not provided. Enabling
            this may cause ClientErrors to appear when multiple Dask workers try to run the
            same Prefect Task.
            `Warning`:  `work_stealing` if provided won't be appended to your custom
            `scheduler_spec_file`. If wanted, don't forget to add it in your container env
            (`DASK_DISTRIBUTED__SCHEDULER__WORK_STEALING`).
        - scheduler_logs (bool, optional): log all Dask scheduler logs, defaults to False
        - private_registry (bool, optional, DEPRECATED): a boolean specifying whether your
            Flow's Docker container will be in a private Docker registry; if so, requires a
            Prefect Secret containing your docker credentials to be set.  Defaults to `False`.
        - docker_secret (str, optional, DEPRECATED): the name of the Prefect Secret containing
            your Docker credentials; defaults to `"DOCKER_REGISTRY_CREDENTIALS"`.  This Secret
            should be a dictionary containing the following keys: `"docker-server"`,
            `"docker-username"`, `"docker-password"`, and `"docker-email"`.
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
        - on_start (Callable, optional): a function callback which will be called before the
            flow begins to run
        - on_exit (Callable, optional): a function callback which will be called after the flow
            finishes its run
        - metadata (dict, optional): extra metadata to be set and serialized on this environment
        - scheduler_spec_file (str, optional): Path to a scheduler spec YAML file
        - worker_spec_file (str, optional): Path to a worker spec YAML file
        - image_pull_secret (str, optional): optional name of an `imagePullSecret` to use for
            the scheduler and worker pods. To specify multiple image pull secrets, provide a comma
            delimited string with no spaces, like `"some-secret,other-secret"`.
            For more information go
            [here](https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/).
            `Warning`:  `image_pull_secret` if provided won't be appended to your custom
            `worker_spec_file` or `scheduler_spec_file`. If you want it, don't forget to add it in
            your spec files.
        - log_k8s_errors (bool, optional): optional toggle to also log Kubernetes errors that may occur
            using the Prefect logger. Defaults to `False`.
    """

    def __init__(
        self,
        min_workers: int = 1,
        max_workers: int = 2,
        work_stealing: bool = True,
        scheduler_logs: bool = False,
        private_registry: bool = False,
        docker_secret: str = None,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        metadata: dict = None,
        scheduler_spec_file: str = None,
        worker_spec_file: str = None,
        image_pull_secret: str = None,
        log_k8s_errors: bool = False,
    ) -> None:
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.work_stealing = work_stealing
        self.scheduler_logs = scheduler_logs
        self.private_registry = private_registry
        if self.private_registry:
            self.docker_secret = docker_secret or "DOCKER_REGISTRY_CREDENTIALS"

            warnings.warn(
                "The `private_registry` and `docker_secret` options are deprecated. "
                "Please set `imagePullSecrets` on custom work and scheduler YAML manifests.",
                stacklevel=2,
            )
        else:
            self.docker_secret = None  # type: ignore
        self.scheduler_spec_file = scheduler_spec_file
        self.worker_spec_file = worker_spec_file
        self.image_pull_secret = image_pull_secret

        # Load specs from file if path given, store on object
        self._scheduler_spec, self._worker_spec = self._load_specs_from_file()

        self._identifier_label = ""
        self.log_k8s_errors = log_k8s_errors

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

    def setup(self, flow: "Flow") -> None:  # type: ignore
        if self.private_registry:
            from kubernetes import client, config

            # Verify environment is running in cluster
            try:
                config.load_incluster_config()
            except config.config_exception.ConfigException:
                self.logger.error("Environment not currently running inside a cluster")
                raise EnvironmentError("Environment not currently inside a cluster")

            v1 = client.CoreV1Api()
            namespace = prefect.context.get("namespace", "default")
            secret_name = namespace + "-docker"
            secrets = v1.list_namespaced_secret(namespace=namespace, watch=False)
            if not [
                secret
                for secret in secrets.items
                if secret.metadata.name == secret_name
            ]:
                self.logger.debug(
                    "Docker registry secret {} does not exist for this tenant.".format(
                        secret_name
                    )
                )
                self._create_namespaced_secret()
            else:
                self.logger.debug(
                    "Docker registry secret {} found.".format(secret_name)
                )

    def execute(self, flow: "Flow") -> None:  # type: ignore
        """
        Create a single Kubernetes job that spins up a dask scheduler, dynamically
        creates worker pods, and runs the flow.

        Args:
            - flow (Flow): the Flow object

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

        if self._scheduler_spec:
            job = self._scheduler_spec
            job = self._populate_scheduler_spec_yaml(
                yaml_obj=job, docker_name=docker_name
            )
        else:
            with open(path.join(path.dirname(__file__), "job.yaml")) as job_file:
                job = yaml.safe_load(job_file)
                job = self._populate_job_yaml(yaml_obj=job, docker_name=docker_name)

        # Create Job
        try:
            batch_client.create_namespaced_job(
                namespace=prefect.context.get("namespace"), body=job
            )
        except Exception as exc:
            self.logger.critical("Failed to create Kubernetes job: {}".format(exc))
            raise exc

    def _create_namespaced_secret(self) -> None:
        self.logger.debug(
            'Creating Docker registry kubernetes secret from "{}" Prefect Secret.'.format(
                self.docker_secret
            )
        )
        try:
            from kubernetes import client

            docker_creds = Secret(self.docker_secret).get()
            assert isinstance(docker_creds, dict)

            v1 = client.CoreV1Api()
            cred_payload = {
                "auths": {
                    docker_creds["docker-server"]: {
                        "Username": docker_creds["docker-username"],
                        "Password": docker_creds["docker-password"],
                        "Email": docker_creds["docker-email"],
                    }
                }
            }
            data = {
                ".dockerconfigjson": base64.b64encode(
                    json.dumps(cred_payload).encode()
                ).decode()
            }
            namespace = prefect.context.get("namespace", "unknown")
            name = namespace + "-docker"
            secret = client.V1Secret(
                api_version="v1",
                data=data,
                kind="Secret",
                metadata=dict(name=name, namespace=namespace),
                type="kubernetes.io/dockerconfigjson",
            )
            v1.create_namespaced_secret(namespace, body=secret)
            self.logger.debug("Created Docker registry secret {}.".format(name))
        except Exception as exc:
            self.logger.error(
                "Failed to create Kubernetes secret for private Docker registry: {}".format(
                    exc
                )
            )
            raise exc

    def run(self, flow: "Flow") -> None:
        """
        Run the flow using a temporary dask-kubernetes cluster.

        Args:
            - flow (Flow): the flow to run.
        """
        # Call on_start callback if specified
        if self.on_start:
            self.on_start()

        try:
            from prefect.engine import get_default_flow_runner_class
            from prefect.engine.executors import DaskExecutor
            from dask_kubernetes import KubeCluster

            if self._worker_spec:
                worker_pod = self._worker_spec
                worker_pod = self._populate_worker_spec_yaml(yaml_obj=worker_pod)
            else:
                with open(
                    path.join(path.dirname(__file__), "worker_pod.yaml")
                ) as pod_file:
                    worker_pod = yaml.safe_load(pod_file)
                    worker_pod = self._populate_worker_pod_yaml(yaml_obj=worker_pod)

            cluster = KubeCluster.from_dict(
                worker_pod, namespace=prefect.context.get("namespace")
            )
            cluster.adapt(minimum=self.min_workers, maximum=self.max_workers)

            executor = DaskExecutor(address=cluster.scheduler_address)
            runner_cls = get_default_flow_runner_class()
            runner_cls(flow=flow).run(executor=executor)
        except Exception as exc:
            self.logger.exception(
                "Unexpected error raised during flow run: {}".format(exc)
            )
            raise exc
        finally:
            # Call on_exit callback if specified
            if self.on_exit:
                self.on_exit()

    def _extra_loggers(self) -> str:
        """
        Set dask-kubernetes related loggers for debugging and providing more
        visibility into the workings of the Dask cluster. These loggers are useful
        for information about cluster autoscaling and possible kubernetes issues
        that may otherwise be hidden.

        Specifying `scheduler_logs=True` on this environment will also elevate the Dask
        scheduler logs. This will lead to a large increase in the amount of logs created
        and should only be used for debugging purposes.

        Returns:
            - str: a string representation of a list of extra loggers to use
        """
        cluster_loggers = [
            "dask_kubernetes.core",
            "distributed.deploy.adaptive",
        ]

        if self.log_k8s_errors:
            cluster_loggers.append("kubernetes")

        config_extra_loggers = prefect.config.logging.extra_loggers

        extra_loggers = [*config_extra_loggers, *cluster_loggers]

        if self.scheduler_logs:
            extra_loggers.append("distributed.scheduler")
        return str(extra_loggers)

    ################################
    # Default YAML Spec Manipulation
    ################################

    def _set_prefect_labels(self, obj: dict) -> None:
        flow_run_id = prefect.context.get("flow_run_id", "unknown")
        labels = {
            "prefect.io/identifier": self.identifier_label,
            "prefect.io/flow_run_id": flow_run_id,
        }
        obj.setdefault("metadata", {}).setdefault("labels", {}).update(labels)

    def _populate_job_yaml(self, yaml_obj: dict, docker_name: str) -> dict:
        """
        Populate the execution job yaml object used in this environment with the proper values

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml
            - docker_name (str): the full path to the docker image

        Returns:
            - dict: a dictionary with the yaml values replaced
        """
        flow_run_id = prefect.context.get("flow_run_id", "unknown")
        namespace = prefect.context.get("namespace", "unknown")

        # set identifier labels
        yaml_obj["metadata"]["name"] = "prefect-dask-job-{}".format(
            self.identifier_label
        )
        self._set_prefect_labels(yaml_obj)
        self._set_prefect_labels(yaml_obj["spec"]["template"])

        # set environment variables
        env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]
        pod_spec = yaml_obj["spec"]["template"]["spec"]
        if self.private_registry:
            pod_spec["imagePullSecrets"] = []
            pod_spec["imagePullSecrets"].append({"name": namespace + "-docker"})
        elif self.image_pull_secret:
            pod_spec["imagePullSecrets"] = []
            secrets = self.image_pull_secret.split(",")
            for secret_name in secrets:
                pod_spec["imagePullSecrets"].append({"name": secret_name})

        env[0]["value"] = prefect.config.cloud.graphql
        env[1]["value"] = prefect.config.cloud.auth_token
        env[2]["value"] = flow_run_id
        env[3]["value"] = prefect.context.get("namespace", "default")
        env[4]["value"] = docker_name
        env[12]["value"] = str(self.work_stealing)
        env[13]["value"] = self._extra_loggers()

        # set image
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"] = docker_name

        return yaml_obj

    def _populate_worker_pod_yaml(self, yaml_obj: dict) -> dict:
        """
        Populate the worker pod yaml object used in this environment with the proper values.

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml

        Returns:
            - dict: a dictionary with the yaml values replaced
        """
        # set identifier labels
        self._set_prefect_labels(yaml_obj)

        # set environment variables
        env = yaml_obj["spec"]["containers"][0]["env"]

        env[0]["value"] = prefect.config.cloud.graphql
        env[1]["value"] = prefect.config.cloud.auth_token
        env[2]["value"] = prefect.context.get("flow_run_id", "")
        env[10]["value"] = self._extra_loggers()

        pod_spec = yaml_obj["spec"]
        if self.private_registry:
            namespace = prefect.context.get("namespace", "default")
            pod_spec["imagePullSecrets"] = []
            pod_spec["imagePullSecrets"].append({"name": namespace + "-docker"})
        elif self.image_pull_secret:
            pod_spec["imagePullSecrets"] = []
            secrets = self.image_pull_secret.split(",")
            for secret_name in secrets:
                pod_spec["imagePullSecrets"].append({"name": secret_name})

        # set image
        yaml_obj["spec"]["containers"][0]["image"] = prefect.context.get(
            "image", "daskdev/dask:latest"
        )

        return yaml_obj

    ###############################
    # Custom YAML Spec Manipulation
    ###############################

    def _populate_scheduler_spec_yaml(self, yaml_obj: dict, docker_name: str) -> dict:
        """
        Populate the custom execution job yaml object used in this environment with the proper
        values.

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml
            - docker_name (str): the full path to the docker image

        Returns:
            - dict: a dictionary with the yaml values replaced
        """
        flow_run_id = prefect.context.get("flow_run_id", "unknown")

        yaml_obj["metadata"]["name"] = "prefect-dask-job-{}".format(
            self.identifier_label
        )
        self._set_prefect_labels(yaml_obj)
        self._set_prefect_labels(yaml_obj["spec"]["template"])

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
                "value": prefect.context.get("namespace", "default"),
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
            {
                "name": "PREFECT__ENGINE__EXECUTOR__DEFAULT_CLASS",
                "value": "prefect.engine.executors.DaskExecutor",
            },
        ]

        # Logging env vars
        log_vars = [
            {
                "name": "PREFECT__LOGGING__LOG_TO_CLOUD",
                "value": str(prefect.config.logging.log_to_cloud).lower(),
            },
            {
                "name": "PREFECT__LOGGING__LEVEL",
                "value": str(prefect.config.logging.level),
            },
            {
                "name": "PREFECT__LOGGING__EXTRA_LOGGERS",
                "value": self._extra_loggers(),
            },
        ]

        # set environment variables
        env = yaml_obj["spec"]["template"]["spec"]["containers"][0].get("env")
        if not env:
            yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"] = []
            env = yaml_obj["spec"]["template"]["spec"]["containers"][0]["env"]

        env.extend(env_values)

        # Append logging env vars if not already present
        for var in log_vars:
            if not any(d.get("name") == var.get("name") for d in env):
                env.append(var)

        # set image
        yaml_obj["spec"]["template"]["spec"]["containers"][0]["image"] = docker_name

        return yaml_obj

    def _populate_worker_spec_yaml(self, yaml_obj: dict) -> dict:
        """
        Populate the custom worker pod yaml object used in this environment with the proper values.

        Args:
            - yaml_obj (dict): A dictionary representing the parsed yaml

        Returns:
            - dict: a dictionary with the yaml values replaced
        """
        # set identifier labels
        self._set_prefect_labels(yaml_obj)

        # Required Cloud environment variables
        env_values = [
            {"name": "PREFECT__CLOUD__GRAPHQL", "value": prefect.config.cloud.graphql},
            {
                "name": "PREFECT__CLOUD__AUTH_TOKEN",
                "value": prefect.config.cloud.auth_token,
            },
            {
                "name": "PREFECT__CONTEXT__FLOW_RUN_ID",
                "value": prefect.context.get("flow_run_id", ""),
            },
            {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
            {
                "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                "value": "prefect.engine.cloud.CloudFlowRunner",
            },
            {
                "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                "value": "prefect.engine.cloud.CloudTaskRunner",
            },
            {
                "name": "PREFECT__ENGINE__EXECUTOR__DEFAULT_CLASS",
                "value": "prefect.engine.executors.DaskExecutor",
            },
        ]

        # Logging env vars
        log_vars = [
            {
                "name": "PREFECT__LOGGING__LOG_TO_CLOUD",
                "value": str(prefect.config.logging.log_to_cloud).lower(),
            },
            {
                "name": "PREFECT__LOGGING__LEVEL",
                "value": str(prefect.config.logging.level),
            },
            {
                "name": "PREFECT__LOGGING__EXTRA_LOGGERS",
                "value": self._extra_loggers(),
            },
        ]

        # set environment variables
        env = yaml_obj["spec"]["containers"][0].get("env")
        if not env:
            yaml_obj["spec"]["containers"][0]["env"] = []
            env = yaml_obj["spec"]["containers"][0]["env"]

        env.extend(env_values)

        # Append logging env vars if not already present
        for var in log_vars:
            if not any(d.get("name") == var.get("name") for d in env):
                env.append(var)

        # set image
        yaml_obj["spec"]["containers"][0]["image"] = prefect.context.get(
            "image", "daskdev/dask:latest"
        )

        return yaml_obj

    def _load_specs_from_file(self) -> tuple:
        """
        Load scheduler and worker spec from provided file paths

        Returns:
            - tuple: scheduler spec dictionary, worker spec dictionary
        """
        scheduler = None
        worker = None

        if self.scheduler_spec_file:
            with open(self.scheduler_spec_file) as scheduler_spec_file:
                scheduler = yaml.safe_load(scheduler_spec_file)

        if self.worker_spec_file:
            with open(self.worker_spec_file) as worker_spec_file:
                worker = yaml.safe_load(worker_spec_file)

        return scheduler, worker

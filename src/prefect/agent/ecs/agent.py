import os
from copy import deepcopy
from typing import Iterable, Dict, Any

import slugify
import yaml

from prefect import config
from prefect.agent import Agent
from prefect.run_configs import ECSRun
from prefect.utilities.agent import get_flow_image, get_flow_run_command
from prefect.utilities.filesystems import read_bytes_from_path
from prefect.utilities.graphql import GraphQLResult


DEFAULT_TASK_DEFINITION_PATH = os.path.join(
    os.path.dirname(__file__), "task_definition.yaml"
)


def merge_run_task_kwargs(opts1: dict, opts2: dict) -> dict:
    """Merge two `run_task_kwargs` dicts, given precedence to `opts2`.

    Values are merged with the following heuristics:

    - Anything outside of `overrides.containerOverrides` is merged directly,
      with precedence given to `opts2`
    - Dicts in the `overrides.containerOverrides` list are matched on their
      `"name"` fields, then merged directly (with precedence given to `opts2`).

    Args:
        - opts1 (dict): A dict of kwargs for `run_task`
        - opts2 (dict): A second dict of kwargs for `run_task`.

    Returns:
        - dict: A merged dict of kwargs
    """

    out = deepcopy(opts1)

    # if opts2 contains keys for capacityProviderStrategy and LaunchType delete launchType
    if "capacityProviderStrategy" in opts2 and "launchType" in out:
        del out["launchType"]

    # if opts2 contains keys for launchType delete capacityProviderStrategy
    if "capacityProviderStrategy" in out and "launchType" in opts2:
        del out["capacityProviderStrategy"]

    # Everything except 'overrides' merge directly
    for k, v in opts2.items():
        if k != "overrides":
            out[k] = v

    # Everything in `overrides` except `containerOverrides` merge directly
    overrides = opts2.get("overrides", {})
    if overrides:
        out_overrides = out.setdefault("overrides", {})
        for k, v in overrides.items():
            if k != "containerOverrides":
                out_overrides[k] = v

    # Entries in `containerOverrides` are paired by name, and then merged
    container_overrides = overrides.get("containerOverrides")
    if container_overrides:
        out_container_overrides = out_overrides.setdefault("containerOverrides", [])
        for entry in container_overrides:
            for out_entry in out_container_overrides:
                if out_entry.get("name") == entry.get("name"):
                    out_entry.update(entry)
                    break
            else:
                out_container_overrides.append(entry)
    return out


class ECSAgent(Agent):
    """
    Agent which deploys flow runs as ECS tasks.

    Args:
        - agent_config_id (str, optional): An optional agent configuration ID
            that can be used to set configuration based on an agent from a
            backend API. If set all configuration values will be pulled from
            the backend agent configuration.
        - name (str, optional): An optional name to give this agent. Can also
            be set through the environment variable `PREFECT__CLOUD__AGENT__NAME`.
            Defaults to "agent".
        - labels (List[str], optional): A list of labels, which are arbitrary
            string identifiers used by Prefect Agents when polling for work.
        - env_vars (dict, optional): A dictionary of environment variables and
            values that will be set on each flow run that this agent submits
            for execution.
        - max_polls (int, optional): Maximum number of times the agent will
            poll Prefect Cloud for flow runs; defaults to infinite.
        - agent_address (str, optional):  Address to serve internal api at.
            Currently this is just health checks for use by an orchestration
            layer. Leave blank for no api server (default).
        - no_cloud_logs (bool, optional): Disable logging to a Prefect backend
            for this agent and all deployed flow runs. Defaults to `False`.
        - task_definition_path (str, optional): Path to a task definition
            template to use when defining new tasks. If not provided, the
            default template will be used.
        - run_task_kwargs_path (str, optional): Path to a `yaml` file
            containing default kwargs to pass to `ECS.client.run_task`. May be
            a local path, or a remote path on e.g. `s3`.
        - aws_access_key_id (str, optional): AWS access key id for connecting
            the boto3 client. If not provided, will be loaded from your
            environment (via either the `AWS_ACCESS_KEY_ID` environment
            variable, or the `~/.aws/config` file). See
            [the boto3 credentials docs][1] for more information.
        - aws_secret_access_key (str, optional): AWS secret access key for
            connecting the boto3 client. If not provided, will be loaded from
            your environment (via either the `AWS_SECRET_ACCESS_KEY`
            environment variable, or the `~/.aws/config` file).
            See [the boto3 credentials docs][1] for more information.
        - aws_session_token (str, optional): AWS session key for connecting the
            boto3 client. If not provided, will be loaded from your environment
            (via either the `AWS_SESSION_TOKEN` environment variable, or the
            `~/.aws/config` file). See [the boto3 credentials docs][1] for more
            information.
        - region_name (str, optional): AWS region name to launch ECS tasks in.
            If not provided, will be loaded from your environment (via either
            the `AWS_DEFAULT_REGION` environment variable, or the
            `~/.aws/config` file). See [the boto3 configuration docs][2] for
            more information.
        - cluster (str, optional): The AWS cluster to use, defaults to
            `"default"` if not provided.
        - launch_type (str, optional): The launch type to use, either
            `"FARGATE"` (default) or `"EC2"`.
        - task_role_arn (str, optional): The default task role ARN to use when
            registering ECS tasks created by this agent.
        - execution_role_arn (str, optional): The default execution role ARN
            to use when registering ECS tasks created by this agent.
        - botocore_config (dict, optional): Additional botocore configuration
            options to be passed to the boto3 client. See [the boto3
            configuration docs][2] for more information.


    [1]: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html

    [2]: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html
    """

    def __init__(  # type: ignore
        self,
        agent_config_id: str = None,
        name: str = None,
        labels: Iterable[str] = None,
        env_vars: dict = None,
        max_polls: int = None,
        agent_address: str = None,
        no_cloud_logs: bool = None,
        task_definition_path: str = None,
        run_task_kwargs_path: str = None,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        aws_session_token: str = None,
        region_name: str = None,
        cluster: str = None,
        launch_type: str = None,
        task_role_arn: str = None,
        execution_role_arn: str = None,
        botocore_config: dict = None,
    ) -> None:
        super().__init__(
            agent_config_id=agent_config_id,
            name=name,
            labels=labels,
            env_vars=env_vars,
            max_polls=max_polls,
            agent_address=agent_address,
            no_cloud_logs=no_cloud_logs,
        )

        from botocore.config import Config
        from prefect.utilities.aws import get_boto_client

        self.cluster = cluster
        self.launch_type = launch_type
        self.task_role_arn = task_role_arn
        self.execution_role_arn = execution_role_arn

        # Load boto configuration. We want to use the standard retry mode by
        # default (which isn't boto's default due to backwards compatibility).
        # The logic below lets the user override our default retry mode either
        # in `botocore_config` or in their aws config file.
        #
        # See https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html
        # for more info.
        boto_config = Config(**botocore_config or {})
        if not boto_config.retries and not os.environ.get("AWS_RETRY_MODE"):
            boto_config.retries = {"mode": "standard"}

        self.boto_kwargs = dict(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region_name,
            config=boto_config,
        )  # type: Dict[str, Any]

        self.ecs_client = get_boto_client("ecs", **self.boto_kwargs)

        # Load default task definition
        if not task_definition_path:
            task_definition_path = DEFAULT_TASK_DEFINITION_PATH
        try:
            self.task_definition = yaml.safe_load(
                read_bytes_from_path(task_definition_path)
            )
        except Exception:
            self.logger.error(
                "Failed to load default task definition from %r",
                task_definition_path,
                exc_info=True,
            )
            raise

        # Load default run_task kwargs
        if run_task_kwargs_path:
            try:
                self.run_task_kwargs = yaml.safe_load(
                    read_bytes_from_path(run_task_kwargs_path)
                )
            except Exception:
                self.logger.error(
                    "Failed to load default `run_task` kwargs from %r",
                    run_task_kwargs_path,
                    exc_info=True,
                )
                raise
        else:
            self.run_task_kwargs = {}

        if not self.run_task_kwargs.get("capacityProviderStrategy"):
            self.launch_type = launch_type.upper() if launch_type else "FARGATE"

            self.logger.debug(
                "No launch type or capacity provider given. Setting launch type to FARGATE.",
            )
        # If running on fargate, auto-configure `networkConfiguration` for the
        # user if they didn't configure it themselves.
        if self.launch_type == "FARGATE" and not self.run_task_kwargs.get(
            "networkConfiguration"
        ):
            self.run_task_kwargs[
                "networkConfiguration"
            ] = self.infer_network_configuration()

    def infer_network_configuration(self) -> dict:
        """Infer default values for `networkConfiguration`.

        This is called when running on `FARGATE` with no `networkConfiguration`
        specified in the default `run_task_kwargs`. This makes it easier to get
        setup, as usually the default is what you want.

        Returns:
            - dict: Inferred `networkConfiguration`
        """
        from prefect.utilities.aws import get_boto_client

        self.logger.debug("Inferring default `networkConfiguration`...")

        ec2 = get_boto_client("ec2", **self.boto_kwargs)
        vpcs = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])[
            "Vpcs"
        ]
        if vpcs:
            vpc_id = vpcs[0]["VpcId"]
            subnets = ec2.describe_subnets(
                Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
            )["Subnets"]
            if subnets:
                config = {
                    "awsvpcConfiguration": {
                        "subnets": [s["SubnetId"] for s in subnets],
                        "assignPublicIp": "ENABLED",
                    }
                }
                self.logger.debug("Using networkConfiguration=%r", config)
                return config

        msg = (
            "Failed to infer default networkConfiguration, please explicitly "
            "configure using `--run-task-kwargs`"
        )
        self.logger.error(msg)
        raise ValueError(msg)

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy a flow run as an ECS task.

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment
        """
        run_config = self._get_run_config(flow_run, ECSRun)
        assert isinstance(run_config, ECSRun)  # mypy

        if run_config.task_definition_arn is None:
            # Register a new task definition
            self.logger.debug(
                "Registering new task definition for flow %s", flow_run.flow.id
            )
            taskdef = self.generate_task_definition(flow_run, run_config)
            resp = self.ecs_client.register_task_definition(**taskdef)
            taskdef_arn = resp["taskDefinition"]["taskDefinitionArn"]
            new_taskdef_arn = True
            self.logger.debug(
                "Registered task definition %s for flow %s",
                taskdef_arn,
                flow_run.flow.id,
            )
        else:
            from prefect.serialization.storage import StorageSchema
            from prefect.storage import Docker

            if isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
                raise ValueError(
                    "Cannot provide `task_definition_arn` when using `Docker` storage"
                )
            taskdef_arn = run_config.task_definition_arn
            resp = self.ecs_client.describe_task_definition(taskDefinition=taskdef_arn)
            taskdef = resp["taskDefinition"]
            new_taskdef_arn = False
            self.logger.debug(
                "Using task definition %s for flow %s", taskdef_arn, flow_run.flow.id
            )

        # Get kwargs to pass to run_task
        kwargs = self.get_run_task_kwargs(flow_run, run_config, taskdef)

        resp = self.ecs_client.run_task(taskDefinition=taskdef_arn, **kwargs)

        # Always deregister the task definition if a new one was registered
        if new_taskdef_arn:
            self.logger.debug("Deregistering task definition %s", taskdef_arn)
            self.ecs_client.deregister_task_definition(taskDefinition=taskdef_arn)

        if resp.get("tasks"):
            task_arn = resp["tasks"][0]["taskArn"]
            self.logger.debug("Started task %r for flow run %r", task_arn, flow_run.id)
            return f"Task {task_arn}"

        raise ValueError(
            "Failed to start task for flow run {0}. Failures: {1}".format(
                flow_run.id, resp.get("failures")
            )
        )

    def generate_task_definition(
        self, flow_run: GraphQLResult, run_config: ECSRun
    ) -> Dict[str, Any]:
        """Generate an ECS task definition from a flow run

        Args:
            - flow_run (GraphQLResult): A flow run object
            - run_config (ECSRun): The flow's run config

        Returns:
            - dict: a dictionary representation of an ECS task definition
        """
        if run_config.task_definition:
            taskdef = deepcopy(run_config.task_definition)
        elif run_config.task_definition_path:
            self.logger.debug(
                "Loading task definition template from %r",
                run_config.task_definition_path,
            )
            template_bytes = read_bytes_from_path(run_config.task_definition_path)
            taskdef = yaml.safe_load(template_bytes)
        else:
            taskdef = deepcopy(self.task_definition)
        slug = slugify.slugify(
            f"{flow_run.flow.name}-{flow_run.id}",
            max_length=255 - len("prefect-"),
            word_boundary=True,
            save_order=True,
        )
        taskdef["family"] = f"prefect-{slug}"

        # Add some metadata tags for easier tracking by users
        taskdef.setdefault("tags", []).extend(
            [
                {"key": "prefect:flow-id", "value": flow_run.flow.id},
                {"key": "prefect:flow-version", "value": str(flow_run.flow.version)},
            ]
        )

        # Get the flow container (creating one if it doesn't already exist)
        containers = taskdef.setdefault("containerDefinitions", [])
        for container in containers:
            if container.get("name") == "flow":
                break
        else:
            container = {"name": "flow"}
            containers.append(container)

        # Set flow image
        container["image"] = image = get_flow_image(
            flow_run, default=container.get("image")
        )

        # Add `PREFECT__CONTEXT__IMAGE` environment variable
        env = {"PREFECT__CONTEXT__IMAGE": image}
        container_env = [{"name": k, "value": v} for k, v in env.items()]
        for entry in container.get("environment", []):
            if entry["name"] not in env:
                container_env.append(entry)
        container["environment"] = container_env

        # Ensure that cpu/memory are strings not integers
        if "cpu" in taskdef:
            taskdef["cpu"] = str(taskdef["cpu"])
        if "memory" in taskdef:
            taskdef["memory"] = str(taskdef["memory"])

        # If we're using Fargate, we need to explicitly set an executionRoleArn on the
        # task definition. If one isn't present, then try to load it from the run_config
        # and then the agent's default.
        if "executionRoleArn" not in taskdef:
            if run_config.execution_role_arn:
                taskdef["executionRoleArn"] = run_config.execution_role_arn
            elif self.execution_role_arn:
                taskdef["executionRoleArn"] = self.execution_role_arn

        # Set requiresCompatibilities if not already set if self.launch_type is set
        if "requiresCompatibilities" not in taskdef and self.launch_type:
            taskdef["requiresCompatibilities"] = [self.launch_type]

        return taskdef

    def get_run_task_kwargs(
        self, flow_run: GraphQLResult, run_config: ECSRun, taskdef: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate kwargs to pass to `ECS.client.run_task` for a flow run

        Args:
            - flow_run (GraphQLResult): A flow run object
            - run_config (ECSRun): The flow's run config
            - taskdef (Dict): The ECS task definition used in ECS.client.run_task

        Returns:
            - dict: kwargs to pass to `ECS.client.run_task`
        """
        # Set agent defaults
        out = deepcopy(self.run_task_kwargs)
        # Use launchType only if capacity provider is not specified
        if not out.get("capacityProviderStrategy"):
            out["launchType"] = self.launch_type

        if self.cluster:
            out["cluster"] = self.cluster

        # Apply run-config kwargs, if any
        if run_config.run_task_kwargs:
            out = merge_run_task_kwargs(out, run_config.run_task_kwargs)

        # Find or create the flow container overrides
        overrides = out.setdefault("overrides", {})
        container_overrides = overrides.setdefault("containerOverrides", [])
        for container in container_overrides:
            if container.get("name") == "flow":
                break
        else:
            container = {"name": "flow"}
            container_overrides.append(container)

        # Task roles and execution roles should be retrieved from the following sources,
        # in order:
        # - An ARN passed explicitly on run_config.
        # - An ARN present on the task definition used for run_task. In this case, we
        #   don't need to provide an override at all.
        # - An ARN passed in to the ECSAgent when instantiated, either programmatically
        #   or via the CLI.
        if run_config.task_role_arn:
            overrides["taskRoleArn"] = run_config.task_role_arn
        elif taskdef.get("taskRoleArn"):
            overrides["taskRoleArn"] = taskdef["taskRoleArn"]
        elif self.task_role_arn:
            overrides["taskRoleArn"] = self.task_role_arn

        if run_config.execution_role_arn:
            overrides["executionRoleArn"] = run_config.execution_role_arn
        elif taskdef.get("executionRoleArn"):
            overrides["executionRoleArn"] = taskdef["executionRoleArn"]
        elif self.execution_role_arn and not taskdef.get("executionRoleArn"):
            overrides["executionRoleArn"] = self.execution_role_arn

        # Set resource requirements, if provided
        # Also ensure that cpu/memory are strings not integers
        if run_config.cpu:
            overrides["cpu"] = str(run_config.cpu)
        elif "cpu" in overrides:
            overrides["cpu"] = str(overrides["cpu"])
        if run_config.memory:
            overrides["memory"] = str(run_config.memory)
        elif "memory" in overrides:
            overrides["memory"] = str(overrides["memory"])

        # Set flow run command
        container["command"] = ["/bin/sh", "-c", get_flow_run_command(flow_run)]

        # Add `PREFECT__LOGGING__LEVEL` environment variable
        env = {"PREFECT__LOGGING__LEVEL": config.logging.level}

        # Populate environment variables from the following sources,
        # with precedence:
        # - Values required for flow execution, hardcoded below
        # - Values set on the ECSRun object
        # - Values set using the `--env` CLI flag on the agent
        env.update(self.env_vars)
        if run_config.env:
            env.update(run_config.env)
        env.update(
            {
                "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
                "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
                "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
                "PREFECT__BACKEND": config.backend,
                "PREFECT__CLOUD__API": config.cloud.api,
                "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,
                "PREFECT__CONTEXT__FLOW_ID": flow_run.flow.id,
                "PREFECT__CLOUD__SEND_FLOW_RUN_LOGS": str(self.log_to_cloud).lower(),
                "PREFECT__CLOUD__API_KEY": self.flow_run_api_key or "",
                "PREFECT__CLOUD__TENANT_ID": (
                    # Providing a tenant id is only necessary when authenticating
                    self.client.tenant_id
                    if self.flow_run_api_key
                    else ""
                ),
                "PREFECT__CLOUD__AGENT__LABELS": str(self.labels),
                # Backwards compatibility variable for containers on Prefect <0.15.0
                "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.log_to_cloud).lower(),
                # Backwards compatibility variable for containers on Prefect <1.0.0
                "PREFECT__CLOUD__AUTH_TOKEN": self.flow_run_api_key or "",
            }
        )
        container_env = [{"name": k, "value": v} for k, v in env.items()]
        for entry in container.get("environment", []):
            if entry["name"] not in env:
                container_env.append(entry)
        container["environment"] = container_env

        return out

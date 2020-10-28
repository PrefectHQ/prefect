import os
import json
from copy import deepcopy
from typing import Iterable, Dict, Any

import slugify
import yaml

from prefect import config
from prefect.agent import Agent
from prefect.run_configs import ECSRun
from prefect.serialization.run_config import RunConfigSchema
from prefect.utilities.agent import get_flow_image, get_flow_run_command
from prefect.utilities.filesystems import read_bytes_from_path
from prefect.utilities.graphql import GraphQLResult


DEFAULT_TASK_DEFINITION_PATH = os.path.join(
    os.path.dirname(__file__), "task_definition.yaml"
)


def parse_run_task_options(opts: list) -> dict:
    """Parse `--run-task-option` inputs to `prefect agent start`.

    Args:
        - opts (list): A list of strings formatted as `"{key}={value}"`,
            where value may be a JSON-compatible value.

    Returns:
        - dict: the parsed parameters
    """
    run_task_kwargs = {}
    for item in opts:
        try:
            key, value = item.split("=")
        except Exception:
            raise ValueError(f"Malformed --run-task-option `{item}`") from None
        try:
            value = json.loads(value)
        except Exception as exc:
            # If it looks like a list/dict then it's poorly formatted
            if any(c in value for c in "{}[]"):
                raise ValueError(
                    f"Error parsing --run-task-option value `{item}`: {str(exc)}"
                ) from None
        run_task_kwargs[key] = value
    return run_task_kwargs


class ECSAgent(Agent):
    """
    Agent which deploys flow runs as ECS tasks.

    **Note**: if AWS authentication kwargs such as `aws_access_key_id` and
    `aws_secret_access_key` are not provided they will be read from the
    environment.

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
            for this agent and all deployed flow runs
        - task_definition_path (str, optional): Path to a task definition
            template to use when defining new tasks. If not provided, the
            default template will be used.
        - aws_access_key_id (str, optional): AWS access key id for connecting
            the boto3 client. If not provided, will be loaded from your
            environment (via either the `AWS_ACCESS_KEY_ID` environment
            variable, or the `~/.aws/config` file). See [the boto3 credentials
            docs][1] for more information.
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
        - run_task_kwargs (dict, optional): Extra keyword arguments to pass to
            `run_task` when starting a task.
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
        no_cloud_logs: bool = False,
        task_definition_path: str = None,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        aws_session_token: str = None,
        region_name: str = None,
        cluster: str = None,
        launch_type: str = None,
        run_task_kwargs: dict = None,
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

        self.cluster = cluster
        self.launch_type = launch_type.upper() if launch_type else "FARGATE"
        self.run_task_kwargs = run_task_kwargs.copy() if run_task_kwargs else {}
        self.task_definition_path = task_definition_path or DEFAULT_TASK_DEFINITION_PATH

        # Load boto configuration. We want to use the standard retry mode by
        # default (which isn't boto's default due to backwards compatibility).
        # The logic below lets the user override our default retry mode either
        # in `botocore_config` or in their aws config file.
        #
        # See https://boto3.amazonaws.com/v1/documentation/api/latest/guide/retries.html
        # for more info.
        boto_config = Config(**botocore_config or {})
        if not boto_config.retries:
            boto_config.retries = {"mode": "standard"}

        self.boto_kwargs = dict(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region_name,
            config=boto_config,
        )  # type: Dict[str, Any]

    def on_startup(self) -> None:
        from prefect.utilities.aws import get_boto_client

        self.ecs_client = get_boto_client("ecs", **self.boto_kwargs)
        self.rgtag_client = get_boto_client(
            "resourcegroupstaggingapi", **self.boto_kwargs
        )

        if self.launch_type == "FARGATE" and not self.run_task_kwargs.get(
            "networkConfiguration"
        ):
            self.run_task_kwargs[
                "networkConfiguration"
            ] = self.get_default_network_configuration()

    def get_default_network_configuration(self) -> dict:
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
            "configure using `--run-param networkConfiguration=...`"
        )
        self.logger.error(msg)
        raise ValueError(msg)

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy flow runs on to a k8s cluster as jobs

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment
        """
        self.logger.info("Deploying flow run %r", flow_run.id)

        # Load and validate the flow's run_config
        if getattr(flow_run.flow, "run_config", None) is not None:
            run_config = RunConfigSchema().load(flow_run.flow.run_config)
            if not isinstance(run_config, ECSRun):
                self.logger.error(
                    "Flow run %s has a `run_config` of type `%s`, only `ECSRun` is supported",
                    flow_run.id,
                    type(run_config).__name__,
                )
                raise TypeError(
                    "Unsupported RunConfig type: %s" % type(run_config).__name__
                )
        else:
            self.logger.error(
                "Flow run %s has a null `run_config`, only `ECSRun` is supported",
                flow_run.id,
            )
            raise TypeError("Flow is missing a `run_config`")

        # Check if a task definition already exists
        taskdef_arn = self.lookup_task_definition_arn(flow_run)
        if not taskdef_arn:
            # Register a new task definition
            self.logger.debug(
                "Registering new task definition for flow %s", flow_run.flow.id
            )
            taskdef = self.generate_task_definition(flow_run, run_config)
            resp = self.ecs_client.register_task_definition(**taskdef)
            taskdef_arn = resp["taskDefinition"]["taskDefinitionArn"]
            self.logger.debug(
                "Registered task definition %s for flow %s",
                taskdef_arn,
                flow_run.flow.id,
            )
        else:
            self.logger.debug(
                "Using task definition %s for flow %s", taskdef_arn, flow_run.flow.id
            )

        # Get kwargs to pass to run_task
        kwargs = self.get_run_task_kwargs(flow_run, run_config)

        resp = self.ecs_client.run_task(taskDefinition=taskdef_arn, **kwargs)
        if resp.get("tasks"):
            task_arn = resp["tasks"][0]["taskArn"]
            self.logger.debug("Started task %r for flow run %r", task_arn, flow_run.id)
            return f"Task {task_arn}"

        raise ValueError(
            "Failed to start task for flow run {0}. Failures: {1}".format(
                flow_run.id, resp.get("failures")
            )
        )

    def get_task_definition_tags(self, flow_run: GraphQLResult) -> dict:
        return {
            "prefect:flow-id": flow_run.flow.id,
            "prefect:flow-version": str(flow_run.flow.version),
        }

    def lookup_task_definition_arn(self, flow_run: GraphQLResult) -> str:
        tags = self.get_task_definition_tags(flow_run)

        from botocore.exceptions import ClientError

        try:
            res = self.rgtag_client.get_resources(
                TagFilters=[{"Key": k, "Values": [v]} for k, v in tags.items()],
                ResourceTypeFilters=["ecs:task-definition"],
            )
            if res["ResourceTagMappingList"]:
                return res["ResourceTagMappingList"][0]["ResourceARN"]
            return ""
        except ClientError:
            return ""

    def generate_task_definition(
        self, flow_run: GraphQLResult, run_config: ECSRun
    ) -> Dict[str, Any]:
        if run_config.task_definition:
            taskdef = deepcopy(run_config.task_definition)
        else:
            task_definition_path = (
                run_config.task_definition_path or self.task_definition_path
            )
            self.logger.debug(
                "Loading task definition template from %r", task_definition_path
            )
            template_bytes = read_bytes_from_path(task_definition_path)
            taskdef = yaml.safe_load(template_bytes)

        slug = slugify.slugify(
            flow_run.flow.name,
            max_length=255 - len("prefect-"),
            word_boundary=True,
            save_order=True,
        )
        family = f"prefect-{slug}"

        tags = self.get_task_definition_tags(flow_run)

        taskdef["family"] = family

        taskdef_tags = [{"key": k, "value": v} for k, v in tags.items()]
        for entry in taskdef.get("tags", []):
            if entry["key"] not in tags:
                taskdef_tags.append(entry)
        taskdef["tags"] = taskdef_tags

        # Get the flow container (creating one if it doesn't already exist)
        containers = taskdef.setdefault("containerDefinitions", [])
        for container in containers:
            if container.get("name") == "flow":
                break
        else:
            container = {"name": "flow"}
            containers.append(container)

        # Set flow image
        container["image"] = get_flow_image(flow_run)

        # Set flow run command
        container["command"] = ["/bin/sh", "-c", get_flow_run_command(flow_run)]

        # Populate static environment variables from the following sources,
        # with precedence:
        # - Static environment variables, hardcoded below
        # - Values in the task definition template
        env = {
            "PREFECT__CLOUD__USE_LOCAL_SECRETS": "false",
            "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudFlowRunner",
            "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS": "prefect.engine.cloud.CloudTaskRunner",
        }
        container_env = [{"name": k, "value": v} for k, v in env.items()]
        for entry in container.get("environment", []):
            if entry["name"] not in env:
                container_env.append(entry)
        container["environment"] = container_env

        # Set resource requirements, if provided
        # Also ensure that cpu/memory are strings not integers
        if run_config.cpu:
            taskdef["cpu"] = str(run_config.cpu)
        elif "cpu" in taskdef:
            taskdef["cpu"] = str(taskdef["cpu"])
        if run_config.memory:
            taskdef["memory"] = str(run_config.memory)
        elif "memory" in taskdef:
            taskdef["memory"] = str(taskdef["memory"])

        return taskdef

    def get_run_task_kwargs(
        self, flow_run: GraphQLResult, run_config: ECSRun
    ) -> Dict[str, Any]:
        out = deepcopy(self.run_task_kwargs)
        if self.launch_type:
            out["launchType"] = self.launch_type
        if self.cluster:
            out["cluster"] = self.cluster

        overrides = out.setdefault("overrides", {})
        container_overrides = overrides.setdefault("containerOverrides", [])
        for container in container_overrides:
            if container.get("name") == "flow":
                break
        else:
            container = {"name": "flow"}
            container_overrides.append(container)

        # Populate environment variables from the following sources,
        # with precedence:
        # - Dynamic values required for flow execution, hardcoded below
        # - Values set on the ECSRun object
        # - Values set using the `--env` CLI flag on the agent
        env = self.env_vars.copy()
        if run_config.env:
            env.update(run_config.env)
        env.update(
            {
                "PREFECT__CLOUD__API": config.cloud.api,
                "PREFECT__CONTEXT__FLOW_RUN_ID": flow_run.id,
                "PREFECT__CONTEXT__FLOW_ID": flow_run.flow.id,
                "PREFECT__LOGGING__LOG_TO_CLOUD": str(self.log_to_cloud).lower(),
                "PREFECT__CLOUD__AUTH_TOKEN": config.cloud.agent.auth_token,
                "PREFECT__CLOUD__AGENT__LABELS": str(self.labels),
            }
        )
        container_env = [{"name": k, "value": v} for k, v in env.items()]
        for entry in container.get("environment", []):
            if entry["name"] not in env:
                container_env.append(entry)
        container["environment"] = container_env

        return out

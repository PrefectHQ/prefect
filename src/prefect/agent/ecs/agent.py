import json
from typing import Iterable

from prefect.agent import Agent


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

    **Note**: if AWS authentication kwargs such as `aws_access_key_id` and `aws_secret_key_id`
    are not provided they will be read from the environment.

    Args:
        - agent_config_id (str, optional): An optional agent configuration ID that can be used to set
            configuration based on an agent from a backend API. If set all configuration values will be
            pulled from backend agent configuration.
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
        - env_vars (dict, optional): a dictionary of environment variables and values that will
            be set on each flow run that this agent submits for execution
        - max_polls (int, optional): maximum number of times the agent will poll Prefect Cloud
            for flow runs; defaults to infinite
        - agent_address (str, optional):  Address to serve internal api at. Currently this is
            just health checks for use by an orchestration layer. Leave blank for no api server
            (default).
        - no_cloud_logs (bool, optional): Disable logging to a Prefect backend for this agent
            and all deployed flow runs
        - default_task_definition (str, optional): The name of a default task definition to
            use when one isn't specified on a flow. Can provide either the `family:revision`,
            just the `family` (in which case the latest active revision is used), or the full
            task definition ARN. If provided, the definition must already be registered. If
            not provided, a default task definition will be registered and used.
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
            Defaults to the value set in the environment variable `AWS_DEFAULT_REGION` or `None`
        - cluster (str, optional): The AWS cluster to use, defaults to `"default"` if not provided.
        - launch_type (str, optional): The launch type to use, either `"FARGATE"` (default) or `"EC2"`.
        - run_task_kwargs (dict, optional): Keyword arguments to pass to `run_task` when starting a task.
        - botocore_config (dict, optional): botocore configuration options to be passed to the
            boto3 client.
            https://botocore.amazonaws.com/v1/documentation/api/latest/reference/config.html
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
        default_task_definition: str = None,
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
        self.default_task_definition = default_task_definition
        self.boto_kwargs = dict(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region_name,
            config=Config(**(botocore_config or {})),
        )
        self.ecs_client = None

    def on_startup(self):
        from prefect.utilities.aws import get_boto_client

        self.ecs_client = get_boto_client("ecs", **self.boto_kwargs)

        if not self.default_task_definition:
            self.register_default_task_definition()

        self.logger.info(
            "Using default task definition: %r", self.default_task_definition
        )

        if self.launch_type == "FARGATE" and not self.run_task_kwargs.get(
            "networkConfiguration"
        ):
            self.run_task_kwargs[
                "networkConfiguration"
            ] = self.get_default_network_configuration()

    def register_default_task_definition(self):
        try:
            self.ecs_client.describe_task_definition(taskDefinition="prefect-default")
            exists = True
        except Exception:
            exists = False

        if not exists:
            self.logger.info("Registering default task definition `prefect-default`")
            self.ecs_client.register_task_definition(
                family="prefect-default",
                networkMode="awsvpc",
                cpu="1024",
                memory="2048",
                containerDefinitions=[
                    {"name": "flow", "image": "prefecthq/prefect:latest"}
                ],
            )

        self.default_task_definition = "prefect-default"

    def get_default_network_configuration(self):
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
                    "subnets": [s["SubnetId"] for s in subnets],
                    "assignPublicIp": "ENABLED",
                }
                self.logger.debug("Using networkConfiguration=%r", config)
                return config

        msg = (
            "Failed to infer default networkConfiguration, please explicitly "
            "configure using `--run-param networkConfiguration=...`"
        )
        self.logger.error(msg)
        raise ValueError(msg)

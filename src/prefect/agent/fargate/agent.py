import os

from prefect import config
from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class FargateAgent(Agent):
    """
    Agent which deploys flow runs as tasks using Fargate. This agent can run anywhere as
    long as the proper access configuration variables are set.

    Args:
        - aws_access_key_id (str, optional): AWS access key id for connecting the boto3
            client. Defaults to the value set in the environment variable
            `AWS_ACCESS_KEY_ID`.
        - aws_secret_access_key (str, optional): AWS secret access key for connecting
            the boto3 client. Defaults to the value set in the environment variable
            `AWS_SECRET_ACCESS_KEY`.
        - region_name (str, optional): AWS region name for connecting the boto3 client.
            Defaults to the value set in the environment variable `REGION_NAME`.
        - cluster (str, optional): The Fargate cluster to deploy tasks. Defaults to the
            value set in the environment variable `CLUSTER`.
        - subnets (list, optional): A list of AWS VPC subnets to use for the tasks that
            are deployed on Fargate. Defaults to the subnets found which have
            `MapPublicIpOnLaunch` disabled.
        - security_groups (list, optional): A list of security groups to associate with
            the deployed tasks. Defaults to the default security group of the VPC.
        - repository_credentials (str, optional): An Amazon Resource Name (ARN) of the
            secret containing the private repository credentials. Defaults to the value
            set in the environment variable `REPOSITORY_CREDENTIALS`.
        - assign_public_ip (str, optional): Whether the task's elastic network interface
            receives a public IP address. Defaults to the value set in the environment
            variable `ASSIGN_PUBLIC_IP` or `ENABLED` otherwise.
        - task_cpu (str, optional): The number of cpu units reserved for the container.
            Defaults to the value set in the environment variable `TASK_CPU` or `256`
            otherwise.
        - task_memory (str, optional): The hard limit (in MiB) of memory to present to
            the container. Defaults to the value set in the environment variable
            `TASK_MEMORY` or `512` otherwise.
    """

    def __init__(
        self,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        region_name: str = None,
        cluster: str = None,
        subnets: list = None,
        security_groups: list = None,
        repository_credentials: str = None,
        assign_public_ip: str = None,
        task_cpu: str = None,
        task_memory: str = None,
    ) -> None:
        super().__init__()

        from boto3 import client as boto3_client

        # Config used for boto3 client initialization
        aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = aws_secret_access_key or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        region_name = region_name or os.getenv("REGION_NAME")

        # Agent task config
        self.cluster = cluster or os.getenv("CLUSTER", "default")
        self.logger.debug("Cluster {}".format(self.cluster))

        self.subnets = subnets or []
        self.logger.debug("Subnets {}".format(self.subnets))

        self.security_groups = security_groups or []
        self.logger.debug("Security groups {}".format(self.security_groups))

        self.repository_credentials = repository_credentials or os.getenv(
            "REPOSITORY_CREDENTIALS"
        )
        self.logger.debug(
            "Repository credentials {}".format(self.repository_credentials)
        )

        self.assign_public_ip = assign_public_ip or os.getenv(
            "ASSIGN_PUBLIC_IP", "ENABLED"
        )
        self.logger.debug("Assign public IP {}".format(self.assign_public_ip))

        self.task_cpu = task_cpu or os.getenv("TASK_CPU", "256")
        self.logger.debug("Task CPU {}".format(self.task_cpu))

        self.task_memory = task_memory or os.getenv("TASK_MEMORY", "512")
        self.logger.debug("Task Memory {}".format(self.task_memory))

        # Client initialization
        self.boto3_client = boto3_client(
            "ecs",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
        )

        # Look for default subnets with `MapPublicIpOnLaunch` disabled
        if not subnets:
            self.logger.debug("No subnets provided, finding defaults")
            ec2 = boto3_client(
                "ec2",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=region_name,
            )
            for subnet in ec2.describe_subnets()["Subnets"]:
                if not subnet.get("MapPublicIpOnLaunch"):
                    self.subnets.append(subnet.get("SubnetId"))
                    self.logger.debug("Subnet {} found".format(subnet.get("SubnetId")))

    def deploy_flows(self, flow_runs: list) -> None:
        """
        Deploy flow runs to Fargate

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        for flow_run in flow_runs:
            self.logger.debug(
                "Deploying flow run {}".format(flow_run.id)  # type: ignore
            )

            # Require Docker storage
            if not isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
                self.logger.error(
                    "Storage for flow run {} is not of type Docker.".format(flow_run.id)
                )
                continue

            # check if task definition exists
            self.logger.debug("Checking for task definition")
            if not self._verify_task_definition_exists(flow_run):
                self.logger.debug("No task definition found")
                self._create_task_definition(flow_run)

            # run task
            self._run_task(flow_run)

    def _verify_task_definition_exists(self, flow_run: GraphQLResult) -> bool:
        """
        Check if a task definition already exists for the flow

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects

        Returns:
            - bool: whether or not a preexisting task definition is found for this flow
        """
        from botocore.exceptions import ClientError

        try:
            self.boto3_client.describe_task_definition(
                taskDefinition="prefect-task-{}".format(
                    flow_run.flow.id[:8]  # type: ignore
                )
            )
            self.logger.debug(
                "Task definition {} found".format(flow_run.flow.id[:8])  # type: ignore
            )
        except ClientError:
            return False

        return True

    def _create_task_definition(self, flow_run: GraphQLResult) -> None:
        """
        Create a task definition for the flow that each flow run will use. This function
        is only called when a flow is run for the first time.

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        self.logger.debug(
            "Using image {} for task definition".format(
                StorageSchema().load(flow_run.flow.storage).name  # type: ignore
            )
        )
        container_definitions = [
            {
                "name": "flow",
                "image": StorageSchema()
                .load(flow_run.flow.storage)  # type: ignore
                .name,
                "command": ["/bin/sh", "-c", "prefect execute cloud-flow"],
                "environment": [
                    {
                        "name": "PREFECT__CLOUD__API",
                        "value": config.cloud.api or "https://api.prefect.io",
                    },
                    {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                    {"name": "PREFECT__LOGGING__LOG_TO_CLOUD", "value": "true"},
                    {"name": "PREFECT__LOGGING__LEVEL", "value": "DEBUG"},
                    {
                        "name": "PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS",
                        "value": "prefect.engine.cloud.CloudFlowRunner",
                    },
                    {
                        "name": "PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS",
                        "value": "prefect.engine.cloud.CloudTaskRunner",
                    },
                ],
                "essential": True,
            }
        ]

        # Assign repository credentials if they are specified
        if self.repository_credentials:
            self.logger.debug("Assigning repository credentials")
            container_definitions[0]["repositoryCredentials"] = {
                "credentialsParameter": self.repository_credentials
            }

        # Register task definition
        self.logger.debug(
            "Registering task definition {}".format(
                flow_run.flow.id[:8]  # type: ignore
            )
        )
        self.boto3_client.register_task_definition(
            family="prefect-task-{}".format(flow_run.flow.id[:8]),  # type: ignore
            containerDefinitions=container_definitions,
            requiresCompatibilities=["FARGATE"],
            networkMode="awsvpc",
            cpu=self.task_cpu,
            memory=self.task_memory,
        )

    def _run_task(self, flow_run: GraphQLResult) -> None:
        """
        Run a task using the flow run.

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
        """
        container_overrides = [
            {
                "name": "flow",
                "environment": [
                    {
                        "name": "PREFECT__CLOUD__AUTH_TOKEN",
                        "value": config.cloud.agent.auth_token,
                    },
                    {
                        "name": "PREFECT__CONTEXT__FLOW_RUN_ID",
                        "value": flow_run.id,  # type: ignore
                    },
                ],
            }
        ]

        network_configuration = {
            "awsvpcConfiguration": {
                "subnets": self.subnets,
                "assignPublicIp": self.assign_public_ip,
            }
        }

        # Asssign task security groups if they are specified
        if self.security_groups:
            self.logger.debug("Assigning security groups")
            network_configuration["awsvpcConfiguration"][
                "securityGroups"
            ] = self.security_groups

        # Run task
        self.logger.debug(
            "Running task using task definition {}".format(
                flow_run.flow.id[:8]  # type: ignore
            )
        )
        self.boto3_client.run_task(
            cluster=self.cluster,
            taskDefinition="prefect-task-{}".format(
                flow_run.flow.id[:8]  # type: ignore
            ),
            overrides={"containerOverrides": container_overrides},
            launchType="FARGATE",
            networkConfiguration=network_configuration,
        )


if __name__ == "__main__":
    FargateAgent().start()

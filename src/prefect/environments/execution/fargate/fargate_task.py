import os
from typing import Any, List

import cloudpickle

import prefect
from prefect import config
from prefect.environments.execution import Environment
from prefect.environments.storage import Docker


class FargateTaskEnvironment(Environment):
    """
    FargateTaskEnvironment is an environment which deploys your flow (stored in a Docker image)
    as a Fargate task. This environment requires AWS credentials and extra boto3 kwargs which
    are used in the creation and running of the Fargate task.

    When providing a custom container definition spec the first container in the spec must be the
    container that the flow runner will be executed on.

    These environment variables are required for cloud but do not need to be included because
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

    `$ /bin/sh -c 'python -c "from prefect.environments import FargateTaskEnvironment; FargateTaskEnvironment().run_flow()"'`

    All `kwargs` are accepted that one would normally pass to boto3 for `register_task_definition`
    and `run_task`. For information on the kwargs supported visit the following links:

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task

    The secrets and kwargs that are provided at initialization time of this environment
    are not serialized and will only ever exist on this object.

    Args:
        - aws_access_key_id (str, optional): AWS access key id for connecting the boto3
            client. Defaults to the value set in the environment variable
            `AWS_ACCESS_KEY_ID`.
        - aws_secret_access_key (str, optional): AWS secret access key for connecting
            the boto3 client. Defaults to the value set in the environment variable
            `AWS_SECRET_ACCESS_KEY`.
        - region_name (str, optional): AWS region name for connecting the boto3 client.
            Defaults to the value set in the environment variable `REGION_NAME`.
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
        - **kwargs (dict, optional): additional keyword arguments to pass to boto3 for
            `register_task_definition` and `run_task`
    """

    def __init__(  # type: ignore
        self,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        region_name: str = None,
        labels: List[str] = None,
        **kwargs
    ) -> None:
        # Not serialized, only stored on the object
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        self.region_name = region_name or os.getenv("REGION_NAME")

        # Parse accepted kwargs for definition and run
        self.task_definition_kwargs, self.task_run_kwargs = self._parse_kwargs(kwargs)

        super().__init__(labels=labels)

    def _parse_kwargs(self, user_kwargs: dict) -> tuple:
        """
        Parse the kwargs passed in and separate them out for `register_task_definition`
        and `run_task`. This is required because boto3 does not allow extra kwargs
        and if they are provided it will raise botocore.exceptions.ParamValidationError.

        Args:
            - user_kwargs (dict): The kwargs passed to the initialization of the environment

        Returns:
            tuple: a tuple of two dictionaries (task_definition_kwargs, task_run_kwargs)
        """
        definition_kwarg_list = [
            "family",
            "taskRoleArn",
            "executionRoleArn",
            "networkMode",
            "containerDefinitions",
            "volumes",
            "placementConstraints",
            "requiresCompatibilities",
            "cpu",
            "memory",
            "tags",
            "pidMode",
            "ipcMode",
            "proxyConfiguration",
            "inferenceAccelerators",
        ]

        run_kwarg_list = [
            "cluster",
            "taskDefinition",
            "count",
            "startedBy",
            "group",
            "placementConstraints",
            "placementStrategy",
            "platformVersion",
            "networkConfiguration",
            "tags",
            "enableECSManagedTags",
            "propagateTags",
        ]

        task_definition_kwargs = {}
        for key, item in user_kwargs.items():
            if key in definition_kwarg_list:
                task_definition_kwargs.update({key: item})

        task_run_kwargs = {}
        for key, item in user_kwargs.items():
            if key in run_kwarg_list:
                task_run_kwargs.update({key: item})

        return task_definition_kwargs, task_run_kwargs

    def setup(self, storage: "Docker") -> None:  # type: ignore
        """
        Register the task definition if it does not already exist.

        Args:
            - storage (Storage): the Storage object that contains the flow
        """
        from boto3 import client as boto3_client
        from botocore.exceptions import ClientError

        boto3_c = boto3_client(
            "ecs",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
        )

        flow_run_id = prefect.context.get("flow_run_id", "unknown")

        definition_exists = True
        try:
            boto3_c.describe_task_definition(
                taskDefinition="prefect-task-{}-custom".format(flow_run_id[:8])
            )
        except ClientError:
            definition_exists = False

        if not definition_exists:
            env_values = [
                {"name": "PREFECT__CLOUD__GRAPHQL", "value": config.cloud.graphql},
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

            # Populate all env vars
            for definition in self.task_definition_kwargs.get("containerDefinitions"):
                definition["environment"].extend(env_values)

            # Populate storage
            self.task_definition_kwargs.get("containerDefinitions")[0][
                "image"
            ] = storage.name

            # Replace command
            self.task_definition_kwargs.get("containerDefinitions")[0]["command"] = [
                "/bin/sh",
                "-c",
                "python -c 'from prefect.environments import FargateTaskEnvironment; FargateTaskEnvironment().run_flow()'",
            ]

            boto3_c.register_task_definition(
                family="prefect-task-{}-custom".format(flow_run_id[:8]),
                **self.task_definition_kwargs
            )

    def execute(  # type: ignore
        self, storage: "Docker", flow_location: str, **kwargs: Any
    ) -> None:
        """
        Run the Fargate task that was defined for this flow.

        Args:
            - storage (Storage): the Storage object that contains the flow
            - flow_location (str): the location of the Flow to execute
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """
        from boto3 import client as boto3_client

        flow_run_id = prefect.context.get("flow_run_id", "unknown")
        container_overrides = [
            {
                "name": "flow",
                "environment": [
                    {
                        "name": "PREFECT__CLOUD__AUTH_TOKEN",
                        "value": config.cloud.agent.auth_token,
                    },
                    {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": flow_run_id},
                    {"name": "PREFECT__CONTEXT__IMAGE", "value": storage.name},
                    {
                        "name": "PREFECT__CONTEXT__FLOW_FILE_PATH",
                        "value": flow_location,
                    },
                ],
            }
        ]

        boto3_c = boto3_client(
            "ecs",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
        )

        boto3_c.run_task(
            taskDefinition="prefect-task-{}-custom".format(flow_run_id[:8]),
            overrides={"containerOverrides": container_overrides},
            launchType="FARGATE",
            **self.task_run_kwargs
        )

    def run_flow(self) -> None:
        """
        Run the flow from specified flow_file_path location using the default executor
        """
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
                executor_cls = get_default_executor_class()
                runner_cls(flow=flow).run(executor=executor_cls)
        except Exception as exc:
            self.logger.exception(
                "Unexpected error raised during flow run: {}".format(exc)
            )
            raise exc

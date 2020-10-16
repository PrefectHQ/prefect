import operator
import os
import warnings
from typing import TYPE_CHECKING, Callable, List

import prefect
from prefect import config
from prefect.environments.execution.base import Environment, _RunMixin
from prefect.utilities.storage import get_flow_image

if TYPE_CHECKING:
    from prefect.core.flow import Flow  # pylint: disable=W0611

_DEFINITION_KWARG_LIST = [
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


class FargateTaskEnvironment(Environment, _RunMixin):
    """
    FargateTaskEnvironment is an environment which deploys your flow as a Fargate task.
    This environment requires AWS credentials and extra boto3 kwargs which
    are used in the creation and running of the Fargate task.

    When providing a custom container definition spec the first container in the spec must be the
    container that the flow runner will be executed on.

    The following environment variables, required for cloud, do not need to be
    included––they are automatically added and populated during execution:

    - `PREFECT__CLOUD__GRAPHQL`
    - `PREFECT__CLOUD__AUTH_TOKEN`
    - `PREFECT__CONTEXT__FLOW_RUN_ID`
    - `PREFECT__CONTEXT__IMAGE`
    - `PREFECT__CLOUD__USE_LOCAL_SECRETS`
    - `PREFECT__ENGINE__FLOW_RUNNER__DEFAULT_CLASS`
    - `PREFECT__ENGINE__TASK_RUNNER__DEFAULT_CLASS`
    - `PREFECT__LOGGING__LOG_TO_CLOUD`
    - `PREFECT__LOGGING__EXTRA_LOGGERS`

    Additionally, the following command will be applied to the first container:

    `$ /bin/sh -c "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'"`

    All `kwargs` are accepted that one would normally pass to boto3 for `register_task_definition`
    and `run_task`. For information on the kwargs supported visit the following links:

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task

    Note: You must provide `family` and `taskDefinition` with the same string so they match on
    run of the task.

    The secrets and kwargs that are provided at initialization time of this environment
    are not serialized and will only ever exist on this object.

    Args:
        - launch_type (str, optional): either FARGATE or EC2, defaults to FARGATE
        - aws_access_key_id (str, optional): AWS access key id for connecting the boto3
            client. Defaults to the value set in the environment variable
            `AWS_ACCESS_KEY_ID` or `None`
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
            Defaults to the value set in the environment variable `REGION_NAME` or `None`
        - executor (Executor, optional): the executor to run the flow with. If not provided, the
            default executor will be used.
        - executor_kwargs (dict, optional): DEPRECATED
        - labels (List[str], optional): a list of labels, which are arbitrary string
            identifiers used by Prefect Agents when polling for work
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
        launch_type: str = "FARGATE",
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        aws_session_token: str = None,
        region_name: str = None,
        executor: "prefect.engine.executors.Executor" = None,
        executor_kwargs: dict = None,
        labels: List[str] = None,
        on_start: Callable = None,
        on_exit: Callable = None,
        metadata: dict = None,
        **kwargs,
    ) -> None:
        self.launch_type = launch_type
        # Not serialized, only stored on the object
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        self.aws_session_token = aws_session_token or os.getenv("AWS_SESSION_TOKEN")
        self.region_name = region_name or os.getenv("REGION_NAME")

        # Parse accepted kwargs for definition and run
        self.task_definition_kwargs, self.task_run_kwargs = self._parse_kwargs(kwargs)

        if executor_kwargs is not None:
            warnings.warn(
                "`executor_kwargs` is deprecated, use `executor` instead", stacklevel=2
            )
        if executor is None:
            executor = prefect.engine.get_default_executor_class()(
                **(executor_kwargs or {})
            )
        elif not isinstance(executor, prefect.engine.executors.Executor):
            raise TypeError(
                f"`executor` must be an `Executor` or `None`, got `{executor}`"
            )
        self.executor = executor

        super().__init__(
            labels=labels, on_start=on_start, on_exit=on_exit, metadata=metadata
        )

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
            if key in _DEFINITION_KWARG_LIST:
                task_definition_kwargs.update({key: item})

        task_run_kwargs = {}
        for key, item in user_kwargs.items():
            if key in run_kwarg_list:
                task_run_kwargs.update({key: item})

        return task_definition_kwargs, task_run_kwargs

    @property
    def dependencies(self) -> list:
        return ["boto3", "botocore"]

    def _render_task_definition_kwargs(self, flow: "Flow") -> dict:
        task_definition_kwargs = self.task_definition_kwargs.copy()

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
            {
                "name": "PREFECT__LOGGING__EXTRA_LOGGERS",
                "value": str(config.logging.extra_loggers),
            },
        ]

        # create containerDefinitions if they do not exist
        if not task_definition_kwargs.get("containerDefinitions"):
            task_definition_kwargs["containerDefinitions"] = []
            task_definition_kwargs["containerDefinitions"].append({})

        # set environment variables for all containers
        for definition in task_definition_kwargs["containerDefinitions"]:
            if not definition.get("environment"):
                definition["environment"] = []
            definition["environment"].extend(env_values)

        # set name on first container
        if not task_definition_kwargs["containerDefinitions"][0].get("name"):
            task_definition_kwargs["containerDefinitions"][0]["name"] = ""

        task_definition_kwargs.get("containerDefinitions")[0]["name"] = "flow-container"

        # set image on first container
        if not task_definition_kwargs["containerDefinitions"][0].get("image"):
            task_definition_kwargs["containerDefinitions"][0]["image"] = ""

        task_definition_kwargs.get("containerDefinitions")[0]["image"] = get_flow_image(
            flow
        )

        # set command on first container
        if not task_definition_kwargs["containerDefinitions"][0].get("command"):
            task_definition_kwargs["containerDefinitions"][0]["command"] = []

        task_definition_kwargs.get("containerDefinitions")[0]["command"] = [
            "/bin/sh",
            "-c",
            "python -c 'import prefect; prefect.environments.execution.load_and_run_flow()'",
        ]

        return task_definition_kwargs

    def _validate_task_definition(
        self, existing_task_definition: dict, task_definition_kwargs: dict
    ) -> None:
        def format_container_definition(definition: dict) -> dict:
            """
            Reformat all object arrays in the containerDefinitions so
            the keys are comparable for validation. Most of these won't apply
            to the first container (overriden by Prefect) but it could apply to
            other containers in the definition, so they are included here.

            The keys that are overriden here are listed in:
            https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definition_parameters.html#container_definitions

            Essentially only the `object array` types need to be overridden since
            they may be returned from AWS's API out of order.
            """
            return {
                **definition,
                "environment": {
                    item["name"]: item["value"]
                    for item in definition.get("environment", [])
                },
                "secrets": {
                    item["name"]: item["valueFrom"]
                    for item in definition.get("secrets", [])
                },
                "mountPoints": {
                    item["sourceVolume"]: item
                    for item in definition.get("mountPoints", [])
                },
                "extraHosts": {
                    item["hostname"]: item["ipAddress"]
                    for item in definition.get("extraHosts", [])
                },
                "volumesFrom": {
                    item["sourceContainer"]: item
                    for item in definition.get("volumesFrom", [])
                },
                "ulimits": {
                    item["name"]: item for item in definition.get("ulimits", [])
                },
                "portMappings": {
                    item["containerPort"]: item
                    for item in definition.get("portMappings", [])
                },
                "logConfiguration": {
                    **definition.get("logConfiguration", {}),
                    "secretOptions": {
                        item["name"]: item["valueFrom"]
                        for item in definition.get("logConfiguration", {}).get(
                            "secretOptions", []
                        )
                    },
                },
            }

        givenContainerDefinitions = sorted(
            [
                format_container_definition(container_definition)
                for container_definition in task_definition_kwargs[
                    "containerDefinitions"
                ]
            ],
            key=operator.itemgetter("name"),
        )
        expectedContainerDefinitions = sorted(
            [
                format_container_definition(container_definition)
                for container_definition in existing_task_definition[
                    "containerDefinitions"
                ]
            ],
            key=operator.itemgetter("name"),
        )

        containerDifferences = [
            "containerDefinition.{idx}.{key} -> Given: {given}, Expected: {expected}".format(
                idx=container_definition.get("name", idx),
                key=key,
                given=value,
                expected=existing_container_definition.get(key),
            )
            for idx, (
                container_definition,
                existing_container_definition,
            ) in enumerate(zip(givenContainerDefinitions, expectedContainerDefinitions))
            for key, value in container_definition.items()
            if value != existing_container_definition.get(key)
        ]

        arnDifferences = [
            "{key} -> Given: {given}, Expected: {expected}".format(
                key=key,
                given=task_definition_kwargs[key],
                expected=existing_task_definition.get(key),
            )
            for key in _DEFINITION_KWARG_LIST
            if key.endswith("Arn")
            and key in task_definition_kwargs
            and (
                existing_task_definition.get(key) != task_definition_kwargs[key]
                and existing_task_definition.get(key, "").split("/")[-1]
                != task_definition_kwargs[key]
            )
        ]

        otherDifferences = [
            "{key} -> Given: {given}, Expected: {expected}".format(
                key=key,
                given=task_definition_kwargs[key],
                expected=existing_task_definition.get(key),
            )
            for key in _DEFINITION_KWARG_LIST
            if key != "containerDefinitions"
            and not key.endswith("Arn")
            and key in task_definition_kwargs
            and existing_task_definition.get(key) != task_definition_kwargs[key]
        ]

        differences = containerDifferences + arnDifferences + otherDifferences

        if differences:
            raise ValueError(
                (
                    "The given taskDefinition does not match the existing taskDefinition {}.\n"
                    "Detail: \n\t{}\n\n"
                    "If the given configuration is desired, deregister the existing\n"
                    "taskDefinition and re-run the flow. Alternatively, you can\n"
                    "change the family/taskDefinition name in the FargateTaskEnvironment\n"
                    "for this flow."
                ).format(
                    self.task_definition_kwargs.get("family"), "\n\t".join(differences)
                )
            )

    def setup(self, flow: "Flow") -> None:  # type: ignore
        """
        Register the task definition if it does not already exist.

        Args:
            - flow (Flow): the Flow object
        """
        from boto3 import client as boto3_client
        from botocore.exceptions import ClientError

        boto3_c = boto3_client(
            "ecs",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.region_name,
        )

        task_definition_kwargs = self._render_task_definition_kwargs(flow)
        try:
            existing_task_definition = boto3_c.describe_task_definition(
                taskDefinition=self.task_definition_kwargs.get("family")
            )["taskDefinition"]

            self._validate_task_definition(
                existing_task_definition, task_definition_kwargs
            )
        except ClientError:
            boto3_c.register_task_definition(**task_definition_kwargs)

    def execute(self, flow: "Flow") -> None:  # type: ignore
        """
        Run the Fargate task that was defined for this flow.

        Args:
            - flow (Flow): the Flow object
        """
        from boto3 import client as boto3_client

        flow_run_id = prefect.context.get("flow_run_id", "unknown")
        container_overrides = [
            {
                "name": "flow-container",
                "environment": [
                    {
                        "name": "PREFECT__CLOUD__AUTH_TOKEN",
                        "value": config.cloud.agent.get("auth_token", "")
                        or config.cloud.get("auth_token", ""),
                    },
                    {"name": "PREFECT__CONTEXT__FLOW_RUN_ID", "value": flow_run_id},
                    {"name": "PREFECT__CONTEXT__IMAGE", "value": get_flow_image(flow)},
                ],
            }
        ]

        boto3_c = boto3_client(
            "ecs",
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            aws_session_token=self.aws_session_token,
            region_name=self.region_name,
        )

        boto3_c.run_task(
            overrides={"containerOverrides": container_overrides},
            launchType=self.launch_type,
            **self.task_run_kwargs,
        )

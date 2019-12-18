from ast import literal_eval
import os
import copy
import json
import re
from typing import Iterable

from prefect import config
from prefect.agent import Agent
from prefect.environments.storage import Docker
from prefect.serialization.storage import StorageSchema
from prefect.utilities.graphql import GraphQLResult


class FargateAgent(Agent):
    """
    Agent which deploys flow runs as tasks using Fargate. This agent can run anywhere as
    long as the proper access configuration variables are set.  Information on using the
    Fargate Agent can be found at https://docs.prefect.io/cloud/agent/fargate.html

    All `kwargs` are accepted that one would normally pass to boto3 for `register_task_definition`
    and `run_task`. For information on the kwargs supported visit the following links:

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.register_task_definition

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ecs.html#ECS.Client.run_task

    Args:
        - name (str, optional): An optional name to give this agent. Can also be set through
            the environment variable `PREFECT__CLOUD__AGENT__NAME`. Defaults to "agent"
        - labels (List[str], optional): a list of labels, which are arbitrary string identifiers used by Prefect
            Agents when polling for work
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
        - enable_task_revisions (bool, optional): Enable registration of task definitions using revisions.
            When enabled, task definitions will use flow name as opposed to flow id and each new version will be a
            task definition revision. Each revision will be registered with a tag called 'PrefectFlowId'
            and 'PrefectFlowVersion' to enable proper lookup for existing revisions.  Flow name is reformatted
            to support task definition naming rules by converting all non-alphanumeric characters to '_'.
            These new tags will also get passed to the task run.
            Defaults to False.
        - use_external_kwargs (bool, optional): When enabled, the agent will check for the existence of an
            external json file containing kwargs to pass into the run_flow process.
        - external_kwargs_s3_bucket (str, optional): S3 bucket containing external kwargs.
        - external_kwargs_s3_key (str, optional): S3 key prefix for the location of <flow_id>/<flow_name>.json
        - **kwargs (dict, optional): additional keyword arguments to pass to boto3 for
            `register_task_definition` and `run_task`
    """

    def __init__(  # type: ignore
        self,
        name: str = None,
        labels: Iterable[str] = None,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        aws_session_token: str = None,
        region_name: str = None,
        enable_task_revisions: bool = False,
        use_external_kwargs: bool = False,
        external_kwargs_s3_bucket: str = None,
        external_kwargs_s3_key: str = None,
        **kwargs
    ) -> None:
        super().__init__(name=name, labels=labels)

        from boto3 import client as boto3_client
        from boto3 import resource as boto3_resource

        # Config used for boto3 client initialization
        aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = aws_secret_access_key or os.getenv(
            "AWS_SECRET_ACCESS_KEY"
        )
        aws_session_token = aws_session_token or os.getenv("AWS_SESSION_TOKEN")
        region_name = region_name or os.getenv("REGION_NAME")

        # revisions and kwargs configurations
        self.enable_task_revisions = enable_task_revisions
        self.use_external_kwargs = use_external_kwargs
        self.external_kwargs_s3_bucket = external_kwargs_s3_bucket
        self.external_kwargs_s3_key = external_kwargs_s3_key

        # Parse accepted kwargs for definition and run
        self.task_definition_kwargs, self.task_run_kwargs = self._parse_kwargs(kwargs, True)

        # populate task_definition_name as None to start
        self.task_definition_name = None

        # Client initialization
        self.boto3_client = boto3_client(
            "ecs",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region_name,
        )
        # fetch external kwargs from s3 if needed
        if self.use_external_kwargs:
            self.s3_resource = boto3_resource(
                "s3",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
                region_name=region_name,
            )

        # get boto3 client for resource groups tagging api
        if self.enable_task_revisions:
            self.boto3_client_tags = boto3_client(
                "resourcegroupstaggingapi",
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
                region_name=region_name,
            )

    def _evaluate_external_kwargs(self, flow_run: GraphQLResult):
        """
        Fetch external kwargs from S3 and create new set of kwargs for `register_task_definition`
        and `run_task` based on copy of default values updated with external values.
        If there is an issue with fetching the kwargs an empty dictionary is returned to allow
        default kwargs to be used.

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            tuple: a tuple of two dictionaries (task_definition_kwargs, task_run_kwargs)
            or a tuple of two None values if use_external_kwargs is disabled.
        """
        if self.use_external_kwargs:
            from botocore.exceptions import ClientError

            # get external kwargs from S3
            try:
                self.logger.info('Fetching external kwargs from S3')
                obj = self.s3_resource.Object(
                    self.external_kwargs_s3_bucket,
                    os.path.join(
                        self.external_kwargs_s3_key,
                        "{}.json".format(
                            flow_run.flow.id[:8]
                        )
                    )
                )
                body = obj.get()['Body'].read().decode('utf-8')
            except ClientError:
                self.logger.info('Flow id {} does not have external kwargs.'.format(flow_run.flow.id[:8]))
                body = '{}'
            self.logger.debug('External kwargs:\n{}'.format(body))

            # create new kwargs from merge of default with external
            self.logger.info('Updating default kwargs with external')
            external_kwargs = json.loads(body)
            # parse external kwargs
            ext_task_definition_kwargs, ext_task_run_kwargs = self._parse_kwargs(external_kwargs)
            self.logger.debug('External task definition kwargs:\n{}'.format(ext_task_definition_kwargs))
            self.logger.debug('External task run kwargs:\n{}'.format(ext_task_run_kwargs))
            # make initial overrides a copy of default kwargs
            task_definition_kwargs_overrides = copy.deepcopy(self.task_definition_kwargs)
            self.logger.debug('Initial task definition overrides:\n{}'.format(task_definition_kwargs_overrides))
            task_run_kwargs_overrides = copy.deepcopy(self.task_run_kwargs)
            self.logger.debug('Initial task run overrides:\n{}'.format(task_run_kwargs_overrides))

            # do not support external tags override on task definitions if enable_task_revisions
            ext_task_definition_kwargs.pop("tags", None)
            self.logger.debug(
                'Overriding tags from external kwargs not supported if enable_task_revisions is True.'
            )

            # Update initial overrides with external kwargs
            task_definition_kwargs_overrides.update(ext_task_definition_kwargs)
            self.logger.debug('Task definition overrides:\n{}'.format(task_definition_kwargs_overrides))
            task_run_kwargs_overrides.update(ext_task_run_kwargs)
            self.logger.debug('Task run overrides:\n{}'.format(task_run_kwargs_overrides))
            # return final updated dictionary
            return task_definition_kwargs_overrides, task_run_kwargs_overrides
        else:
            return None, None

    def _parse_kwargs(self, user_kwargs: dict, check_envars: bool = False) -> tuple:
        """
        Parse the kwargs passed in and separate them out for `register_task_definition`
        and `run_task`. This is required because boto3 does not allow extra kwargs
        and if they are provided it will raise botocore.exceptions.ParamValidationError.

        Args:
            - user_kwargs (dict): The kwargs passed to the initialization of the environment
            - check_envars (bool): Whether to check envars for kwargs

        Returns:
            tuple: a tuple of two dictionaries (task_definition_kwargs, task_run_kwargs)
        """
        definition_kwarg_list = [
            "taskRoleArn",
            "executionRoleArn",
            "volumes",
            "placementConstraints",
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
                self.logger.debug("{} = {}".format(key, item))

        task_run_kwargs = {}
        for key, item in user_kwargs.items():
            if key in run_kwarg_list:
                task_run_kwargs.update({key: item})
                self.logger.debug("{} = {}".format(key, item))

        # Check environment if keys were not provided
        if check_envars:
            for key in definition_kwarg_list:
                if not task_definition_kwargs.get(key) and os.getenv(key):
                    self.logger.debug("{} from environment variable".format(key))
                    def_env_value = os.getenv(key)
                    try:
                        # Parse env var if needed
                        def_env_value = literal_eval(def_env_value)  # type: ignore
                    except ValueError:
                        pass
                    task_definition_kwargs.update({key: def_env_value})

            for key in run_kwarg_list:
                if not task_run_kwargs.get(key) and os.getenv(key):
                    self.logger.debug("{} from environment variable".format(key))
                    run_env_value = os.getenv(key)
                    try:
                        # Parse env var if needed
                        run_env_value = literal_eval(run_env_value)  # type: ignore
                    except ValueError:
                        pass
                    task_run_kwargs.update({key: run_env_value})

        return task_definition_kwargs, task_run_kwargs

    def deploy_flow(self, flow_run: GraphQLResult) -> str:
        """
        Deploy flow runs to Fargate

        Args:
            - flow_run (GraphQLResult): A GraphQLResult flow run object

        Returns:
            - str: Information about the deployment

        Raises:
            - ValueError: if deployment attempted on unsupported Storage type
        """
        self.logger.debug(
            "Deploying flow run {}".format(flow_run.id)  # type: ignore
        )
        # set proper task_definition_name and tags based on enable_task_revisions flag
        if self.enable_task_revisions:
            self.logger.debug("Native ECS task revisions enabled")
            # set task definition name
            self.task_definition_name = re.sub(r'[^a-zA-Z0-9]', '_', flow_run.flow.name)
            # add flow id to definition tags
            if not self.task_definition_kwargs.get("tags"):
                self.task_definition_kwargs["tags"] = []
            else:
                self.task_definition_kwargs["tags"] = copy.deepcopy(self.task_definition_kwargs["tags"])
            append_tag = True
            for i in self.task_definition_kwargs["tags"]:
                if i["key"] == "PrefectFlowId":
                    i["value"] = flow_run.flow.id[:8]
                    append_tag = False
            if append_tag:
                self.task_definition_kwargs["tags"].append({
                    "key": "PrefectFlowId",
                    "value": flow_run.flow.id[:8]
                })
            append_tag = True
            for i in self.task_definition_kwargs["tags"]:
                if i["key"] == "PrefectFlowVersion":
                    i["value"] = str(flow_run.flow.version)
                    append_tag = False
            if append_tag:
                self.task_definition_kwargs["tags"].append({
                    "key": "PrefectFlowVersion",
                    "value": str(flow_run.flow.version)
                })
        else:
            self.task_definition_name = "prefect-task-{}".format(
                flow_run.flow.id[:8]  # type: ignore
            )

        # Require Docker storage
        if not isinstance(StorageSchema().load(flow_run.flow.storage), Docker):
            self.logger.error(
                "Storage for flow run {} is not of type Docker.".format(flow_run.id)
            )
            raise ValueError("Unsupported Storage type")

        # evaluate for external kwargs
        task_definition_kwargs_overrides, task_run_kwargs_overrides = self._evaluate_external_kwargs(flow_run)

        # check if task definition exists
        self.logger.debug("Checking for task definition")
        if not self._verify_task_definition_exists(flow_run):
            self.logger.debug("No task definition found")
            self._create_task_definition(flow_run, task_definition_kwargs_overrides)

        # run task
        task_arn = self._run_task(flow_run, task_run_kwargs_overrides)

        self.logger.debug("Run created for task {}".format(task_arn))

        return "Task ARN: {}".format(task_arn)

    def _verify_task_definition_exists(self, flow_run: GraphQLResult) -> bool:
        """
        Check if a task definition already exists for the flow

        Args:
            - flow_run (GraphQLResult): A GraphQLResult representing a flow run object

        Returns:
            - bool: whether or not a preexisting task definition is found for this flow
        """
        from botocore.exceptions import ClientError

        try:
            definition_exists = True
            task_definition_name = self.task_definition_name
            definition_response = self.boto3_client.describe_task_definition(
                taskDefinition=task_definition_name,
                include=[
                    "TAGS",
                ]
            )
            # if current active task definition has current flow id, then exists
            if self.enable_task_revisions:
                definition_exists = False
                tag_dict = {x['key']: x['value'] for x in definition_response["tags"]}
                current_flow_id = tag_dict.get('PrefectFlowId')
                current_flow_version = int(tag_dict.get('PrefectFlowVersion', 0))
                if current_flow_id == flow_run.flow.id[:8]:
                    self.logger.debug(
                        "Active task definition for {} already exists".format(flow_run.flow.id[:8])  # type: ignore
                    )
                    definition_exists = True
                elif flow_run.flow.version < current_flow_version:
                    tag_search = self.boto3_client_tags.get_resources(
                        TagFilters=[
                            {
                                "Key": "PrefectFlowId",
                                "Values": [flow_run.flow.id[:8]]
                            }
                        ],
                        ResourceTypeFilters=[
                            "ecs:task-definition"
                        ]
                    )
                    if tag_search['ResourceTagMappingList']:
                        self.task_definition_name = [
                            x.get("ResourceARN") for x in tag_search['ResourceTagMappingList']
                        ][-1]
                        self.logger.debug(
                            "Active task definition for {} already exists".format(flow_run.flow.id[:8])  # type: ignore
                        )
                        definition_exists = True
            else:
                self.logger.debug(
                    "Task definition {} found".format(task_definition_name)  # type: ignore
                )
        except ClientError:
            return False
        return definition_exists

    def _create_task_definition(self, flow_run: GraphQLResult, task_definition_kwargs_overrides: dict = None) -> None:
        """
        Create a task definition for the flow that each flow run will use. This function
        is only called when a flow is run for the first time.

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
            - task_definition_kwargs_overrides (dict): kwargs to use over the default kwargs
        """
        self.logger.debug(
            "Using image {} for task definition".format(
                StorageSchema().load(flow_run.flow.storage).name  # type: ignore
            )
        )
        task_definition_name = self.task_definition_name
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
                    {
                        "name": "PREFECT__CLOUD__AGENT__LABELS",
                        "value": str(self.labels),
                    },
                    {"name": "PREFECT__CLOUD__USE_LOCAL_SECRETS", "value": "false"},
                    {
                        "name": "PREFECT__LOGGING__LOG_TO_CLOUD",
                        "value": str(self.log_to_cloud).lower(),
                    },
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

        # Register task definition
        self.logger.debug(
            "Registering task definition {}".format(
                task_definition_name  # type: ignore
            )
        )
        task_definition_kwargs = task_definition_kwargs_overrides or self.task_definition_kwargs
        self.boto3_client.register_task_definition(
            family=task_definition_name,  # type: ignore
            containerDefinitions=container_definitions,
            requiresCompatibilities=["FARGATE"],
            networkMode="awsvpc",
            **task_definition_kwargs
        )

    def _run_task(self, flow_run: GraphQLResult, task_run_kwargs_overrides: dict = None) -> str:
        """
        Run a task using the flow run.

        Args:
            - flow_runs (list): A list of GraphQLResult flow run objects
            - task_run_kwargs_overrides (dict): kwargs to use over the default kwargs
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
                    }
                ],
            }
        ]

        task_definition_name = self.task_definition_name
        # Run task
        self.logger.debug(
            "Running task using task definition {}".format(
                task_definition_name  # type: ignore
            )
        )
        task_run_kwargs = task_run_kwargs_overrides or self.task_run_kwargs
        task = self.boto3_client.run_task(
            taskDefinition=task_definition_name,
            overrides={"containerOverrides": container_overrides},
            launchType="FARGATE",
            **task_run_kwargs
        )

        return task["tasks"][0].get("taskArn")


if __name__ == "__main__":
    FargateAgent().start()

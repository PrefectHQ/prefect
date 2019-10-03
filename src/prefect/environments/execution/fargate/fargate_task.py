import os
import uuid
from typing import Any, List

import cloudpickle
import yaml

import prefect
from prefect import config
from prefect.environments.execution import Environment
from prefect.environments.storage import Docker

from boto3 import client as boto3_client
from botocore.exceptions import ClientError


class FargateTaskEnvironment(Environment):
    """"""

    def __init__(
        self,
        labels: List[str] = None,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        region_name: str = None,
        cluster: str = None,
        **kwargs
    ) -> None:
        self.identifier_label = str(uuid.uuid4())

        # Not serialized, only stored on the object
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.region_name = region_name
        self.cluster = cluster or "default"

        # task_definition = {
        #     "family": kwargs.get("family"),
        #     "taskRoleArn": kwargs.get("taskRoleArn"),
        #     "executionRoleArn": kwargs.get("executionRoleArn"),
        #     "networkMode": kwargs.get()
        # }

        self.task_definition_kwargs = kwargs or {}

        super().__init__(labels=labels)

    def setup(self, storage: "Docker") -> None:
        """
        Sets up any infrastructure needed for this environment

        Args:
            - storage (Storage): the Storage object that contains the flow
        """
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
            # self.logger.debug(
            #     "Task definition {} found".format(flow_run.flow.id[:8])  # type: ignore
            # )
        except ClientError:
            definition_exists = False

        if not definition_exists:
            env_values = [
                {
                    "name": "PREFECT__CLOUD__GRAPHQL",
                    "value": prefect.config.cloud.graphql,
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
            # Populate storage name and flow file path, do this during execution step
            # self.task_definition_kwargs.get("containerDefinitions")[0][
            #     "environment"
            # ].extend(
            #     [
            #         {"name": "PREFECT__CONTEXT__IMAGE", "value": storage.name},
            #         {
            #             "name": "PREFECT__CONTEXT__FLOW_FILE_PATH",
            #             "value": storage.flows,
            #         },
            #     ]
            # )

    def execute(self, storage: "Docker", flow_location: str, **kwargs: Any) -> None:
        """
        Executes the flow for this environment from the storage parameter

        Args:
            - storage (Storage): the Storage object that contains the flow
            - flow_location (str): the location of the Flow to execute
            - **kwargs (Any): additional keyword arguments to pass to the runner
        """
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
            cluster=self.cluster,
            taskDefinition="prefect-task-{}-custom".format(flow_run_id[:8]),
            overrides={"containerOverrides": container_overrides},
            launchType="FARGATE",
            # networkConfiguration=network_configuration,
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

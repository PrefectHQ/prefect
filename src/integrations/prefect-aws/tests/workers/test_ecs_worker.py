import json
import logging
from functools import partial
from typing import Any, Awaitable, Callable, Dict, List, Optional
from unittest.mock import ANY, MagicMock
from unittest.mock import patch as mock_patch
from uuid import uuid4

import anyio
import botocore
import pytest
import yaml
from moto import mock_ec2, mock_ecs, mock_logs
from moto.ec2.utils import generate_instance_identity_document
from pydantic import VERSION as PYDANTIC_VERSION

from prefect.server.schemas.core import FlowRun
from prefect.utilities.asyncutils import run_sync_in_worker_thread

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import ValidationError
else:
    from pydantic import ValidationError

from prefect_aws.credentials import _get_client_cached
from prefect_aws.workers.ecs_worker import (
    _TASK_DEFINITION_CACHE,
    ECS_DEFAULT_CONTAINER_NAME,
    ECS_DEFAULT_CPU,
    ECS_DEFAULT_FAMILY,
    ECS_DEFAULT_MEMORY,
    AwsCredentials,
    ECSJobConfiguration,
    ECSVariables,
    ECSWorker,
    InfrastructureNotAvailable,
    InfrastructureNotFound,
    _get_container,
    get_prefect_image_name,
    mask_sensitive_env_values,
    parse_identifier,
)

TEST_TASK_DEFINITION_YAML = """
containerDefinitions:
- cpu: 1024
  image: prefecthq/prefect:2.1.0-python3.8
  memory: 2048
  name: prefect
family: prefect
"""

TEST_TASK_DEFINITION = yaml.safe_load(TEST_TASK_DEFINITION_YAML)


@pytest.fixture
def flow_run():
    return FlowRun(flow_id=uuid4(), deployment_id=uuid4())


@pytest.fixture
def container_status_code():
    yield MagicMock(return_value=0)


@pytest.fixture(autouse=True)
def reset_task_definition_cache():
    _TASK_DEFINITION_CACHE.clear()
    yield


@pytest.fixture(autouse=True)
def patch_task_watch_poll_interval(monkeypatch):
    # Patch the poll interval to be way shorter for speed during testing!
    monkeypatch.setattr(
        ECSVariables.__fields__["task_watch_poll_interval"], "default", 0.05
    )


def inject_moto_patches(moto_mock, patches: Dict[str, List[Callable]]):
    def injected_call(method, patch_list, *args, **kwargs):
        for patch in patch_list:
            result = patch(method, *args, **kwargs)
        return result

    for account in moto_mock.backends:
        for region in moto_mock.backends[account]:
            backend = moto_mock.backends[account][region]

            for attr, attr_patches in patches.items():
                original_method = getattr(backend, attr)
                setattr(
                    backend, attr, partial(injected_call, original_method, attr_patches)
                )


def patch_run_task(mock, run_task, *args, **kwargs):
    """
    Track calls to `run_task` by calling a mock as well.
    """
    mock(*args, **kwargs)
    return run_task(*args, **kwargs)


def patch_describe_tasks_add_containers(
    session, container_status_code, describe_tasks, *args, **kwargs
):
    """
    Adds the containers to moto's task description.

    Otherwise, containers is always empty.
    """
    ecs_client = session.client("ecs")

    result = describe_tasks(*args, **kwargs)
    for task in result:
        if not task.containers:
            # Pull containers from the task definition
            task_definition = ecs_client.describe_task_definition(
                taskDefinition=task.task_definition_arn
            )["taskDefinition"]
            task.containers = [
                {
                    "name": container["name"],
                    "exitCode": container_status_code.return_value,
                }
                for container in task_definition.get("containerDefinitions", [])
            ]

        # Populate all the containers in overrides
        if task.overrides.get("container_overrides"):
            for container in task.overrides["container_overrides"]:
                if not _get_container(task.containers, container.name):
                    task.containers.append(
                        {
                            "name": container.name,
                            "exitCode": container_status_code.return_value,
                        }
                    )

        # Or add the default container
        else:
            if not _get_container(task.containers, ECS_DEFAULT_CONTAINER_NAME):
                task.containers.append(
                    {
                        "name": ECS_DEFAULT_CONTAINER_NAME,
                        "exitCode": container_status_code.return_value,
                    }
                )

    return result


def patch_calculate_task_resource_requirements(
    _calculate_task_resource_requirements, task_definition
):
    """
    Adds support for non-EC2 execution modes to moto's calculation of task definition.
    """
    for container_definition in task_definition.container_definitions:
        container_definition.setdefault("memory", 0)
    return _calculate_task_resource_requirements(task_definition)


def create_log_stream(session, run_task, *args, **kwargs):
    """
    When running a task, create the log group and stream if logging is configured on
    containers.

    See https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_awslogs.html
    """
    tasks = run_task(*args, **kwargs)
    if not tasks:
        return tasks
    task = tasks[0]

    ecs_client = session.client("ecs")
    logs_client = session.client("logs")

    task_definition = ecs_client.describe_task_definition(
        taskDefinition=task.task_definition_arn
    )["taskDefinition"]

    for container in task_definition.get("containerDefinitions", []):
        log_config = container.get("logConfiguration", {})
        if log_config:
            if log_config.get("logDriver") != "awslogs":
                continue

            options = log_config.get("options", {})
            if not options:
                raise ValueError("logConfiguration does not include options.")

            group_name = options.get("awslogs-group")
            if not group_name:
                raise ValueError(
                    "logConfiguration.options does not include awslogs-group"
                )

            if options.get("awslogs-create-group") == "true":
                logs_client.create_log_group(logGroupName=group_name)

            stream_prefix = options.get("awslogs-stream-prefix")
            if not stream_prefix:
                raise ValueError(
                    "logConfiguration.options does not include awslogs-stream-prefix"
                )

            logs_client.create_log_stream(
                logGroupName=group_name,
                logStreamName=f"{stream_prefix}/{container['name']}/{task.id}",
            )

    return tasks


def add_ec2_instance_to_ecs_cluster(session, cluster_name):
    ecs_client = session.client("ecs")
    ec2_client = session.client("ec2")
    ec2_resource = session.resource("ec2")

    ecs_client.create_cluster(clusterName=cluster_name)

    images = ec2_client.describe_images()
    image_id = images["Images"][0]["ImageId"]

    test_instance = ec2_resource.create_instances(
        ImageId=image_id, MinCount=1, MaxCount=1
    )[0]

    ecs_client.register_container_instance(
        cluster=cluster_name,
        instanceIdentityDocument=json.dumps(
            generate_instance_identity_document(test_instance)
        ),
    )


def create_test_ecs_cluster(ecs_client, cluster_name) -> str:
    """
    Create an ECS cluster and return its ARN
    """
    return ecs_client.create_cluster(clusterName=cluster_name)["cluster"]["clusterArn"]


def describe_task(ecs_client, task_arn, **kwargs) -> dict:
    """
    Describe a single ECS task
    """
    return ecs_client.describe_tasks(tasks=[task_arn], include=["TAGS"], **kwargs)[
        "tasks"
    ][0]


async def stop_task(ecs_client, task_arn, **kwargs):
    """
    Stop an ECS task.

    Additional keyword arguments are passed to `ECSClient.stop_task`.
    """
    task = await run_sync_in_worker_thread(describe_task, ecs_client, task_arn)
    # Check that the task started successfully
    assert task["lastStatus"] == "RUNNING", "Task should be RUNNING before stopping"
    print("Stopping task...")
    await run_sync_in_worker_thread(ecs_client.stop_task, task=task_arn, **kwargs)


def describe_task_definition(ecs_client, task):
    return ecs_client.describe_task_definition(
        taskDefinition=task["taskDefinitionArn"]
    )["taskDefinition"]


@pytest.fixture
def ecs_mocks(
    aws_credentials: AwsCredentials, flow_run: FlowRun, container_status_code
):
    with mock_ecs() as ecs:
        with mock_ec2():
            with mock_logs():
                session = aws_credentials.get_boto3_session()

                inject_moto_patches(
                    ecs,
                    {
                        # Add containers to running tasks — otherwise not included
                        "describe_tasks": [
                            partial(
                                patch_describe_tasks_add_containers,
                                session,
                                container_status_code,
                            )
                        ],
                        # Fix moto internal resource requirement calculations
                        "_calculate_task_resource_requirements": [
                            patch_calculate_task_resource_requirements
                        ],
                        # Add log group creation
                        "run_task": [partial(create_log_stream, session)],
                    },
                )

                create_test_ecs_cluster(session.client("ecs"), "default")

                # NOTE: Even when using FARGATE, moto requires container instances to be
                #       registered. This differs from AWS behavior.
                add_ec2_instance_to_ecs_cluster(session, "default")

                yield ecs


async def construct_configuration(**options):
    variables = ECSVariables(**options)
    print(f"Using variables: {variables.json(indent=2)}")

    configuration = await ECSJobConfiguration.from_template_and_values(
        base_job_template=ECSWorker.get_default_base_job_template(),
        values={**variables.dict(exclude_none=True)},
    )
    print(f"Constructed test configuration: {configuration.json(indent=2)}")

    return configuration


async def construct_configuration_with_job_template(
    template_overrides: dict, **variables: dict
):
    variables = ECSVariables(**variables)
    print(f"Using variables: {variables.json(indent=2)}")

    base_template = ECSWorker.get_default_base_job_template()
    for key in template_overrides:
        base_template["job_configuration"][key] = template_overrides[key]

    print(
        "Using base template configuration:"
        f" {json.dumps(base_template['job_configuration'], indent=2)}"
    )

    configuration = await ECSJobConfiguration.from_template_and_values(
        base_job_template=base_template,
        values={**variables.dict(exclude_none=True)},
    )
    print(f"Constructed test configuration: {configuration.json(indent=2)}")

    return configuration


async def run_then_stop_task(
    worker: ECSWorker,
    configuration: ECSJobConfiguration,
    flow_run: FlowRun,
    after_start: Optional[Callable[[str], Awaitable[Any]]] = None,
) -> str:
    """
    Run an ECS Task then stop it.

    Moto will not advance the state of tasks, so `ECSTask.run` would hang forever if
    the run is created successfully and not stopped.

    `after_start` can be used to run something after the task starts but before it is
    stopped. It will be passed the task arn.
    """
    session = configuration.aws_credentials.get_boto3_session()
    result = None

    async def run(task_status):
        nonlocal result
        result = await worker.run(flow_run, configuration, task_status=task_status)
        return

    with anyio.fail_after(20):
        async with anyio.create_task_group() as tg:
            identifier = await tg.start(run)
            cluster, task_arn = parse_identifier(identifier)

            if after_start:
                await after_start(task_arn)

            # Stop the task after it starts to prevent the test from running forever
            tg.start_soon(
                partial(stop_task, session.client("ecs"), task_arn, cluster=cluster)
            )

    return result


@pytest.mark.usefixtures("ecs_mocks")
async def test_default(aws_credentials: AwsCredentials, flow_run: FlowRun):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials, command="echo test"
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)
    task = describe_task(ecs_client, task_arn)

    assert task == {
        "attachments": ANY,
        "clusterArn": ANY,
        # Note: This container list is not generated by moto and our test suite injects
        #       reasonable values
        "containers": [{"exitCode": 0, "name": "prefect"}],
        "desiredStatus": "STOPPED",
        "lastStatus": "STOPPED",
        "launchType": "FARGATE",
        "overrides": {
            "containerOverrides": [
                {"name": "prefect", "environment": [], "command": ["echo", "test"]}
            ]
        },
        "startedBy": ANY,
        "tags": [],
        "taskArn": ANY,
        "taskDefinitionArn": ANY,
    }

    task_definition = describe_task_definition(ecs_client, task)
    assert task_definition["containerDefinitions"] == [
        {
            "name": ECS_DEFAULT_CONTAINER_NAME,
            "image": get_prefect_image_name(),
            "cpu": 0,
            "memory": 0,
            "portMappings": [],
            "essential": True,
            "environment": [],
            "mountPoints": [],
            "volumesFrom": [],
        }
    ]


@pytest.mark.usefixtures("ecs_mocks")
async def test_image(aws_credentials: AwsCredentials, flow_run: FlowRun):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials, image="prefecthq/prefect-dev:main-python3.9"
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)
    task = describe_task(ecs_client, task_arn)
    assert task["lastStatus"] == "STOPPED"

    task_definition = describe_task_definition(ecs_client, task)
    assert task_definition["containerDefinitions"] == [
        {
            "name": ECS_DEFAULT_CONTAINER_NAME,
            "image": "prefecthq/prefect-dev:main-python3.9",
            "cpu": 0,
            "memory": 0,
            "portMappings": [],
            "essential": True,
            "environment": [],
            "mountPoints": [],
            "volumesFrom": [],
        }
    ]


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize("launch_type", ["EC2", "FARGATE", "FARGATE_SPOT"])
async def test_launch_types(
    aws_credentials: AwsCredentials, launch_type: str, flow_run: FlowRun
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials, launch_type=launch_type
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        # Capture the task run call because moto does not track
        # 'capacityProviderStrategy'
        original_run_task = worker._create_task_run
        mock_run_task = MagicMock(side_effect=original_run_task)
        worker._create_task_run = mock_run_task

        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)

    if launch_type != "FARGATE_SPOT":
        assert launch_type in task_definition["compatibilities"]
        assert task["launchType"] == launch_type
    else:
        assert "FARGATE" in task_definition["compatibilities"]
        # FARGATE SPOT requires a null launch type
        assert not task.get("launchType")
        # Instead, it requires a capacity provider strategy but this is not supported
        # by moto and is not present on the task even when provided so we assert on the
        # mock call to ensure it is sent

        assert mock_run_task.call_args[0][1].get("capacityProviderStrategy") == [
            {"capacityProvider": "FARGATE_SPOT", "weight": 1}
        ]

    requires_capabilities = task_definition.get("requiresCompatibilities", [])
    if launch_type != "EC2":
        assert "FARGATE" in requires_capabilities
    else:
        assert not requires_capabilities


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize("launch_type", ["EC2", "FARGATE", "FARGATE_SPOT"])
@pytest.mark.parametrize(
    "cpu,memory", [(None, None), (1024, None), (None, 2048), (2048, 4096)]
)
async def test_cpu_and_memory(
    aws_credentials: AwsCredentials,
    launch_type: str,
    flow_run: FlowRun,
    cpu: int,
    memory: int,
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials, launch_type=launch_type, cpu=cpu, memory=memory
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)
    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)
    container_definition = _get_container(
        task_definition["containerDefinitions"], ECS_DEFAULT_CONTAINER_NAME
    )
    overrides = task["overrides"]
    container_overrides = _get_container(
        overrides["containerOverrides"], ECS_DEFAULT_CONTAINER_NAME
    )

    if launch_type == "EC2":
        # EC2 requires CPU and memory to be defined at the container level
        assert container_definition["cpu"] == cpu or ECS_DEFAULT_CPU
        assert container_definition["memory"] == memory or ECS_DEFAULT_MEMORY
    else:
        # Fargate requires CPU and memory to be defined at the task definition level
        assert task_definition["cpu"] == str(cpu or ECS_DEFAULT_CPU)
        assert task_definition["memory"] == str(memory or ECS_DEFAULT_MEMORY)

    # We always provide non-null values as overrides on the task run
    assert overrides.get("cpu") == (str(cpu) if cpu else None)
    assert overrides.get("memory") == (str(memory) if memory else None)
    # And as overrides for the Prefect container
    assert container_overrides.get("cpu") == cpu
    assert container_overrides.get("memory") == memory


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize("launch_type", ["EC2", "FARGATE", "FARGATE_SPOT"])
async def test_network_mode_default(
    aws_credentials: AwsCredentials,
    launch_type: str,
    flow_run: FlowRun,
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials, launch_type=launch_type
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)

    if launch_type == "EC2":
        assert task_definition["networkMode"] == "bridge"
    else:
        assert task_definition["networkMode"] == "awsvpc"


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize("launch_type", ["EC2", "FARGATE", "FARGATE_SPOT"])
async def test_container_command(
    aws_credentials: AwsCredentials,
    launch_type: str,
    flow_run: FlowRun,
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        launch_type=launch_type,
        command="prefect version",
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)

    container_overrides = _get_container(
        task["overrides"]["containerOverrides"], ECS_DEFAULT_CONTAINER_NAME
    )
    assert container_overrides["command"] == ["prefect", "version"]


@pytest.mark.usefixtures("ecs_mocks")
async def test_task_definition_arn(aws_credentials: AwsCredentials, flow_run: FlowRun):
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    task_definition_arn = ecs_client.register_task_definition(**TEST_TASK_DEFINITION)[
        "taskDefinition"
    ]["taskDefinitionArn"]

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        task_definition_arn=task_definition_arn,
        launch_type="EC2",
    )

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    print(task)
    assert (
        task["taskDefinitionArn"] == task_definition_arn
    ), "The task definition should be used without registering a new one"


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize(
    "overrides",
    [{"image": "new-image"}, {"configure_cloudwatch_logs": True}, {"family": "foobar"}],
)
async def test_task_definition_arn_with_variables_that_are_ignored(
    aws_credentials, overrides, caplog, flow_run
):
    """
    Any of these overrides should cause the task definition to be copied and
    registered as a new version
    """
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    task_definition_arn = ecs_client.register_task_definition(
        **TEST_TASK_DEFINITION, executionRoleArn="base"
    )["taskDefinition"]["taskDefinitionArn"]

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        task_definition_arn=task_definition_arn,
        launch_type="EC2",
        **overrides,
    )

    async with ECSWorker(work_pool_name="test") as worker:
        with caplog.at_level(
            logging.INFO, logger=worker.get_flow_run_logger(flow_run).name
        ):
            result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    assert (
        task["taskDefinitionArn"] == task_definition_arn
    ), "A new task definition should not be registered"

    # TODO: Add logging for this case
    # assert (
    #     "Settings require changes to the linked task definition. "
    #     "The settings will be ignored. "
    #     "Enable DEBUG level logs to see the difference."
    #     in caplog.text
    # )


@pytest.mark.usefixtures("ecs_mocks")
async def test_environment_variables(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        env={"FOO": "BAR"},
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)
    prefect_container_definition = _get_container(
        task_definition["containerDefinitions"], ECS_DEFAULT_CONTAINER_NAME
    )
    assert not prefect_container_definition[
        "environment"
    ], "Variables should not be passed until runtime"

    prefect_container_overrides = _get_container(
        task["overrides"]["containerOverrides"], ECS_DEFAULT_CONTAINER_NAME
    )
    expected = [{"name": "FOO", "value": "BAR"}]
    assert prefect_container_overrides.get("environment") == expected


@pytest.mark.usefixtures("ecs_mocks")
async def test_labels(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        labels={
            "foo": "bar",
            "af_sn253@!$@&$%@(bfausfg!#!*&):@cas{}[]'XY": (
                "af_sn253@!$@&$%@(bfausfg!#!*&):@cas{}[]'XY"
            ),
        },
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)
    assert not task_definition.get("tags"), "Labels should not be passed until runtime"
    assert task.get("tags") == [
        {
            "key": "foo",
            "value": "bar",
        },
        {
            # Slugified to remove invalid characters
            "key": "af_sn253@-@-@-bfausfg-:@cas-XY",
            "value": "af_sn253@-@-@-bfausfg-:@cas-XY",
        },
    ]


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize("default_cluster", [True, False])
async def test_cluster(
    aws_credentials: AwsCredentials, flow_run: FlowRun, default_cluster: bool
):
    configuration = configuration = await construct_configuration(
        cluster=None if default_cluster else "second-cluster",
        aws_credentials=aws_credentials,
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    # Construct a non-default cluster. We build this in either case since otherwise
    # there is only one cluster and there's no choice but to use the default.
    second_cluster_arn = create_test_ecs_cluster(ecs_client, "second-cluster")
    add_ec2_instance_to_ecs_cluster(session, "second-cluster")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)

    if default_cluster:
        assert task["clusterArn"].endswith("default")
    else:
        assert task["clusterArn"] == second_cluster_arn


@pytest.mark.usefixtures("ecs_mocks")
async def test_execution_role_arn(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        execution_role_arn="test",
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)

    assert task_definition["executionRoleArn"] == "test"


@pytest.mark.usefixtures("ecs_mocks")
async def test_task_role_arn(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        task_role_arn="test",
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)
    task = describe_task(ecs_client, task_arn)

    assert task["overrides"]["taskRoleArn"] == "test"


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_from_vpc_id(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ec2_resource = session.resource("ec2")
    vpc = ec2_resource.create_vpc(CidrBlock="10.0.0.0/16")
    subnet = ec2_resource.create_subnet(CidrBlock="10.0.2.0/24", VpcId=vpc.id)

    configuration = await construct_configuration(
        aws_credentials=aws_credentials, vpc_id=vpc.id
    )

    session = aws_credentials.get_boto3_session()

    async with ECSWorker(work_pool_name="test") as worker:
        # Capture the task run call because moto does not track 'networkConfiguration'
        original_run_task = worker._create_task_run
        mock_run_task = MagicMock(side_effect=original_run_task)
        worker._create_task_run = mock_run_task

        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    network_configuration = mock_run_task.call_args[0][1].get("networkConfiguration")

    # Subnet ids are copied from the vpc
    assert network_configuration == {
        "awsvpcConfiguration": {
            "subnets": [subnet.id],
            "assignPublicIp": "ENABLED",
            "securityGroups": [],
        }
    }


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_1_subnet_in_custom_settings_1_in_vpc(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ec2_resource = session.resource("ec2")
    vpc = ec2_resource.create_vpc(CidrBlock="10.0.0.0/16")
    subnet = ec2_resource.create_subnet(CidrBlock="10.0.2.0/24", VpcId=vpc.id)
    security_group = ec2_resource.create_security_group(
        GroupName="ECSWorkerTestSG", Description="ECS Worker test SG", VpcId=vpc.id
    )

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        vpc_id=vpc.id,
        override_network_configuration=True,
        network_configuration={
            "subnets": [subnet.id],
            "assignPublicIp": "DISABLED",
            "securityGroups": [security_group.id],
        },
    )

    session = aws_credentials.get_boto3_session()

    async with ECSWorker(work_pool_name="test") as worker:
        # Capture the task run call because moto does not track 'networkConfiguration'
        original_run_task = worker._create_task_run
        mock_run_task = MagicMock(side_effect=original_run_task)
        worker._create_task_run = mock_run_task

        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    network_configuration = mock_run_task.call_args[0][1].get("networkConfiguration")

    # Subnet ids are copied from the vpc
    assert network_configuration == {
        "awsvpcConfiguration": {
            "subnets": [subnet.id],
            "assignPublicIp": "DISABLED",
            "securityGroups": [security_group.id],
        }
    }


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_1_sn_in_custom_settings_many_in_vpc(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ec2_resource = session.resource("ec2")
    vpc = ec2_resource.create_vpc(CidrBlock="10.0.0.0/16")
    subnet = ec2_resource.create_subnet(CidrBlock="10.0.2.0/24", VpcId=vpc.id)
    ec2_resource.create_subnet(CidrBlock="10.0.3.0/24", VpcId=vpc.id)
    ec2_resource.create_subnet(CidrBlock="10.0.4.0/24", VpcId=vpc.id)

    security_group = ec2_resource.create_security_group(
        GroupName="ECSWorkerTestSG", Description="ECS Worker test SG", VpcId=vpc.id
    )

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        vpc_id=vpc.id,
        override_network_configuration=True,
        network_configuration={
            "subnets": [subnet.id],
            "assignPublicIp": "DISABLED",
            "securityGroups": [security_group.id],
        },
    )

    session = aws_credentials.get_boto3_session()

    async with ECSWorker(work_pool_name="test") as worker:
        # Capture the task run call because moto does not track 'networkConfiguration'
        original_run_task = worker._create_task_run
        mock_run_task = MagicMock(side_effect=original_run_task)
        worker._create_task_run = mock_run_task

        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    network_configuration = mock_run_task.call_args[0][1].get("networkConfiguration")

    # Subnet ids are copied from the vpc
    assert network_configuration == {
        "awsvpcConfiguration": {
            "subnets": [subnet.id],
            "assignPublicIp": "DISABLED",
            "securityGroups": [security_group.id],
        }
    }


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_many_subnet_in_custom_settings_many_in_vpc(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ec2_resource = session.resource("ec2")
    vpc = ec2_resource.create_vpc(CidrBlock="10.0.0.0/16")
    subnets = [
        ec2_resource.create_subnet(CidrBlock="10.0.2.0/24", VpcId=vpc.id),
        ec2_resource.create_subnet(CidrBlock="10.0.33.0/24", VpcId=vpc.id),
        ec2_resource.create_subnet(CidrBlock="10.0.44.0/24", VpcId=vpc.id),
    ]
    subnet_ids = [subnet.id for subnet in subnets]

    security_group = ec2_resource.create_security_group(
        GroupName="ECSWorkerTestSG", Description="ECS Worker test SG", VpcId=vpc.id
    )

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        vpc_id=vpc.id,
        override_network_configuration=True,
        network_configuration={
            "subnets": subnet_ids,
            "assignPublicIp": "DISABLED",
            "securityGroups": [security_group.id],
        },
    )

    session = aws_credentials.get_boto3_session()

    async with ECSWorker(work_pool_name="test") as worker:
        # Capture the task run call because moto does not track 'networkConfiguration'
        original_run_task = worker._create_task_run
        mock_run_task = MagicMock(side_effect=original_run_task)
        worker._create_task_run = mock_run_task

        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    network_configuration = mock_run_task.call_args[0][1].get("networkConfiguration")

    # Subnet ids are copied from the vpc
    assert network_configuration == {
        "awsvpcConfiguration": {
            "subnets": subnet_ids,
            "assignPublicIp": "DISABLED",
            "securityGroups": [security_group.id],
        }
    }


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_from_custom_settings_invalid_subnet(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ec2_resource = session.resource("ec2")
    vpc = ec2_resource.create_vpc(CidrBlock="10.0.0.0/16")
    security_group = ec2_resource.create_security_group(
        GroupName="ECSWorkerTestSG", Description="ECS Worker test SG", VpcId=vpc.id
    )
    ec2_resource.create_subnet(CidrBlock="10.0.2.0/24", VpcId=vpc.id)

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        vpc_id=vpc.id,
        override_network_configuration=True,
        network_configuration={
            "subnets": ["sn-8asdas"],
            "assignPublicIp": "DISABLED",
            "securityGroups": [security_group.id],
        },
    )

    session = aws_credentials.get_boto3_session()

    with pytest.raises(
        ValueError,
        match=(
            r"Subnets \['sn-8asdas'\] not found within VPC with ID "
            + vpc.id
            + r"\.Please check that VPC is associated with supplied subnets\."
        ),
    ):
        async with ECSWorker(work_pool_name="test") as worker:
            original_run_task = worker._create_task_run
            mock_run_task = MagicMock(side_effect=original_run_task)
            worker._create_task_run = mock_run_task

            await run_then_stop_task(worker, configuration, flow_run)


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_from_custom_settings_invalid_subnet_multiple_vpc_subnets(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ec2_resource = session.resource("ec2")
    vpc = ec2_resource.create_vpc(CidrBlock="10.0.0.0/16")
    security_group = ec2_resource.create_security_group(
        GroupName="ECSWorkerTestSG", Description="ECS Worker test SG", VpcId=vpc.id
    )
    subnet = ec2_resource.create_subnet(CidrBlock="10.0.2.0/24", VpcId=vpc.id)
    invalid_subnet_id = "subnet-3bf19de7"

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        vpc_id=vpc.id,
        override_network_configuration=True,
        network_configuration={
            "subnets": [invalid_subnet_id, subnet.id],
            "assignPublicIp": "DISABLED",
            "securityGroups": [security_group.id],
        },
    )

    session = aws_credentials.get_boto3_session()

    with pytest.raises(
        ValueError,
        match=(
            rf"Subnets \['{invalid_subnet_id}', '{subnet.id}'\] not found within VPC"
            f" with ID {vpc.id}.Please check that VPC is associated with supplied"
            " subnets."
        ),
    ):
        async with ECSWorker(work_pool_name="test") as worker:
            original_run_task = worker._create_task_run
            mock_run_task = MagicMock(side_effect=original_run_task)
            worker._create_task_run = mock_run_task

            await run_then_stop_task(worker, configuration, flow_run)


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_configure_network_requires_vpc_id(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    with pytest.raises(
        ValidationError,
        match="You must provide a `vpc_id` to enable custom `network_configuration`.",
    ):
        await construct_configuration(
            aws_credentials=aws_credentials,
            override_network_configuration=True,
            network_configuration={
                "subnets": [],
                "assignPublicIp": "ENABLED",
                "securityGroups": [],
            },
        )


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_from_default_vpc(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ec2_client = session.client("ec2")

    default_vpc_id = ec2_client.describe_vpcs(
        Filters=[{"Name": "isDefault", "Values": ["true"]}]
    )["Vpcs"][0]["VpcId"]
    default_subnets = ec2_client.describe_subnets(
        Filters=[{"Name": "vpc-id", "Values": [default_vpc_id]}]
    )["Subnets"]

    configuration = await construct_configuration(aws_credentials=aws_credentials)

    async with ECSWorker(work_pool_name="test") as worker:
        # Capture the task run call because moto does not track 'networkConfiguration'
        original_run_task = worker._create_task_run
        mock_run_task = MagicMock(side_effect=original_run_task)
        worker._create_task_run = mock_run_task

        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0

    network_configuration = mock_run_task.call_args[0][1].get("networkConfiguration")

    # Subnet ids are copied from the vpc
    assert network_configuration == {
        "awsvpcConfiguration": {
            "subnets": [subnet["SubnetId"] for subnet in default_subnets],
            "assignPublicIp": "ENABLED",
            "securityGroups": [],
        }
    }


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize("explicit_network_mode", [True, False])
async def test_network_config_is_empty_without_awsvpc_network_mode(
    aws_credentials: AwsCredentials, explicit_network_mode: bool, flow_run: FlowRun
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        # EC2 uses the 'bridge' network mode by default but we want to have test
        # coverage for when it is set on the task definition
        task_definition={"networkMode": "bridge"} if explicit_network_mode else None,
        # FARGATE requires the 'awsvpc' network mode
        launch_type="EC2",
    )

    async with ECSWorker(work_pool_name="test") as worker:
        # Capture the task run call because moto does not track 'networkConfiguration'
        original_run_task = worker._create_task_run
        mock_run_task = MagicMock(side_effect=original_run_task)
        worker._create_task_run = mock_run_task

        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0

    network_configuration = mock_run_task.call_args[0][1].get("networkConfiguration")
    assert network_configuration is None


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_missing_default_vpc(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ec2_client = session.client("ec2")

    default_vpc_id = ec2_client.describe_vpcs(
        Filters=[{"Name": "isDefault", "Values": ["true"]}]
    )["Vpcs"][0]["VpcId"]
    ec2_client.delete_vpc(VpcId=default_vpc_id)

    configuration = await construct_configuration(aws_credentials=aws_credentials)

    with pytest.raises(ValueError, match="Failed to find the default VPC"):
        async with ECSWorker(work_pool_name="test") as worker:
            await run_then_stop_task(worker, configuration, flow_run)


@pytest.mark.usefixtures("ecs_mocks")
async def test_network_config_from_vpc_with_no_subnets(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ec2_resource = session.resource("ec2")
    vpc = ec2_resource.create_vpc(CidrBlock="172.16.0.0/16")

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        vpc_id=vpc.id,
    )

    with pytest.raises(
        ValueError, match=f"Failed to find subnets for VPC with ID {vpc.id}"
    ):
        async with ECSWorker(work_pool_name="test") as worker:
            await run_then_stop_task(worker, configuration, flow_run)


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize("launch_type", ["FARGATE", "FARGATE_SPOT"])
async def test_bridge_network_mode_raises_on_fargate(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
    launch_type: str,
):
    configuration = await construct_configuration_with_job_template(
        aws_credentials=aws_credentials,
        launch_type=launch_type,
        template_overrides=dict(task_definition={"networkMode": "bridge"}),
    )

    with pytest.raises(
        ValueError,
        match=(
            "Found network mode 'bridge' which is not compatible with launch type "
            f"{launch_type!r}"
        ),
    ):
        async with ECSWorker(work_pool_name="test") as worker:
            await run_then_stop_task(worker, configuration, flow_run)


@pytest.mark.usefixtures("ecs_mocks")
async def test_stream_output(
    aws_credentials: AwsCredentials, flow_run: FlowRun, caplog
):
    session = aws_credentials.get_boto3_session()
    logs_client = session.client("logs")

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        configure_cloudwatch_logs=True,
        stream_output=True,
        execution_role_arn="test",
        # Override the family so it does not match the container name
        family="test-family",
        # Override the prefix so it does not match the container name
        cloudwatch_logs_options={"awslogs-stream-prefix": "test-prefix"},
        cluster="default",
    )

    async def write_fake_log(task_arn):
        # TODO: moto does not appear to support actually reading these logs
        #       as they do not appear during `get_log_event` calls
        # prefix/container-name/task-id
        stream_name = f"test-prefix/prefect/{task_arn.rsplit('/')[-1]}"
        logs_client.put_log_events(
            logGroupName="prefect",
            logStreamName=stream_name,
            logEvents=[
                {"timestamp": i, "message": f"test-message-{i}"} for i in range(100)
            ],
        )

    async with ECSWorker(work_pool_name="test") as worker:
        await run_then_stop_task(
            worker, configuration, flow_run, after_start=write_fake_log
        )

    logs_client = session.client("logs")
    streams = logs_client.describe_log_streams(logGroupName="prefect")["logStreams"]

    assert len(streams) == 1

    # Ensure we did not encounter any logging errors
    assert "Failed to read log events" not in caplog.text

    # TODO: When moto supports reading logs, fix this
    # out, err = capsys.readouterr()
    # assert "test-message-{i}" in err


orig = botocore.client.BaseClient._make_api_call


def mock_make_api_call(self, operation_name, kwarg):
    if operation_name == "RunTask":
        return {
            "failures": [
                {"arn": "string", "reason": "string", "detail": "string"},
            ]
        }
    return orig(self, operation_name, kwarg)


@pytest.mark.usefixtures("ecs_mocks")
async def test_run_task_error_handling(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
    capsys,
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        task_role_arn="test",
    )

    with mock_patch(
        "botocore.client.BaseClient._make_api_call", new=mock_make_api_call
    ):
        async with ECSWorker(work_pool_name="test") as worker:
            with pytest.raises(RuntimeError, match="Failed to run ECS task") as exc:
                await run_then_stop_task(worker, configuration, flow_run)

    assert exc.value.args[0] == "Failed to run ECS task: string"


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize(
    "cloudwatch_logs_options",
    [
        {
            "awslogs-stream-prefix": "override-prefix",
            "max-buffer-size": "2m",
        },
        {
            "max-buffer-size": "2m",
        },
    ],
)
async def test_cloudwatch_log_options(
    aws_credentials: AwsCredentials, flow_run: FlowRun, cloudwatch_logs_options: dict
):
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        configure_cloudwatch_logs=True,
        execution_role_arn="test",
        cloudwatch_logs_options=cloudwatch_logs_options,
    )
    work_pool_name = "test"
    async with ECSWorker(work_pool_name=work_pool_name) as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)

    for container in task_definition["containerDefinitions"]:
        prefix = f"prefect-logs_{work_pool_name}_{flow_run.deployment_id}"
        if cloudwatch_logs_options.get("awslogs-stream-prefix"):
            prefix = cloudwatch_logs_options["awslogs-stream-prefix"]
        if container["name"] == ECS_DEFAULT_CONTAINER_NAME:
            # Assert that the container has logging configured with user
            # provided options
            assert container["logConfiguration"] == {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-create-group": "true",
                    "awslogs-group": "prefect",
                    "awslogs-region": "us-east-1",
                    "awslogs-stream-prefix": prefix,
                    "max-buffer-size": "2m",
                },
            }
        else:
            # Other containers should not be modified
            assert "logConfiguration" not in container


@pytest.mark.usefixtures("ecs_mocks")
async def test_deregister_task_definition(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        auto_deregister_task_definition=True,
    )

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)
    assert task_definition["status"] == "INACTIVE"


@pytest.mark.usefixtures("ecs_mocks")
async def test_deregister_task_definition_does_not_apply_to_linked_arn(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    task_definition_arn = ecs_client.register_task_definition(**TEST_TASK_DEFINITION)[
        "taskDefinition"
    ]["taskDefinitionArn"]

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        auto_deregister_task_definition=True,
        task_definition_arn=task_definition_arn,
        launch_type="EC2",
    )
    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    describe_task_definition(ecs_client, task)["status"] == "ACTIVE"


@pytest.mark.usefixtures("ecs_mocks")
async def test_match_latest_revision_in_family(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    configuration_1 = await construct_configuration(
        aws_credentials=aws_credentials,
    )

    configuration_2 = await construct_configuration(
        aws_credentials=aws_credentials,
        execution_role_arn="test",
    )

    configuration_3 = await construct_configuration(
        aws_credentials=aws_credentials,
        match_latest_revision_in_family=True,
        execution_role_arn="test",
    )

    # Let the first worker run and register two task definitions
    async with ECSWorker(work_pool_name="test") as worker:
        await run_then_stop_task(worker, configuration_1, flow_run)
        result_1 = await run_then_stop_task(worker, configuration_2, flow_run)

    # Start a new worker with an empty cache
    async with ECSWorker(work_pool_name="test") as worker:
        result_2 = await run_then_stop_task(worker, configuration_3, flow_run)

    assert result_1.status_code == 0
    _, task_arn_1 = parse_identifier(result_1.identifier)

    assert result_2.status_code == 0
    _, task_arn_2 = parse_identifier(result_2.identifier)

    task_1 = describe_task(ecs_client, task_arn_1)
    task_2 = describe_task(ecs_client, task_arn_2)

    assert task_1["taskDefinitionArn"] == task_2["taskDefinitionArn"]
    assert task_2["taskDefinitionArn"].endswith(":2")


@pytest.mark.usefixtures("ecs_mocks")
async def test_match_latest_revision_in_family_custom_family(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    configuration_1 = await construct_configuration(
        aws_credentials=aws_credentials,
        family="test-family",
    )

    configuration_2 = await construct_configuration(
        aws_credentials=aws_credentials,
        execution_role_arn="test",
        family="test-family",
    )

    configuration_3 = await construct_configuration(
        aws_credentials=aws_credentials,
        match_latest_revision_in_family=True,
        execution_role_arn="test",
        family="test-family",
    )

    # Let the first worker run and register two task definitions
    async with ECSWorker(work_pool_name="test") as worker:
        await run_then_stop_task(worker, configuration_1, flow_run)
        result_1 = await run_then_stop_task(worker, configuration_2, flow_run)

    # Start a new worker with an empty cache
    async with ECSWorker(work_pool_name="test") as worker:
        result_2 = await run_then_stop_task(worker, configuration_3, flow_run)

    assert result_1.status_code == 0
    _, task_arn_1 = parse_identifier(result_1.identifier)

    assert result_2.status_code == 0
    _, task_arn_2 = parse_identifier(result_2.identifier)

    task_1 = describe_task(ecs_client, task_arn_1)
    task_2 = describe_task(ecs_client, task_arn_2)

    assert task_1["taskDefinitionArn"] == task_2["taskDefinitionArn"]
    assert task_2["taskDefinitionArn"].endswith(":2")


@pytest.mark.usefixtures("ecs_mocks")
async def test_worker_caches_registered_task_definitions(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials, command="echo test"
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result_1 = await run_then_stop_task(worker, configuration, flow_run)
        result_2 = await run_then_stop_task(worker, configuration, flow_run)

    assert result_2.status_code == 0

    _, task_arn_1 = parse_identifier(result_1.identifier)
    task_1 = describe_task(ecs_client, task_arn_1)
    _, task_arn_2 = parse_identifier(result_2.identifier)
    task_2 = describe_task(ecs_client, task_arn_2)

    assert task_1["taskDefinitionArn"] == task_2["taskDefinitionArn"]
    assert flow_run.deployment_id in _TASK_DEFINITION_CACHE


@pytest.mark.usefixtures("ecs_mocks")
async def test_worker_cache_miss_for_registered_task_definitions_clears_from_cache(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials, command="echo test"
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result_1 = await run_then_stop_task(worker, configuration, flow_run)

        # Fail to retrieve from cache on next run
        worker._retrieve_task_definition = MagicMock(
            side_effect=RuntimeError("failure retrieving from cache")
        )

        result_2 = await run_then_stop_task(worker, configuration, flow_run)

    assert result_2.status_code == 0

    _, task_arn_1 = parse_identifier(result_1.identifier)
    task_1 = describe_task(ecs_client, task_arn_1)
    _, task_arn_2 = parse_identifier(result_2.identifier)
    task_2 = describe_task(ecs_client, task_arn_2)

    assert task_1["taskDefinitionArn"] != task_2["taskDefinitionArn"]
    assert (
        task_1["taskDefinitionArn"] not in _TASK_DEFINITION_CACHE.values()
    ), _TASK_DEFINITION_CACHE


@pytest.mark.usefixtures("ecs_mocks")
async def test_worker_task_definition_cache_is_per_deployment_id(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials, command="echo test"
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result_1 = await run_then_stop_task(worker, configuration, flow_run)
        result_2 = await run_then_stop_task(
            worker, configuration, flow_run.copy(update=dict(deployment_id=uuid4()))
        )

    assert result_2.status_code == 0

    _, task_arn_1 = parse_identifier(result_1.identifier)
    task_1 = describe_task(ecs_client, task_arn_1)
    _, task_arn_2 = parse_identifier(result_2.identifier)
    task_2 = describe_task(ecs_client, task_arn_2)

    assert task_1["taskDefinitionArn"] != task_2["taskDefinitionArn"]


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize(
    "overrides",
    [{"image": "new-image"}, {"configure_cloudwatch_logs": True}, {"family": "foobar"}],
)
async def test_worker_task_definition_cache_miss_on_config_changes(
    aws_credentials: AwsCredentials, flow_run: FlowRun, overrides: dict
):
    configuration_1 = await construct_configuration(
        aws_credentials=aws_credentials, execution_role_arn="test"
    )
    configuration_2 = await construct_configuration(
        aws_credentials=aws_credentials, execution_role_arn="test", **overrides
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result_1 = await run_then_stop_task(worker, configuration_1, flow_run)
        result_2 = await run_then_stop_task(worker, configuration_2, flow_run)

    assert result_2.status_code == 0

    _, task_arn_1 = parse_identifier(result_1.identifier)
    task_1 = describe_task(ecs_client, task_arn_1)
    _, task_arn_2 = parse_identifier(result_2.identifier)
    task_2 = describe_task(ecs_client, task_arn_2)

    assert task_1["taskDefinitionArn"] != task_2["taskDefinitionArn"]


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize(
    "overrides",
    [{"image": "new-image"}, {"configure_cloudwatch_logs": True}, {"family": "foobar"}],
)
async def test_worker_task_definition_cache_miss_on_deregistered(
    aws_credentials: AwsCredentials, flow_run: FlowRun, overrides: dict
):
    configuration_1 = await construct_configuration(
        aws_credentials=aws_credentials,
        execution_role_arn="test",
        auto_deregister_task_defininition=True,
    )
    configuration_2 = await construct_configuration(
        aws_credentials=aws_credentials, execution_role_arn="test", **overrides
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result_1 = await run_then_stop_task(worker, configuration_1, flow_run)
        result_2 = await run_then_stop_task(worker, configuration_2, flow_run)

    assert result_2.status_code == 0

    _, task_arn_1 = parse_identifier(result_1.identifier)
    task_1 = describe_task(ecs_client, task_arn_1)
    _, task_arn_2 = parse_identifier(result_2.identifier)
    task_2 = describe_task(ecs_client, task_arn_2)

    assert task_1["taskDefinitionArn"] != task_2["taskDefinitionArn"]


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize("launch_type", ["EC2", "FARGATE"])
@pytest.mark.parametrize(
    "overrides",
    [
        {"env": {"FOO": "BAR"}},
        {"command": "test"},
        {"labels": {"FOO": "BAR"}},
        {"stream_output": True, "configure_cloudwatch_logs": False},
        {"cluster": "test"},
        {"task_role_arn": "test"},
        # Note: null environment variables can cause override, but not when missing
        # from the base task definition
        {"env": {"FOO": None}},
        # The following would not result in a copy when using a task_definition_arn
        # but will be eagerly set on the new task definition and result in a cache miss
        # {"cpu": 2048},
        # {"memory": 4096},
        # {"execution_role_arn": "test"},
        # {"launch_type": "EXTERNAL"},
    ],
    ids=lambda item: str(sorted(list(set(item.keys())))),
)
async def test_worker_task_definition_cache_hit_on_config_changes(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
    overrides: dict,
    launch_type: str,
):
    """
    Any of these overrides should be configured at runtime and not cause a cache miss
    and for a new task definition to be registered
    """
    configuration_1 = await construct_configuration(
        aws_credentials=aws_credentials,
        execution_role_arn="test",
        launch_type=launch_type,
    )
    configuration_2 = await construct_configuration(
        aws_credentials=aws_credentials,
        execution_role_arn="test",
        launch_type=launch_type,
        **overrides,
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    if "cluster" in overrides:
        create_test_ecs_cluster(ecs_client, overrides["cluster"])
        add_ec2_instance_to_ecs_cluster(session, overrides["cluster"])

    async with ECSWorker(work_pool_name="test") as worker:
        result_1 = await run_then_stop_task(worker, configuration_1, flow_run)
        result_2 = await run_then_stop_task(worker, configuration_2, flow_run)

    assert result_2.status_code == 0

    _, task_arn_1 = parse_identifier(result_1.identifier)
    task_1 = describe_task(ecs_client, task_arn_1)
    _, task_arn_2 = parse_identifier(result_2.identifier)
    task_2 = describe_task(ecs_client, task_arn_2)

    assert (
        task_1["taskDefinitionArn"] == task_2["taskDefinitionArn"]
    ), "The existing task definition should be used"


@pytest.mark.usefixtures("ecs_mocks")
async def test_user_defined_container_command_in_task_definition_template(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
):
    configuration = await construct_configuration_with_job_template(
        template_overrides=dict(
            task_definition={
                "containerDefinitions": [
                    {"name": ECS_DEFAULT_CONTAINER_NAME, "command": ["echo", "hello"]}
                ]
            }
        ),
        aws_credentials=aws_credentials,
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)

    container_overrides = _get_container(
        task["overrides"]["containerOverrides"], ECS_DEFAULT_CONTAINER_NAME
    )
    assert "command" not in container_overrides


@pytest.mark.usefixtures("ecs_mocks")
async def test_user_defined_container_command_in_task_definition_template_override(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
):
    configuration = await construct_configuration_with_job_template(
        template_overrides=dict(
            task_definition={
                "containerDefinitions": [
                    {"name": ECS_DEFAULT_CONTAINER_NAME, "command": ["echo", "hello"]}
                ]
            }
        ),
        aws_credentials=aws_credentials,
        command="echo goodbye",
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)

    container_overrides = _get_container(
        task["overrides"]["containerOverrides"], ECS_DEFAULT_CONTAINER_NAME
    )
    assert container_overrides["command"] == ["echo", "goodbye"]


@pytest.mark.usefixtures("ecs_mocks")
async def test_user_defined_container_in_task_definition_template(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
):
    configuration = await construct_configuration_with_job_template(
        template_overrides=dict(
            task_definition={
                "containerDefinitions": [
                    {
                        "name": "user-defined-name",
                        "command": ["echo", "hello"],
                        "image": "alpine",
                    }
                ]
            },
        ),
        aws_credentials=aws_credentials,
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)

    user_container = _get_container(
        task_definition["containerDefinitions"], "user-defined-name"
    )
    assert user_container is not None, "The user-specified container should be present"
    assert user_container["command"] == ["echo", "hello"]
    assert user_container["image"] == "alpine", "The image should be left unchanged"

    default_container = _get_container(
        task_definition["containerDefinitions"], ECS_DEFAULT_CONTAINER_NAME
    )
    assert default_container is None, "The default container should be not be added"

    container_overrides = task["overrides"]["containerOverrides"]
    user_container_overrides = _get_container(container_overrides, "user-defined-name")
    default_container_overrides = _get_container(
        container_overrides, ECS_DEFAULT_CONTAINER_NAME
    )
    assert (
        user_container_overrides
    ), "The user defined container should be included in overrides"
    assert (
        default_container_overrides is None
    ), "The default container should not be in overrides"


@pytest.mark.usefixtures("ecs_mocks")
async def test_user_defined_container_image_in_task_definition_template(
    aws_credentials: AwsCredentials,
    flow_run: FlowRun,
):
    configuration = await construct_configuration_with_job_template(
        template_overrides=dict(
            task_definition={
                "containerDefinitions": [
                    {
                        "name": ECS_DEFAULT_CONTAINER_NAME,
                        "image": "use-this-image",
                    }
                ]
            },
        ),
        aws_credentials=aws_credentials,
        image="not-templated-anywhere",
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)

    prefect_container = _get_container(
        task_definition["containerDefinitions"], ECS_DEFAULT_CONTAINER_NAME
    )
    assert (
        prefect_container["image"] == "use-this-image"
    ), "The image from the task definition should be used"


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize("launch_type", ["EC2", "FARGATE", "FARGATE_SPOT"])
async def test_user_defined_cpu_and_memory_in_task_definition_template(
    aws_credentials: AwsCredentials, launch_type: str, flow_run: FlowRun
):
    configuration = await construct_configuration_with_job_template(
        template_overrides=dict(
            task_definition={
                "containerDefinitions": [
                    {
                        "name": ECS_DEFAULT_CONTAINER_NAME,
                        "command": "{{ command }}",
                        "image": "{{ image }}",
                        "cpu": 2048,
                        "memory": 4096,
                    }
                ],
                "cpu": "4096",
                "memory": "8192",
            },
        ),
        aws_credentials=aws_credentials,
        launch_type=launch_type,
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)

    container_definition = _get_container(
        task_definition["containerDefinitions"], ECS_DEFAULT_CONTAINER_NAME
    )
    overrides = task["overrides"]
    container_overrides = _get_container(
        overrides["containerOverrides"], ECS_DEFAULT_CONTAINER_NAME
    )

    # All of these values should be retained
    assert container_definition["cpu"] == 2048
    assert container_definition["memory"] == 4096
    assert task_definition["cpu"] == str(4096)
    assert task_definition["memory"] == str(8192)

    # No values should be overridden at runtime
    assert overrides.get("cpu") is None
    assert overrides.get("memory") is None
    assert container_overrides.get("cpu") is None
    assert container_overrides.get("memory") is None


@pytest.mark.usefixtures("ecs_mocks")
async def test_user_defined_environment_variables_in_task_definition_template(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    configuration = await construct_configuration_with_job_template(
        template_overrides=dict(
            task_definition={
                "containerDefinitions": [
                    {
                        "name": ECS_DEFAULT_CONTAINER_NAME,
                        "environment": [
                            {"name": "BAR", "value": "FOO"},
                            {"name": "OVERRIDE", "value": "OLD"},
                        ],
                    }
                ],
            },
        ),
        aws_credentials=aws_credentials,
        env={"FOO": "BAR", "OVERRIDE": "NEW"},
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)

    prefect_container_definition = _get_container(
        task_definition["containerDefinitions"], ECS_DEFAULT_CONTAINER_NAME
    )

    assert prefect_container_definition["environment"] == [
        {"name": "BAR", "value": "FOO"},
        {"name": "OVERRIDE", "value": "OLD"},
    ]

    prefect_container_overrides = _get_container(
        task["overrides"]["containerOverrides"], ECS_DEFAULT_CONTAINER_NAME
    )
    assert prefect_container_overrides.get("environment") == [
        {"name": "FOO", "value": "BAR"},
        {"name": "OVERRIDE", "value": "NEW"},
    ]


@pytest.mark.usefixtures("ecs_mocks")
async def test_user_defined_capacity_provider_strategy(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        capacity_provider_strategy=[
            {"base": 0, "weight": 1, "capacityProvider": "r6i.large"}
        ],
    )
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        # Capture the task run call because moto does not track
        # 'capacityProviderStrategy'
        original_run_task = worker._create_task_run
        mock_run_task = MagicMock(side_effect=original_run_task)
        worker._create_task_run = mock_run_task

        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    assert not task.get("launchType")
    # Instead, it requires a capacity provider strategy but this is not supported
    # by moto and is not present on the task even when provided so we assert on the
    # mock call to ensure it is sent
    assert mock_run_task.call_args[0][1].get("capacityProviderStrategy") == [
        {"base": 0, "weight": 1, "capacityProvider": "r6i.large"},
    ]


@pytest.mark.usefixtures("ecs_mocks")
async def test_user_defined_environment_variables_in_task_run_request_template(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    configuration = await construct_configuration_with_job_template(
        template_overrides=dict(
            task_run_request={
                "overrides": {
                    "containerOverrides": [
                        {
                            "name": ECS_DEFAULT_CONTAINER_NAME,
                            "environment": [
                                {"name": "BAR", "value": "FOO"},
                                {"name": "OVERRIDE", "value": "OLD"},
                                {"name": "UNSET", "value": "GONE"},
                            ],
                        }
                    ],
                },
            },
        ),
        aws_credentials=aws_credentials,
        env={"FOO": "BAR", "OVERRIDE": "NEW", "UNSET": None},
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)

    prefect_container_definition = _get_container(
        task_definition["containerDefinitions"], ECS_DEFAULT_CONTAINER_NAME
    )

    assert (
        prefect_container_definition["environment"] == []
    ), "No environment variables in the task definition"

    prefect_container_overrides = _get_container(
        task["overrides"]["containerOverrides"], ECS_DEFAULT_CONTAINER_NAME
    )
    assert prefect_container_overrides.get("environment") == [
        {"name": "BAR", "value": "FOO"},
        {"name": "FOO", "value": "BAR"},
        {"name": "OVERRIDE", "value": "NEW"},
    ]


@pytest.mark.usefixtures("ecs_mocks")
async def test_user_defined_tags_in_task_run_request_template(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    configuration = await construct_configuration_with_job_template(
        template_overrides=dict(
            task_run_request={
                "tags": [
                    {"key": "BAR", "value": "FOO"},
                    {"key": "OVERRIDE", "value": "OLD"},
                ]
            },
        ),
        aws_credentials=aws_credentials,
        labels={"FOO": "BAR", "OVERRIDE": "NEW"},
    )

    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    async with ECSWorker(work_pool_name="test") as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    assert task.get("tags") == [
        {"key": "BAR", "value": "FOO"},
        {"key": "FOO", "value": "BAR"},
        {"key": "OVERRIDE", "value": "NEW"},
    ]


@pytest.mark.usefixtures("ecs_mocks")
@pytest.mark.parametrize(
    "cluster", [None, "default", "second-cluster", "second-cluster-arn"]
)
async def test_kill_infrastructure(aws_credentials, cluster: str, flow_run):
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    # Kill requires cluster-specificity so we test with variable clusters
    second_cluster_arn = create_test_ecs_cluster(ecs_client, "second-cluster")
    add_ec2_instance_to_ecs_cluster(session, "second-cluster")

    if cluster == "second-cluster-arn":
        # Use the actual arn for this test case
        cluster = second_cluster_arn

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        cluster=cluster,
    )

    with anyio.fail_after(5):
        async with ECSWorker(work_pool_name="test") as worker:
            async with anyio.create_task_group() as tg:
                identifier = await tg.start(worker.run, flow_run, configuration)

                await worker.kill_infrastructure(
                    configuration=configuration, infrastructure_pid=identifier
                )

    _, task_arn = parse_identifier(identifier)
    task = describe_task(ecs_client, task_arn)
    assert task["lastStatus"] == "STOPPED"


@pytest.mark.usefixtures("ecs_mocks")
async def test_kill_infrastructure_with_invalid_identifier(aws_credentials):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
    )

    with pytest.raises(ValueError):
        async with ECSWorker(work_pool_name="test") as worker:
            await worker.kill_infrastructure(configuration, "test")


@pytest.mark.usefixtures("ecs_mocks")
async def test_kill_infrastructure_with_mismatched_cluster(aws_credentials):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        cluster="foo",
    )

    with pytest.raises(
        InfrastructureNotAvailable,
        match=(
            "Cannot stop ECS task: this infrastructure block has access to cluster "
            "'foo' but the task is running in cluster 'bar'."
        ),
    ):
        async with ECSWorker(work_pool_name="test") as worker:
            await worker.kill_infrastructure(configuration, "bar:::task_arn")


@pytest.mark.usefixtures("ecs_mocks")
async def test_kill_infrastructure_with_cluster_that_does_not_exist(aws_credentials):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        cluster="foo",
    )

    with pytest.raises(
        InfrastructureNotFound,
        match="Cannot stop ECS task: the cluster 'foo' could not be found.",
    ):
        async with ECSWorker(work_pool_name="test") as worker:
            await worker.kill_infrastructure(configuration, "foo::task_arn")


@pytest.mark.usefixtures("ecs_mocks")
async def test_kill_infrastructure_with_task_that_does_not_exist(
    aws_credentials, flow_run
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        cluster="default",
    )

    # Run the task so that a task definition is registered in the cluster
    async with ECSWorker(work_pool_name="test") as worker:
        await run_then_stop_task(worker, configuration, flow_run)

        with pytest.raises(
            InfrastructureNotFound,
            match=(
                "Cannot stop ECS task: the task 'foo' could not be found in cluster"
                " 'default'"
            ),
        ):
            await worker.kill_infrastructure(configuration, "default::foo")


@pytest.mark.usefixtures("ecs_mocks")
async def test_kill_infrastructure_with_cluster_that_has_no_tasks(aws_credentials):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        cluster="default",
    )

    with pytest.raises(
        InfrastructureNotFound,
        match="Cannot stop ECS task: the cluster 'default' has no tasks.",
    ):
        async with ECSWorker(work_pool_name="test") as worker:
            await worker.kill_infrastructure(configuration, "default::foo")


@pytest.mark.usefixtures("ecs_mocks")
async def test_kill_infrastructure_with_task_that_is_already_stopped(
    aws_credentials, flow_run
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
        cluster="default",
    )

    async with ECSWorker(work_pool_name="test") as worker:
        # Run and stop the task
        result = await run_then_stop_task(worker, configuration, flow_run)
        _, task_arn = parse_identifier(result.identifier)

        # AWS will happily stop the task "again"
        await worker.kill_infrastructure(configuration, f"default::{task_arn}")


@pytest.mark.usefixtures("ecs_mocks")
async def test_kill_infrastructure_with_grace_period(aws_credentials, caplog, flow_run):
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")

    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
    )

    with anyio.fail_after(5):
        async with anyio.create_task_group() as tg:
            async with ECSWorker(work_pool_name="test") as worker:
                identifier = await tg.start(worker.run, flow_run, configuration)

            await worker.kill_infrastructure(
                configuration, identifier, grace_seconds=60
            )

    # Task stops correctly
    _, task_arn = parse_identifier(identifier)
    task = describe_task(ecs_client, task_arn)
    assert task["lastStatus"] == "STOPPED"

    # Logs warning
    assert "grace period of 60s requested, but AWS does not support" in caplog.text


async def test_retry_on_failed_task_start(
    aws_credentials: AwsCredentials, flow_run, ecs_mocks
):
    run_task_mock = MagicMock(return_value=[])

    configuration = await construct_configuration(
        aws_credentials=aws_credentials, command="echo test"
    )

    inject_moto_patches(
        ecs_mocks,
        {
            "run_task": [run_task_mock],
        },
    )

    with pytest.raises(RuntimeError):
        async with ECSWorker(work_pool_name="test") as worker:
            await run_then_stop_task(worker, configuration, flow_run)

    assert run_task_mock.call_count == 3


@pytest.mark.usefixtures("ecs_mocks")
async def test_worker_uses_cached_boto3_client(aws_credentials: AwsCredentials):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
    )

    _get_client_cached.cache_clear()

    assert _get_client_cached.cache_info().hits == 0, "Initial call count should be 0"

    async with ECSWorker(work_pool_name="test") as worker:
        worker._get_client(configuration, "ecs")
        worker._get_client(configuration, "ecs")
        worker._get_client(configuration, "ecs")

    assert _get_client_cached.cache_info().misses == 1
    assert _get_client_cached.cache_info().hits == 2


async def test_mask_sensitive_env_values():
    task_run_request = {
        "overrides": {
            "containerOverrides": [
                {
                    "environment": [
                        {"name": "PREFECT_API_KEY", "value": "SeNsItiVe VaLuE"},
                        {"name": "PREFECT_API_URL", "value": "NORMAL_VALUE"},
                    ]
                }
            ]
        }
    }

    res = mask_sensitive_env_values(task_run_request, ["PREFECT_API_KEY"], 3, "***")
    assert (
        res["overrides"]["containerOverrides"][0]["environment"][0]["value"] == "SeN***"
    )
    assert (
        res["overrides"]["containerOverrides"][0]["environment"][1]["value"]
        == "NORMAL_VALUE"
    )


@pytest.mark.usefixtures("ecs_mocks")
async def test_get_or_generate_family(
    aws_credentials: AwsCredentials, flow_run: FlowRun
):
    configuration = await construct_configuration(
        aws_credentials=aws_credentials,
    )

    work_pool_name = "test"
    session = aws_credentials.get_boto3_session()
    ecs_client = session.client("ecs")
    family = f"{ECS_DEFAULT_FAMILY}_{work_pool_name}_{flow_run.deployment_id}"

    async with ECSWorker(work_pool_name=work_pool_name) as worker:
        result = await run_then_stop_task(worker, configuration, flow_run)

    assert result.status_code == 0
    _, task_arn = parse_identifier(result.identifier)

    task = describe_task(ecs_client, task_arn)
    task_definition = describe_task_definition(ecs_client, task)
    assert task_definition["family"] == family

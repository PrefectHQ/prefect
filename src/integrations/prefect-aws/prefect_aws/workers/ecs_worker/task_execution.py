"""
Task execution and monitoring for ECS worker.
"""

import json
import logging
import shlex
import time
from copy import deepcopy
from typing import Any, Dict, Generator, Optional, Tuple

from slugify import slugify
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random

from .logging import mask_api_key, stream_available_logs
from .utils import (
    _TAG_REGEX,
    CREATE_TASK_RUN_MAX_DELAY_JITTER_SECONDS,
    CREATE_TASK_RUN_MIN_DELAY_JITTER_SECONDS,
    CREATE_TASK_RUN_MIN_DELAY_SECONDS,
    ECS_DEFAULT_CONTAINER_NAME,
    MAX_CREATE_TASK_RUN_ATTEMPTS,
    _container_name_from_task_definition,
    _get_container,
)

# Internal type alias for ECS clients which are generated dynamically in botocore
_ECSClient = Any


def report_task_run_creation_failure(
    configuration: Any, task_run: dict, exc: Exception
) -> None:
    """
    Wrap common AWS task run creation failures with nicer user-facing messages.
    """
    # AWS generates exception types at runtime so they must be captured a bit
    # differently than normal.
    if "ClusterNotFoundException" in str(exc):
        cluster = task_run.get("cluster", "default")
        raise RuntimeError(
            f"Failed to run ECS task, cluster {cluster!r} not found. "
            "Confirm that the cluster is configured in your region."
        ) from exc
    elif "No Container Instances" in str(exc) and task_run.get("launchType") == "EC2":
        cluster = task_run.get("cluster", "default")
        raise RuntimeError(
            f"Failed to run ECS task, cluster {cluster!r} does not appear to "
            "have any container instances associated with it. Confirm that you "
            "have EC2 container instances available."
        ) from exc
    elif (
        "failed to validate logger args" in str(exc)
        and "AccessDeniedException" in str(exc)
        and configuration.configure_cloudwatch_logs
    ):
        raise RuntimeError(
            "Failed to run ECS task, the attached execution role does not appear"
            " to have sufficient permissions. Ensure that the execution role"
            f" {configuration.execution_role!r} has permissions"
            " logs:CreateLogStream, logs:CreateLogGroup, and logs:PutLogEvents."
        )
    else:
        raise


def wait_for_task_start(
    logger: logging.Logger,
    configuration: Any,
    task_arn: str,
    cluster_arn: str,
    ecs_client: _ECSClient,
    timeout: int,
) -> dict:
    """
    Waits for an ECS task run to reach a RUNNING status.

    If a STOPPED status is reached instead, an exception is raised indicating the
    reason that the task run did not start.
    """
    for task in watch_task_run(
        logger,
        configuration,
        task_arn,
        cluster_arn,
        ecs_client,
        until_status="RUNNING",
        timeout=timeout,
    ):
        # TODO: It is possible that the task has passed _through_ a RUNNING
        #       status during the polling interval. In this case, there is not an
        #       exception to raise.
        if task["lastStatus"] == "STOPPED":
            code = task.get("stopCode")
            reason = task.get("stoppedReason")
            # Generate a dynamic exception type from the AWS name
            raise type(code, (RuntimeError,), {})(reason)

    return task


def wait_for_task_finish(
    logger: logging.Logger,
    configuration: Any,
    task_arn: str,
    cluster_arn: str,
    task_definition: dict,
    ecs_client: _ECSClient,
    logs_client: Optional[Any] = None,
):
    """
    Watch an ECS task until it reaches a STOPPED status.

    If configured, logs from the Prefect container are streamed to stderr.

    Returns a description of the task on completion.
    """
    can_stream_output = False
    container_name = (
        configuration.container_name
        or _container_name_from_task_definition(task_definition)
        or ECS_DEFAULT_CONTAINER_NAME
    )

    if configuration.stream_output:
        container_def = _get_container(
            task_definition["containerDefinitions"], container_name
        )
        if not container_def:
            logger.warning(
                "Prefect container definition not found in "
                "task definition. Output cannot be streamed."
            )
        elif not container_def.get("logConfiguration"):
            logger.warning(
                "Logging configuration not found on task. Output cannot be streamed."
            )
        elif not container_def["logConfiguration"].get("logDriver") == "awslogs":
            logger.warning(
                "Logging configuration uses unsupported "
                " driver {container_def['logConfiguration'].get('logDriver')!r}. "
                "Output cannot be streamed."
            )
        else:
            # Prepare to stream the output
            log_config = container_def["logConfiguration"]["options"]
            can_stream_output = True
            # Track the last log timestamp to prevent double display
            last_log_timestamp: Optional[int] = None
            # Determine the name of the stream as "prefix/container/run-id"
            stream_name = "/".join(
                [
                    log_config["awslogs-stream-prefix"],
                    container_name,
                    task_arn.rsplit("/")[-1],
                ]
            )
            logger.info(f"Streaming output from container {container_name!r}...")

    for task in watch_task_run(
        logger,
        configuration,
        task_arn,
        cluster_arn,
        ecs_client,
        current_status="RUNNING",
    ):
        if configuration.stream_output and can_stream_output and logs_client:
            # On each poll for task run status, also retrieve available logs
            last_log_timestamp = stream_available_logs(
                logger,
                logs_client,
                log_group=log_config["awslogs-group"],
                log_stream=stream_name,
                last_log_timestamp=last_log_timestamp,
            )

    return task


def watch_task_run(
    logger: logging.Logger,
    configuration: Any,
    task_arn: str,
    cluster_arn: str,
    ecs_client: _ECSClient,
    current_status: str = "UNKNOWN",
    until_status: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Generator[None, None, dict]:
    """
    Watches an ECS task run by querying every `poll_interval` seconds. After each
    query, the retrieved task is yielded. This function returns when the task run
    reaches a STOPPED status or the provided `until_status`.

    Emits a log each time the status changes.
    """
    last_status = status = current_status
    t0 = time.time()
    while status != until_status:
        tasks = ecs_client.describe_tasks(
            tasks=[task_arn], cluster=cluster_arn, include=["TAGS"]
        )["tasks"]

        if tasks:
            task = tasks[0]

            status = task["lastStatus"]
            if status != last_status:
                logger.info(f"ECS task status is {status}.")

            yield task

            # No point in continuing if the status is final
            if status == "STOPPED":
                break

            last_status = status

        else:
            # Intermittently, the task will not be described. We wat to respect the
            # watch timeout though.
            logger.debug("Task not found.")

        elapsed_time = time.time() - t0
        if timeout is not None and elapsed_time > timeout:
            raise RuntimeError(
                f"Timed out after {elapsed_time}s while watching task for status "
                f"{until_status or 'STOPPED'}."
            )
        time.sleep(configuration.task_watch_poll_interval)


def prepare_task_run_request(
    configuration: Any,
    task_definition: dict,
    task_definition_arn: str,
) -> dict:
    """
    Prepare a task run request payload.
    """
    task_run_request = deepcopy(configuration.task_run_request)

    task_run_request.setdefault("taskDefinition", task_definition_arn)

    assert task_run_request["taskDefinition"] == task_definition_arn, (
        f"Task definition ARN mismatch: {task_run_request['taskDefinition']!r} "
        f"!= {task_definition_arn!r}"
    )
    capacityProviderStrategy = task_run_request.get("capacityProviderStrategy")

    if capacityProviderStrategy:
        # Should not be provided at all if capacityProviderStrategy is set, see https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_RunTask.html#ECS-RunTask-request-capacityProviderStrategy  # noqa
        logger = logging.getLogger(__name__)
        logger.warning(
            "Found capacityProviderStrategy. Removing launchType from task run request."
        )
        task_run_request.pop("launchType", None)

    elif task_run_request.get("launchType") == "FARGATE_SPOT":
        # Should not be provided at all for FARGATE SPOT
        task_run_request.pop("launchType", None)

        # A capacity provider strategy is required for FARGATE SPOT
        task_run_request["capacityProviderStrategy"] = [
            {"capacityProvider": "FARGATE_SPOT", "weight": 1}
        ]
    overrides = task_run_request.get("overrides", {})
    container_overrides = overrides.get("containerOverrides", [])

    # Ensure the container name is set if not provided at template time

    container_name = (
        configuration.container_name
        or _container_name_from_task_definition(task_definition)
        or ECS_DEFAULT_CONTAINER_NAME
    )

    if container_overrides and not container_overrides[0].get("name"):
        container_overrides[0]["name"] = container_name

    # Ensure configuration command is respected post-templating

    orchestration_container = _get_container(container_overrides, container_name)

    if orchestration_container:
        # Override the command if given on the configuration
        if configuration.command:
            orchestration_container["command"] = configuration.command

    # Clean up templated variable formatting

    for container in container_overrides:
        if isinstance(container.get("command"), str):
            container["command"] = shlex.split(container["command"])
        if isinstance(container.get("environment"), dict):
            container["environment"] = [
                {"name": k, "value": v} for k, v in container["environment"].items()
            ]

        # Remove null values — they're not allowed by AWS
        container["environment"] = [
            item
            for item in container.get("environment", [])
            if item["value"] is not None
        ]

    if isinstance(task_run_request.get("tags"), dict):
        task_run_request["tags"] = [
            {"key": k, "value": v} for k, v in task_run_request["tags"].items()
        ]

    if overrides.get("cpu"):
        overrides["cpu"] = str(overrides["cpu"])

    if overrides.get("memory"):
        overrides["memory"] = str(overrides["memory"])

    # Ensure configuration tags and env are respected post-templating

    tags = [
        item
        for item in task_run_request.get("tags", [])
        if item["key"] not in configuration.labels.keys()
    ] + [
        {"key": k, "value": v} for k, v in configuration.labels.items() if v is not None
    ]

    # Slugify tags keys and values
    tags = [
        {
            "key": slugify(
                item["key"],
                regex_pattern=_TAG_REGEX,
                allow_unicode=True,
                lowercase=False,
            ),
            "value": slugify(
                item["value"],
                regex_pattern=_TAG_REGEX,
                allow_unicode=True,
                lowercase=False,
            ),
        }
        for item in tags
    ]

    if tags:
        task_run_request["tags"] = tags

    if orchestration_container:
        environment = [
            item
            for item in orchestration_container.get("environment", [])
            if item["name"] not in configuration.env.keys()
        ] + [
            {"name": k, "value": v}
            for k, v in configuration.env.items()
            if v is not None
        ]
        if environment:
            orchestration_container["environment"] = environment

    # Remove empty container overrides

    overrides["containerOverrides"] = [v for v in container_overrides if v]

    return task_run_request


@retry(
    stop=stop_after_attempt(MAX_CREATE_TASK_RUN_ATTEMPTS),
    wait=wait_fixed(CREATE_TASK_RUN_MIN_DELAY_SECONDS)
    + wait_random(
        CREATE_TASK_RUN_MIN_DELAY_JITTER_SECONDS,
        CREATE_TASK_RUN_MAX_DELAY_JITTER_SECONDS,
    ),
    reraise=True,
)
def create_task_run(ecs_client: _ECSClient, task_run_request: dict) -> str:
    """
    Create a run of a task definition.

    Returns the task run ARN.
    """
    task = ecs_client.run_task(**task_run_request)
    if task["failures"]:
        raise RuntimeError(f"Failed to run ECS task: {task['failures'][0]['reason']}")
    elif not task["tasks"]:
        raise RuntimeError(
            "Failed to run ECS task: no tasks or failures were returned."
        )
    return task["tasks"][0]


def report_container_status_code(
    logger: logging.Logger, name: str, status_code: Optional[int]
) -> None:
    """
    Display a log for the given container status code.
    """
    if status_code is None:
        logger.error(
            f"Task exited without reporting an exit status for container {name!r}."
        )
    elif status_code == 0:
        logger.info(f"Container {name!r} exited successfully.")
    else:
        logger.warning(
            f"Container {name!r} exited with non-zero exit code {status_code}."
        )


def create_task_and_wait_for_start(
    logger: logging.Logger,
    ecs_client: _ECSClient,
    configuration: Any,
    flow_run: Any,
    task_definition_cache: Dict[Any, str],
    get_or_register_task_definition_func: Any,
    prepare_task_definition_func: Any,
    retrieve_task_definition_func: Any,
    validate_task_definition_func: Any,
    prepare_task_run_request_func: Any,
    load_network_configuration_func: Any,
    custom_network_configuration_func: Any,
    get_client_func: Any,
    work_pool: Any,
    create_task_run_func: Any = None,
) -> Tuple[str, str, dict, bool]:
    """
    Register the task definition, create the task run, and wait for it to start.

    Returns a tuple of
    - The task ARN
    - The task's cluster ARN
    - The task definition
    - A bool indicating if the task definition is newly registered
    """
    task_definition_arn = configuration.task_run_request.get("taskDefinition")
    new_task_definition_registered = False

    if not task_definition_arn:
        task_definition = prepare_task_definition_func(
            configuration, region=ecs_client.meta.region_name, flow_run=flow_run
        )

        cached_task_definition_arn = (
            task_definition_cache.get(flow_run.deployment_id)
            if flow_run.deployment_id
            else task_definition_cache.get(flow_run.flow_id)
        )

        (
            task_definition_arn,
            new_task_definition_registered,
        ) = get_or_register_task_definition_func(
            logger,
            ecs_client,
            configuration,
            flow_run,
            task_definition,
            cached_task_definition_arn,
        )
    else:
        task_definition = retrieve_task_definition_func(
            logger, ecs_client, task_definition_arn
        )
        if configuration.task_definition:
            from prefect.utilities.templating import find_placeholders

            template_with_placeholders = work_pool.base_job_template[
                "job_configuration"
            ]["task_definition"]
            placeholders = [
                placeholder.name
                for placeholder in find_placeholders(template_with_placeholders)
            ]

            logger.warning(
                "Skipping task definition construction since a task definition"
                " ARN is provided."
            )

            if placeholders:
                logger.warning(
                    "The following job variable references"
                    " in the task definition template will be ignored: "
                    + ", ".join(placeholders)
                )

    validate_task_definition_func(task_definition, configuration)

    if flow_run.deployment_id:
        task_definition_cache[flow_run.deployment_id] = task_definition_arn
    else:
        task_definition_cache[flow_run.flow_id] = task_definition_arn

    logger.info(f"Using ECS task definition {task_definition_arn!r}...")
    logger.debug(
        f"Task definition {json.dumps(task_definition, indent=2, default=str)}"
    )

    # Prepare task run request with network configuration if needed
    task_run_request = prepare_task_run_request_func(
        configuration,
        task_definition,
        task_definition_arn,
    )

    # Handle network configuration
    if (
        task_definition.get("networkMode") == "awsvpc"
        and not task_run_request.get("networkConfiguration")
        and not configuration.network_configuration
    ):
        ec2_client = get_client_func(configuration, "ec2")
        task_run_request["networkConfiguration"] = load_network_configuration_func(
            configuration.vpc_id, configuration, ec2_client
        )

    # Use networkConfiguration if supplied by user
    if (
        task_definition.get("networkMode") == "awsvpc"
        and configuration.network_configuration
        and configuration.vpc_id
    ):
        ec2_client = get_client_func(configuration, "ec2")
        task_run_request["networkConfiguration"] = custom_network_configuration_func(
            configuration.vpc_id,
            configuration.network_configuration,
            configuration,
            ec2_client,
        )

    logger.info("Creating ECS task run...")
    logger.debug(
        "Task run request"
        f"{json.dumps(mask_api_key(task_run_request), indent=2, default=str)}"
    )

    try:
        # Use the provided create_task_run function if available, otherwise use the default
        if create_task_run_func:
            task = create_task_run_func(ecs_client, task_run_request)
        else:
            task = create_task_run(ecs_client, task_run_request)
        task_arn = task["taskArn"]
        cluster_arn = task["clusterArn"]
    except Exception as exc:
        report_task_run_creation_failure(configuration, task_run_request, exc)
        raise

    logger.info("Waiting for ECS task run to start...")
    wait_for_task_start(
        logger,
        configuration,
        task_arn,
        cluster_arn,
        ecs_client,
        timeout=configuration.task_start_timeout_seconds,
    )

    return task_arn, cluster_arn, task_definition, new_task_definition_registered


def watch_task_and_get_exit_code(
    logger: logging.Logger,
    configuration: Any,
    task_arn: str,
    cluster_arn: str,
    task_definition: dict,
    deregister_task_definition: bool,
    ecs_client: _ECSClient,
    logs_client: Optional[Any] = None,
) -> Optional[int]:
    """
    Wait for the task run to complete and retrieve the exit code of the Prefect
    container.
    """

    # Wait for completion and stream logs
    task = wait_for_task_finish(
        logger,
        configuration,
        task_arn,
        cluster_arn,
        task_definition,
        ecs_client,
        logs_client,
    )

    if deregister_task_definition:
        ecs_client.deregister_task_definition(taskDefinition=task["taskDefinitionArn"])

    container_name = (
        configuration.container_name
        or _container_name_from_task_definition(task_definition)
        or ECS_DEFAULT_CONTAINER_NAME
    )

    # Check the status code of the Prefect container
    container = _get_container(task["containers"], container_name)
    assert container is not None, (
        f"'{container_name}' container missing from task: {task}"
    )
    status_code = container.get("exitCode")
    report_container_status_code(logger, container_name, status_code)

    return status_code

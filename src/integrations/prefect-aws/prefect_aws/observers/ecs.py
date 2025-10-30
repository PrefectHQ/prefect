from __future__ import annotations

import asyncio
import datetime
import enum
import json
import logging
import uuid
from collections import deque
from contextlib import AsyncExitStack
from datetime import timedelta
from functools import partial
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Literal,
    NamedTuple,
    Protocol,
    TypedDict,
    Union,
)

import aiobotocore.session
import anyio
from botocore.exceptions import ClientError
from cachetools import LRUCache
from prefect_aws.settings import EcsObserverSettings
from slugify import slugify

import prefect
from prefect.events.clients import get_events_client
from prefect.events.schemas.events import Event, RelatedResource, Resource
from prefect.exceptions import ObjectNotFound
from prefect.states import Crashed
from prefect.utilities.engine import propose_state

if TYPE_CHECKING:
    from mypy_boto3_sqs.type_defs import MessageTypeDef
    from types_aiobotocore_ecs import ECSClient


logger: logging.Logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_last_event_cache: LRUCache[uuid.UUID, Event] = LRUCache(maxsize=1000)

_ECS_DEFAULT_CONTAINER_NAME = "prefect"

_ECS_EVENT_DETAIL_MAP: dict[
    str, Literal["task", "container-instance", "deployment"]
] = {
    "ECS Task State Change": "task",
    "ECS Container Instance State Change": "container-instance",
    "ECS Deployment": "deployment",
}

EcsTaskLastStatus = Literal[
    "PROVISIONING",
    "PENDING",
    "ACTIVATING",
    "RUNNING",
    "DEACTIVATING",
    "STOPPING",
    "DEPROVISIONING",
    "STOPPED",
    "DELETED",
]


class FilterCase(enum.Enum):
    PRESENT = enum.auto()
    ABSENT = enum.auto()


class EcsEventHandler(Protocol):
    __name__: str

    def __call__(
        self,
        event: dict[str, Any],
        tags: dict[str, str],
    ) -> None: ...


class AsyncEcsEventHandler(Protocol):
    __name__: str

    async def __call__(
        self,
        event: dict[str, Any],
        tags: dict[str, str],
    ) -> None: ...


class EventHandlerFilters(TypedDict):
    tags: TagsFilter
    last_status: LastStatusFilter


class TagsFilter:
    def __init__(self, **tags: str | FilterCase):
        self.tags = tags

    def is_match(self, tags: dict[str, str]) -> bool:
        return not self.tags or all(
            tag_value == FilterCase.PRESENT
            and tag_name in tags
            or tag_value == FilterCase.ABSENT
            and tag_name not in tags
            or tag_value == tags.get(tag_name)
            for tag_name, tag_value in self.tags.items()
        )


class LastStatusFilter:
    def __init__(self, *statuses: EcsTaskLastStatus):
        self.statuses = statuses

    def is_match(self, last_status: EcsTaskLastStatus) -> bool:
        return not self.statuses or last_status in self.statuses


HandlerWithFilters = NamedTuple(
    "HandlerWithFilters",
    [
        ("handler", Union[EcsEventHandler, AsyncEcsEventHandler]),
        ("filters", EventHandlerFilters),
    ],
)


class EcsTaskTagsReader:
    def __init__(self):
        self.ecs_client: "ECSClient | None" = None
        self._cache: LRUCache[str, dict[str, str]] = LRUCache(maxsize=100)

    async def read_tags(self, cluster_arn: str, task_arn: str) -> dict[str, str]:
        if not self.ecs_client:
            raise RuntimeError("ECS client not initialized for EcsTaskTagsReader")

        if task_arn in self._cache:
            return self._cache[task_arn]

        try:
            response = await self.ecs_client.describe_tasks(
                cluster=cluster_arn,
                tasks=[task_arn],
                include=["TAGS"],
            )
        except Exception as e:
            print(f"Error reading tags for task {task_arn}: {e}")
            return {}

        if not (tasks := response.get("tasks", [])):
            return {}

        if len(tasks) == 0:
            return {}

        tags = {
            tag["key"]: tag["value"]
            for tag in tasks[0].get("tags", [])
            if "key" in tag and "value" in tag
        }
        self._cache[task_arn] = tags
        return tags

    async def __aenter__(self):
        self.ecs_client = (
            await aiobotocore.session.get_session().create_client("ecs").__aenter__()
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.ecs_client:
            await self.ecs_client.__aexit__(*args)


SQS_MEMORY = 10
SQS_CONSECUTIVE_FAILURES = 3
SQS_BACKOFF = 1
SQS_MAX_BACKOFF_ATTEMPTS = 5

OBSERVER_RESTART_BASE_DELAY = 30
OBSERVER_MAX_RESTART_ATTEMPTS = 5


class SqsSubscriber:
    def __init__(self, queue_name: str, queue_region: str | None = None):
        self.queue_name = queue_name
        self.queue_region = queue_region

    async def stream_messages(
        self,
    ) -> AsyncGenerator["MessageTypeDef", None]:
        session = aiobotocore.session.get_session()
        async with session.create_client(
            "sqs", region_name=self.queue_region
        ) as sqs_client:
            try:
                queue_url = (await sqs_client.get_queue_url(QueueName=self.queue_name))[
                    "QueueUrl"
                ]
            except ClientError as e:
                if (
                    e.response.get("Error", {}).get("Code")
                    == "AWS.SimpleQueueService.NonExistentQueue"
                ):
                    logger.warning(
                        (
                            "SQS queue '%s' does not exist in region '%s'. "
                            "This worker will continue to submit ECS tasks, but event replication "
                            "and crash detection will not work. To enable ECS event replication and "
                            "crash detection, deploy an SQS queue using "
                            "`prefect-aws ecs-worker deploy-events` and configure the "
                            "PREFECT_INTEGRATIONS_AWS_ECS_OBSERVER_SQS_QUEUE_NAME environment "
                            "variable on your worker to point to the deployed queue."
                        ),
                        self.queue_name,
                        self.queue_region or "default",
                    )
                    return
                raise

            track_record: deque[bool] = deque(
                [True] * SQS_CONSECUTIVE_FAILURES, maxlen=SQS_CONSECUTIVE_FAILURES
            )
            failures: deque[tuple[Exception, TracebackType | None]] = deque(
                maxlen=SQS_MEMORY
            )
            backoff_count = 0

            while True:
                try:
                    messages = await sqs_client.receive_message(
                        QueueUrl=queue_url,
                        MaxNumberOfMessages=10,
                        WaitTimeSeconds=20,
                    )
                    for message in messages.get("Messages", []):
                        if not (receipt_handle := message.get("ReceiptHandle")):
                            continue

                        yield message

                        await sqs_client.delete_message(
                            QueueUrl=queue_url,
                            ReceiptHandle=receipt_handle,
                        )

                    backoff_count = 0
                except Exception as e:
                    track_record.append(False)
                    failures.append((e, e.__traceback__))
                    logger.debug("Failed to receive messages from SQS", exc_info=e)

                if not any(track_record):
                    backoff_count += 1

                    if backoff_count > SQS_MAX_BACKOFF_ATTEMPTS:
                        logger.error(
                            "SQS polling exceeded maximum backoff attempts (%s). "
                            "Last %s errors: %s",
                            SQS_MAX_BACKOFF_ATTEMPTS,
                            len(failures),
                            [str(e) for e, _ in failures],
                        )
                        raise RuntimeError(
                            f"SQS polling failed after {SQS_MAX_BACKOFF_ATTEMPTS} backoff attempts"
                        )

                    track_record.extend([True] * SQS_CONSECUTIVE_FAILURES)
                    failures.clear()
                    backoff_seconds = SQS_BACKOFF * 2**backoff_count
                    logger.debug(
                        "Backing off due to consecutive errors, using increased interval of %s seconds.",
                        backoff_seconds,
                    )
                    await asyncio.sleep(backoff_seconds)


class EcsObserver:
    def __init__(
        self,
        settings: EcsObserverSettings | None = None,
        sqs_subscriber: SqsSubscriber | None = None,
        ecs_tags_reader: EcsTaskTagsReader | None = None,
    ):
        self.settings = settings or EcsObserverSettings()

        self.sqs_subscriber = sqs_subscriber or SqsSubscriber(
            queue_name=self.settings.sqs.queue_name,
            queue_region=self.settings.sqs.queue_region,
        )
        self.ecs_tags_reader = ecs_tags_reader or EcsTaskTagsReader()
        self.event_handlers: dict[
            Literal["task", "container-instance", "deployment"],
            list[HandlerWithFilters],
        ] = {
            "task": [],
            "container-instance": [],
            "deployment": [],
        }

    async def run(self):
        async with AsyncExitStack() as stack:
            task_group = await stack.enter_async_context(anyio.create_task_group())
            await stack.enter_async_context(self.ecs_tags_reader)

            async for message in self.sqs_subscriber.stream_messages():
                if not (body := message.get("Body")):
                    logger.debug(
                        "No body in message. Skipping.",
                        extra={"sqs_message": message},
                    )
                    continue

                body = json.loads(body)
                if (task_arn := body.get("detail", {}).get("taskArn")) and (
                    cluster_arn := body.get("detail", {}).get("clusterArn")
                ):
                    tags = await self.ecs_tags_reader.read_tags(
                        cluster_arn=cluster_arn,
                        task_arn=task_arn,
                    )
                else:
                    tags = {}

                if not (detail_type := body.get("detail-type")):
                    logger.debug(
                        "No event type in message. Skipping.",
                        extra={"sqs_message": message},
                    )
                    continue

                if detail_type not in _ECS_EVENT_DETAIL_MAP:
                    logger.debug("Unknown event type: %s. Skipping.", detail_type)
                    continue

                last_status = body.get("detail", {}).get("lastStatus")
                event_type = _ECS_EVENT_DETAIL_MAP[detail_type]
                for handler, filters in self.event_handlers[event_type]:
                    if filters["tags"].is_match(tags) and filters[
                        "last_status"
                    ].is_match(last_status):
                        logger.debug(
                            "Running handler %s for message",
                            handler.__name__,
                            extra={"sqs_message": message},
                        )
                        if asyncio.iscoroutinefunction(handler):
                            task_group.start_soon(handler, body, tags)
                        else:
                            task_group.start_soon(
                                asyncio.to_thread, partial(handler, body, tags)
                            )

    def on_event(
        self,
        event_type: Literal["task", "container-instance", "deployment"],
        /,
        tags: dict[str, str | FilterCase] | None = None,
        statuses: list[EcsTaskLastStatus] | None = None,
    ):
        def decorator(fn: EcsEventHandler | AsyncEcsEventHandler):
            self.event_handlers[event_type].append(
                HandlerWithFilters(
                    handler=fn,
                    filters={
                        "tags": TagsFilter(**(tags or {})),
                        "last_status": LastStatusFilter(*(statuses or [])),
                    },
                )
            )
            return fn

        return decorator


def _related_resources_from_tags(tags: dict[str, str]) -> list[RelatedResource]:
    """Convert labels to related resources"""
    related: list[RelatedResource] = []
    if flow_run_id := tags.get("prefect.io/flow-run-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.flow-run.{flow_run_id}",
                    "prefect.resource.role": "flow-run",
                    "prefect.resource.name": tags.get("prefect.io/flow-run-name"),
                }
            )
        )
    if deployment_id := tags.get("prefect.io/deployment-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.deployment.{deployment_id}",
                    "prefect.resource.role": "deployment",
                    "prefect.resource.name": tags.get("prefect.io/deployment-name"),
                }
            )
        )
    if flow_id := tags.get("prefect.io/flow-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.flow.{flow_id}",
                    "prefect.resource.role": "flow",
                    "prefect.resource.name": tags.get("prefect.io/flow-name"),
                }
            )
        )
    if work_pool_id := tags.get("prefect.io/work-pool-id"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.work-pool.{work_pool_id}",
                    "prefect.resource.role": "work-pool",
                    "prefect.resource.name": tags.get("prefect.io/work-pool-name"),
                }
            )
        )
    if worker_name := tags.get("prefect.io/worker-name"):
        related.append(
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": f"prefect.worker.ecs.{slugify(worker_name)}",
                    "prefect.resource.role": "worker",
                    "prefect.resource.name": worker_name,
                    "prefect.worker-type": "ecs",
                    "prefect.version": prefect.__version__,
                }
            )
        )
    return related


ecs_observer = EcsObserver()


@ecs_observer.on_event("task", tags={"prefect.io/flow-run-id": FilterCase.PRESENT})
async def replicate_ecs_event(event: dict[str, Any], tags: dict[str, str]):
    handler_logger = logger.getChild("replicate_ecs_event")
    event_id = event.get("id")
    if not event_id:
        handler_logger.debug("No event ID in event. Skipping.")
        return

    task_arn = event.get("detail", {}).get("taskArn")
    if not task_arn:
        handler_logger.debug("No task ARN in event. Skipping.")
        return

    last_status = event.get("detail", {}).get("lastStatus")
    if not last_status:
        handler_logger.debug("No last status in event. Skipping.")
        return

    handler_logger.debug(
        "Replicating ECS task %s event %s",
        last_status,
        event_id,
        extra={"event": event},
    )
    async with get_events_client() as events_client:
        event_id = uuid.UUID(event_id)

        task_id = task_arn.split("/")[-1]

        resource = {
            "prefect.resource.id": f"prefect.ecs.task.{task_id}",
            "ecs.taskArn": task_arn,
        }
        if cluster_arn := event.get("detail", {}).get("clusterArn"):
            resource["ecs.clusterArn"] = cluster_arn
        if task_definition_arn := event.get("detail", {}).get("taskDefinitionArn"):
            resource["ecs.taskDefinitionArn"] = task_definition_arn

        prefect_event = Event(
            event=f"prefect.ecs.task.{last_status.lower()}",
            resource=Resource.model_validate(resource),
            id=event_id,
            related=_related_resources_from_tags(tags),
        )
        if ecs_event_time := event.get("time"):
            prefect_event.occurred = datetime.datetime.fromisoformat(
                ecs_event_time.replace("Z", "+00:00")
            )

        if (prev_event := _last_event_cache.get(event_id)) is not None:
            if (
                -timedelta(minutes=5)
                < (prefect_event.occurred - prev_event.occurred)
                < timedelta(minutes=5)
            ):
                prefect_event.follows = prev_event.id

        try:
            await events_client.emit(event=prefect_event)
            handler_logger.debug(
                "Replicated ECS task %s event %s",
                last_status,
                event_id,
                extra={"event": prefect_event},
            )
            _last_event_cache[event_id] = prefect_event
        except Exception:
            handler_logger.exception("Error emitting event %s", event_id)


@ecs_observer.on_event(
    "task", tags={"prefect.io/flow-run-id": FilterCase.PRESENT}, statuses=["STOPPED"]
)
async def mark_runs_as_crashed(event: dict[str, Any], tags: dict[str, str]):
    handler_logger = logger.getChild("mark_runs_as_crashed")

    task_arn = event.get("detail", {}).get("taskArn")
    if not task_arn:
        handler_logger.debug("No task ARN in event. Skipping.")
        return

    flow_run_id = tags.get("prefect.io/flow-run-id")

    async with prefect.get_client() as orchestration_client:
        try:
            flow_run = await orchestration_client.read_flow_run(
                flow_run_id=uuid.UUID(flow_run_id)
            )
        except ObjectNotFound:
            logger.debug(f"Flow run {flow_run_id} not found, skipping")
            return

        assert flow_run.state is not None, "Expected flow run state to be set"

        # Exit early for final or scheduled states
        if flow_run.state.is_final() or flow_run.state.is_scheduled():
            logger.debug(
                f"Flow run {flow_run_id} is in final or scheduled state, skipping"
            )
            return

        containers = event.get("detail", {}).get("containers", [])

        containers_with_non_zero_exit_codes = [
            container
            for container in containers
            if container.get("exitCode") is None or container.get("exitCode") != 0
        ]

        if any(containers_with_non_zero_exit_codes):
            container_identifiers = [
                c.get("name") or c.get("containerArn") for c in containers
            ]
            handler_logger.info(
                "The following containers stopped with a non-zero exit code: %s. Marking flow run %s as crashed",
                container_identifiers,
                flow_run_id,
            )
            await propose_state(
                client=orchestration_client,
                state=Crashed(
                    message=f"The following containers stopped with a non-zero exit code: {container_identifiers}"
                ),
                flow_run_id=uuid.UUID(flow_run_id),
            )


@ecs_observer.on_event(
    "task",
    tags={"prefect.io/degregister-task-definition": "true"},
    statuses=["STOPPED"],
)
async def deregister_task_definition(event: dict[str, Any], tags: dict[str, str]):
    handler_logger = logger.getChild("deregister_task_definition")

    if not (task_definition_arn := event.get("detail", {}).get("taskDefinitionArn")):
        handler_logger.debug("No task definition ARN in event. Skipping.")
        return

    async with aiobotocore.session.get_session().create_client("ecs") as ecs_client:
        await ecs_client.deregister_task_definition(taskDefinition=task_definition_arn)
        handler_logger.info(
            "Task definition %s successfully deregistered", task_definition_arn
        )


_observer_task: asyncio.Task[None] | None = None
_observer_restart_count: int = 0
_observer_restart_task: asyncio.Task[None] | None = None


async def _restart_observer_after_delay(delay: int):
    """Restart the observer after a delay."""
    global _observer_task, _observer_restart_count, _observer_restart_task

    logger.info(
        "ECS observer will restart in %s seconds (attempt %s of %s)",
        delay,
        _observer_restart_count,
        OBSERVER_MAX_RESTART_ATTEMPTS,
    )
    await asyncio.sleep(delay)

    # Start the observer again
    _observer_task = asyncio.create_task(ecs_observer.run())
    _observer_task.add_done_callback(_observer_task_done)
    _observer_restart_task = None
    logger.info("ECS observer restarted")


def _observer_task_done(task: asyncio.Task[None]):
    global _observer_restart_count, _observer_restart_task

    if task.cancelled():
        logger.debug("ECS observer task cancelled")
        _observer_restart_count = 0
    elif task.exception():
        logger.error("ECS observer task crashed", exc_info=task.exception())
        _observer_restart_count += 1

        if _observer_restart_count <= OBSERVER_MAX_RESTART_ATTEMPTS:
            # Schedule a restart with exponential backoff
            delay = OBSERVER_RESTART_BASE_DELAY * (2 ** (_observer_restart_count - 1))
            try:
                loop = asyncio.get_event_loop()
                _observer_restart_task = loop.create_task(
                    _restart_observer_after_delay(delay)
                )
            except RuntimeError:
                logger.error(
                    "Cannot schedule observer restart: no event loop available"
                )
        else:
            logger.error(
                "ECS observer has crashed %s times, giving up on automatic restarts",
                _observer_restart_count,
            )
    else:
        logger.debug("ECS observer task completed")
        _observer_restart_count = 0


async def start_observer():
    global _observer_task, _observer_restart_count, _observer_restart_task
    if _observer_task:
        return

    # Cancel any pending restart task
    if _observer_restart_task and not _observer_restart_task.done():
        _observer_restart_task.cancel()
        try:
            await _observer_restart_task
        except asyncio.CancelledError:
            pass
        _observer_restart_task = None

    _observer_restart_count = 0
    _observer_task = asyncio.create_task(ecs_observer.run())
    _observer_task.add_done_callback(_observer_task_done)
    logger.debug("ECS observer started")


async def stop_observer():
    global _observer_task, _observer_restart_count, _observer_restart_task

    # Cancel any pending restart task
    if _observer_restart_task and not _observer_restart_task.done():
        _observer_restart_task.cancel()
        try:
            await _observer_restart_task
        except asyncio.CancelledError:
            pass
        _observer_restart_task = None

    if not _observer_task:
        return

    task = _observer_task
    _observer_task = None
    _observer_restart_count = 0

    task.cancel()
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        pass

    logger.debug("ECS observer stopped")

from __future__ import annotations

import asyncio
import datetime
import enum
import json
import logging
import uuid
from contextlib import AsyncExitStack
from datetime import timedelta
from functools import partial
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

if TYPE_CHECKING:
    from mypy_boto3_sqs.type_defs import MessageTypeDef
    from types_aiobotocore_ecs import ECSClient


logger: logging.Logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_last_event_cache: LRUCache[uuid.UUID, Event] = LRUCache(maxsize=1000)

_ECS_EVENT_DETAIL_MAP: dict[
    str, Literal["task", "container-instance", "deployment"]
] = {
    "ECS Task State Change": "task",
    "ECS Container Instance State Change": "container-instance",
    "ECS Deployment": "deployment",
}


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

        tags = {
            tag["key"]: tag["value"]
            for tag in response.get("tasks", [{}])[0].get("tags", [])
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
                        f"SQS queue '{self.queue_name}' does not exist in region '{self.queue_region or 'default'}'. "
                        "To enable ECS event replication, deploy an SQS queue using the prefect-aws CLI and "
                        "configure the PREFECT_INTEGRATIONS_AWS_ECS_OBSERVER_SQS_QUEUE_NAME environment variable "
                        "on your worker to point to the deployed queue."
                    )
                    return
                raise

            while True:
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

                event_type = _ECS_EVENT_DETAIL_MAP[detail_type]
                for handler, filters in self.event_handlers[event_type]:
                    if filters["tags"].is_match(tags):
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
    ):
        def decorator(fn: EcsEventHandler | AsyncEcsEventHandler):
            self.event_handlers[event_type].append(
                HandlerWithFilters(
                    handler=fn,
                    filters={"tags": TagsFilter(**(tags or {}))},
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
                    "prefect.worker-type": "kubernetes",
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


_observer_task: asyncio.Task[None] | None = None


async def start_observer():
    global _observer_task
    if _observer_task:
        return

    _observer_task = asyncio.create_task(ecs_observer.run())
    logger.debug("ECS observer started")


async def stop_observer():
    global _observer_task
    if not _observer_task:
        return

    task = _observer_task
    _observer_task = None

    task.cancel()
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        pass

    logger.debug("ECS observer stopped")

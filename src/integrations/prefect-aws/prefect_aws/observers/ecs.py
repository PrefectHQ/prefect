from __future__ import annotations

import enum
import json
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Literal,
    NamedTuple,
    Protocol,
    TypedDict,
)

import aiobotocore.session
from cachetools import LRUCache
from mypy_boto3_sqs.type_defs import MessageTypeDef
from prefect_aws.settings import EcsObserverSettings

if TYPE_CHECKING:
    from types_aiobotocore_ecs import ECSClient


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
    def __call__(
        self,
        event: dict[str, Any],
        tags: dict[str, str],
    ) -> None: ...


class EventHandlerFilters(TypedDict):
    tags: dict[str, str | FilterCase] | None


HandlerWithFilters = NamedTuple(
    "HandlerWithFilters",
    [("handler", EcsEventHandler), ("filters", EventHandlerFilters)],
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
        await self.ecs_client.__aexit__(*args)


class SqsSubscriber:
    def __init__(self, queue_name: str, queue_region: str | None = None):
        self.queue_name = queue_name
        self.queue_region = queue_region

    async def stream_messages(
        self,
    ) -> AsyncGenerator[MessageTypeDef, None]:
        session = aiobotocore.session.get_session()
        async with session.create_client(
            "sqs", region_name=self.queue_region
        ) as sqs_client:
            queue_url = (await sqs_client.get_queue_url(QueueName=self.queue_name))[
                "QueueUrl"
            ]
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
        async with self.ecs_tags_reader:
            async for message in self.sqs_subscriber.stream_messages():
                if not (body := message.get("Body")):
                    print("No body in message. Skipping.")
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
                    print("No event type in message. Skipping.")
                    continue

                if detail_type not in _ECS_EVENT_DETAIL_MAP:
                    print(f"Unknown event type: {detail_type}. Skipping.")
                    continue

                event_type = _ECS_EVENT_DETAIL_MAP[detail_type]
                for handler in self.event_handlers[event_type]:
                    if (tag_filters := handler.filters.get("tags")) is None:
                        handler.handler(body, tags)
                        continue

                    if all(
                        tag_value == FilterCase.PRESENT
                        and tag_name in tags
                        or tag_value == FilterCase.ABSENT
                        and tag_name not in tags
                        or tag_value == tags.get(tag_name)
                        for tag_name, tag_value in tag_filters.items()
                    ):
                        handler.handler(body, tags)

    def on_event(
        self,
        event_type: Literal["task", "container-instance", "deployment"],
        /,
        tags: dict[str, str | FilterCase] | None = None,
    ):
        def decorator(fn: EcsEventHandler):
            self.event_handlers[event_type].append(
                HandlerWithFilters(handler=fn, filters={"tags": tags})
            )
            return fn

        return decorator

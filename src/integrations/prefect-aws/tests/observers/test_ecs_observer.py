from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from cachetools import LRUCache
from prefect_aws.observers.ecs import (
    EcsObserver,
    EcsTaskTagsReader,
    FilterCase,
    ObserverInfrastructureManager,
    SqsSubscriber,
    TagsFilter,
    _related_resources_from_tags,
    replicate_ecs_event,
    start_observer,
    stop_observer,
)
from prefect_aws.settings import EcsObserverSettings, EcsObserverSqsSettings

from prefect.events.schemas.events import Event, Resource


class TestEcsObserverSettings:
    def test_default_values(self):
        settings = EcsObserverSettings()
        assert settings.enabled is True
        assert settings.automatic_setup is False
        assert isinstance(settings.sqs, EcsObserverSqsSettings)

    def test_custom_values(self):
        settings = EcsObserverSettings(
            enabled=False,
            automatic_setup=True,
        )
        assert settings.enabled is False
        assert settings.automatic_setup is True

    def test_sqs_settings_defaults(self):
        sqs_settings = EcsObserverSqsSettings()
        assert sqs_settings.queue_name == "prefect-ecs-tasks-events"
        assert sqs_settings.queue_region is None


class TestTagsFilter:
    def test_is_match_with_no_filter_tags(self):
        filter = TagsFilter()
        assert filter.is_match({"any": "tags"})
        assert filter.is_match({})

    def test_is_match_with_present_filter(self):
        filter = TagsFilter(required_key=FilterCase.PRESENT)
        assert filter.is_match({"required_key": "any_value"})
        assert not filter.is_match({"other_key": "value"})
        assert not filter.is_match({})

    def test_is_match_with_absent_filter(self):
        filter = TagsFilter(forbidden_key=FilterCase.ABSENT)
        assert filter.is_match({"other_key": "value"})
        assert filter.is_match({})
        assert not filter.is_match({"forbidden_key": "any_value"})

    def test_is_match_with_specific_value(self):
        filter = TagsFilter(key1="expected_value")
        assert filter.is_match({"key1": "expected_value"})
        assert not filter.is_match({"key1": "wrong_value"})
        assert not filter.is_match({})

    def test_is_match_with_combined_filters(self):
        filter = TagsFilter(
            present_key=FilterCase.PRESENT,
            absent_key=FilterCase.ABSENT,
            specific_key="specific_value",
        )
        assert filter.is_match(
            {"present_key": "any", "specific_key": "specific_value", "other": "data"}
        )
        assert not filter.is_match(
            {"present_key": "any", "specific_key": "wrong_value"}
        )
        assert not filter.is_match(
            {"present_key": "any", "absent_key": "should_not_be_here"}
        )
        assert not filter.is_match({"specific_key": "specific_value"})


class TestEcsTaskTagsReader:
    @pytest.fixture
    def tags_reader(self):
        return EcsTaskTagsReader()

    @pytest.fixture
    def mock_ecs_client(self):
        client = AsyncMock()
        return client

    async def test_init(self, tags_reader: EcsTaskTagsReader):
        assert tags_reader.ecs_client is None
        assert isinstance(tags_reader._cache, LRUCache)
        assert tags_reader._cache.maxsize == 100

    async def test_read_tags_without_client(self, tags_reader: EcsTaskTagsReader):
        with pytest.raises(RuntimeError, match="ECS client not initialized"):
            await tags_reader.read_tags("cluster-arn", "task-arn")

    async def test_read_tags_from_cache(
        self, tags_reader: EcsTaskTagsReader, mock_ecs_client: AsyncMock
    ):
        tags_reader.ecs_client = mock_ecs_client
        cached_tags = {"key": "value"}
        tags_reader._cache["task-arn"] = cached_tags

        result = await tags_reader.read_tags("cluster-arn", "task-arn")

        assert result == cached_tags
        mock_ecs_client.describe_tasks.assert_not_called()

    async def test_read_tags_from_ecs(
        self, tags_reader: EcsTaskTagsReader, mock_ecs_client: AsyncMock
    ):
        tags_reader.ecs_client = mock_ecs_client
        mock_ecs_client.describe_tasks.return_value = {
            "tasks": [
                {
                    "tags": [
                        {"key": "tag1", "value": "value1"},
                        {"key": "tag2", "value": "value2"},
                    ]
                }
            ]
        }

        result = await tags_reader.read_tags("cluster-arn", "task-arn")

        assert result == {"tag1": "value1", "tag2": "value2"}
        assert tags_reader._cache["task-arn"] == result
        mock_ecs_client.describe_tasks.assert_called_once_with(
            cluster="cluster-arn",
            tasks=["task-arn"],
            include=["TAGS"],
        )

    async def test_read_tags_handles_missing_keys(
        self, tags_reader: EcsTaskTagsReader, mock_ecs_client: AsyncMock
    ):
        tags_reader.ecs_client = mock_ecs_client
        mock_ecs_client.describe_tasks.return_value = {
            "tasks": [
                {
                    "tags": [
                        {"key": "tag1", "value": "value1"},
                        {"value": "missing_key"},
                        {"key": "missing_value"},
                        {},
                    ]
                }
            ]
        }

        result = await tags_reader.read_tags("cluster-arn", "task-arn")

        assert result == {"tag1": "value1"}

    async def test_read_tags_handles_empty_response(
        self, tags_reader: EcsTaskTagsReader, mock_ecs_client: AsyncMock
    ):
        tags_reader.ecs_client = mock_ecs_client
        mock_ecs_client.describe_tasks.return_value = {}

        result = await tags_reader.read_tags("cluster-arn", "task-arn")

        assert result == {}

    async def test_read_tags_handles_exception(
        self,
        tags_reader: EcsTaskTagsReader,
        mock_ecs_client: AsyncMock,
        capfd: pytest.CaptureFixture[str],
    ):
        tags_reader.ecs_client = mock_ecs_client
        mock_ecs_client.describe_tasks.side_effect = Exception("AWS error")

        result = await tags_reader.read_tags("cluster-arn", "task-arn")

        assert result == {}
        captured = capfd.readouterr()
        assert "Error reading tags for task task-arn: AWS error" in captured.out


class TestSqsSubscriber:
    @pytest.fixture
    def subscriber(self) -> SqsSubscriber:
        return SqsSubscriber("test-queue", "us-east-1")

    def test_init(self) -> None:
        subscriber = SqsSubscriber("queue-name", "us-west-2")
        assert subscriber.queue_name == "queue-name"
        assert subscriber.queue_region == "us-west-2"

    def test_init_without_region(self) -> None:
        subscriber = SqsSubscriber("queue-name")
        assert subscriber.queue_name == "queue-name"
        assert subscriber.queue_region is None

    @patch("prefect_aws.observers.ecs.aiobotocore.session.get_session")
    async def test_stream_messages(
        self, mock_get_session: AsyncMock, subscriber: SqsSubscriber
    ) -> None:
        mock_session = Mock()
        mock_sqs_client = AsyncMock()
        mock_client_context = AsyncMock()
        mock_client_context.__aenter__.return_value = mock_sqs_client
        mock_session.create_client.return_value = mock_client_context
        mock_get_session.return_value = mock_session

        mock_sqs_client.get_queue_url.return_value = {
            "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        }

        messages_batch_1 = {
            "Messages": [
                {"Body": "message1", "ReceiptHandle": "handle1"},
                {"Body": "message2", "ReceiptHandle": "handle2"},
            ]
        }
        messages_batch_2 = {
            "Messages": [
                {"Body": "message3", "ReceiptHandle": "handle3"},
            ]
        }
        empty_batch = {"Messages": []}

        mock_sqs_client.receive_message.side_effect = [
            messages_batch_1,
            messages_batch_2,
            empty_batch,
        ]

        messages = []
        message_generator = subscriber.stream_messages()
        async for message in message_generator:
            messages.append(message)
            if len(messages) >= 3:
                # Close the generator properly to avoid pending task warning
                await message_generator.aclose()
                break

        assert len(messages) == 3
        assert messages[0]["Body"] == "message1"
        assert messages[1]["Body"] == "message2"
        assert messages[2]["Body"] == "message3"

        # Note: Only 2 deletes will be called because we break after the 3rd yield
        # but before its delete can execute
        assert mock_sqs_client.delete_message.call_count == 2
        delete_calls = mock_sqs_client.delete_message.call_args_list

        # Extract the arguments from each call (only 2 will complete)
        for i, handle in enumerate(["handle1", "handle2"]):
            call_kwargs = delete_calls[i].kwargs
            assert (
                call_kwargs["QueueUrl"]
                == "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
            )
            assert call_kwargs["ReceiptHandle"] == handle

    @patch("prefect_aws.observers.ecs.aiobotocore.session.get_session")
    async def test_stream_messages_skips_without_receipt_handle(
        self, mock_get_session: AsyncMock, subscriber: SqsSubscriber
    ):
        mock_session = Mock()
        mock_sqs_client = AsyncMock()
        mock_client_context = AsyncMock()
        mock_client_context.__aenter__.return_value = mock_sqs_client
        mock_session.create_client.return_value = mock_client_context
        mock_get_session.return_value = mock_session

        mock_sqs_client.get_queue_url.return_value = {
            "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789/test-queue"
        }

        messages_batch = {
            "Messages": [
                {"Body": "message1"},  # No ReceiptHandle, should be skipped
                {"Body": "message2", "ReceiptHandle": "handle2"},
            ]
        }

        # Second batch to ensure we can break out
        empty_batch: dict[str, list[Any]] = {"Messages": []}

        mock_sqs_client.receive_message.side_effect = [
            messages_batch,
            empty_batch,
        ]

        messages: list[dict[str, Any]] = []
        message_generator = subscriber.stream_messages()
        async for message in message_generator:
            messages.append(message)
            # Since message1 is skipped (no receipt handle), we only get message2
            await message_generator.aclose()
            break

        assert len(messages) == 1
        assert messages[0]["Body"] == "message2"
        assert messages[0]["ReceiptHandle"] == "handle2"

        # Note: delete may not be called if we break immediately after yield
        # The generator is interrupted before the delete after yield can execute


class TestObserverInfrastructureManager:
    @pytest.fixture
    def infrastructure_manager(self) -> ObserverInfrastructureManager:
        return ObserverInfrastructureManager(region="us-east-1")

    @pytest.fixture
    def mock_sqs_client(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_events_client(self) -> AsyncMock:
        return AsyncMock()

    def test_init(self) -> None:
        manager = ObserverInfrastructureManager()
        assert manager.region is None
        assert manager.sqs_client is None
        assert manager.events_client is None
        assert manager._stack is None

    def test_init_with_region(self) -> None:
        manager = ObserverInfrastructureManager(region="us-west-2")
        assert manager.region == "us-west-2"

    async def test_check_sqs_queue_exists_true(
        self,
        infrastructure_manager: ObserverInfrastructureManager,
        mock_sqs_client: AsyncMock,
    ):
        infrastructure_manager.sqs_client = mock_sqs_client
        mock_sqs_client.get_queue_url.return_value = {
            "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123/test-queue"
        }

        result = await infrastructure_manager.check_sqs_queue_exists("test-queue")

        assert result is True
        mock_sqs_client.get_queue_url.assert_called_once_with(QueueName="test-queue")

    async def test_check_sqs_queue_exists_false(
        self,
        infrastructure_manager: ObserverInfrastructureManager,
        mock_sqs_client: AsyncMock,
    ):
        from botocore.exceptions import ClientError

        infrastructure_manager.sqs_client = mock_sqs_client
        mock_sqs_client.get_queue_url.side_effect = ClientError(
            {"Error": {"Code": "AWS.SimpleQueueService.NonExistentQueue"}},
            "GetQueueUrl",
        )

        result = await infrastructure_manager.check_sqs_queue_exists(
            "nonexistent-queue"
        )

        assert result is False
        mock_sqs_client.get_queue_url.assert_called_once_with(
            QueueName="nonexistent-queue"
        )

    async def test_check_sqs_queue_exists_other_error(
        self,
        infrastructure_manager: ObserverInfrastructureManager,
        mock_sqs_client: AsyncMock,
    ):
        from botocore.exceptions import ClientError

        infrastructure_manager.sqs_client = mock_sqs_client
        mock_sqs_client.get_queue_url.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "GetQueueUrl"
        )

        with pytest.raises(ClientError):
            await infrastructure_manager.check_sqs_queue_exists("test-queue")

    async def test_check_sqs_queue_exists_no_client(
        self, infrastructure_manager: ObserverInfrastructureManager
    ):
        with pytest.raises(RuntimeError, match="SQS client not initialized"):
            await infrastructure_manager.check_sqs_queue_exists("test-queue")

    async def test_setup_sqs_queue(
        self,
        infrastructure_manager: ObserverInfrastructureManager,
        mock_sqs_client: AsyncMock,
    ):
        infrastructure_manager.sqs_client = mock_sqs_client

        # Mock create_queue response
        mock_sqs_client.create_queue.return_value = {
            "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123/test-queue"
        }

        # Mock get_queue_attributes response
        mock_sqs_client.get_queue_attributes.return_value = {
            "Attributes": {"QueueArn": "arn:aws:sqs:us-east-1:123:test-queue"}
        }

        result = await infrastructure_manager.setup_sqs_queue("test-queue")

        assert result == "arn:aws:sqs:us-east-1:123:test-queue"

        # Verify create_queue was called with correct parameters
        mock_sqs_client.create_queue.assert_called_once_with(
            QueueName="test-queue",
            Attributes={
                "MessageRetentionPeriod": "1209600",
                "VisibilityTimeoutSeconds": "60",
            },
        )

        # Verify policy was set
        policy_call = mock_sqs_client.set_queue_attributes.call_args
        assert (
            policy_call[1]["QueueUrl"]
            == "https://sqs.us-east-1.amazonaws.com/123/test-queue"
        )
        policy = json.loads(policy_call[1]["Attributes"]["Policy"])
        assert policy["Version"] == "2012-10-17"
        assert len(policy["Statement"]) == 1
        assert policy["Statement"][0]["Principal"]["Service"] == "events.amazonaws.com"

    async def test_setup_sqs_queue_no_client(
        self, infrastructure_manager: ObserverInfrastructureManager
    ):
        with pytest.raises(RuntimeError, match="SQS client not initialized"):
            await infrastructure_manager.setup_sqs_queue("test-queue")

    async def test_setup_eventbridge_rule(
        self,
        infrastructure_manager: ObserverInfrastructureManager,
        mock_events_client: AsyncMock,
    ):
        infrastructure_manager.events_client = mock_events_client
        queue_arn = "arn:aws:sqs:us-east-1:123:test-queue"

        await infrastructure_manager.setup_eventbridge_rule(queue_arn)

        # Verify put_rule was called
        put_rule_call = mock_events_client.put_rule.call_args
        assert put_rule_call[1]["Name"] == "prefect-ecs-task-state-changes"
        event_pattern = json.loads(put_rule_call[1]["EventPattern"])
        assert event_pattern["source"] == ["aws.ecs"]
        assert "ECS Task State Change" in event_pattern["detail-type"]

        # Verify put_targets was called
        put_targets_call = mock_events_client.put_targets.call_args
        assert put_targets_call[1]["Rule"] == "prefect-ecs-task-state-changes"
        assert put_targets_call[1]["Targets"][0]["Arn"] == queue_arn

    async def test_setup_eventbridge_rule_no_client(
        self, infrastructure_manager: ObserverInfrastructureManager
    ):
        with pytest.raises(RuntimeError, match="Events client not initialized"):
            await infrastructure_manager.setup_eventbridge_rule(
                "arn:aws:sqs:us-east-1:123:test"
            )

    async def test_setup_complete_infrastructure(
        self,
        infrastructure_manager: ObserverInfrastructureManager,
        mock_sqs_client: AsyncMock,
        mock_events_client: AsyncMock,
    ):
        infrastructure_manager.sqs_client = mock_sqs_client
        infrastructure_manager.events_client = mock_events_client

        # Mock the setup_sqs_queue response
        mock_sqs_client.create_queue.return_value = {
            "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123/test-queue"
        }
        mock_sqs_client.get_queue_attributes.return_value = {
            "Attributes": {"QueueArn": "arn:aws:sqs:us-east-1:123:test-queue"}
        }

        result = await infrastructure_manager.setup_complete_infrastructure(
            "test-queue"
        )

        assert result == "arn:aws:sqs:us-east-1:123:test-queue"

        # Verify both SQS and EventBridge setup were called
        mock_sqs_client.create_queue.assert_called_once()
        mock_events_client.put_rule.assert_called_once()
        mock_events_client.put_targets.assert_called_once()


class TestEcsObserver:
    @pytest.fixture
    def settings(self) -> EcsObserverSettings:
        return EcsObserverSettings()

    @pytest.fixture
    def mock_sqs_subscriber(self) -> AsyncMock:
        return AsyncMock(spec=SqsSubscriber)

    @pytest.fixture
    def mock_tags_reader(self) -> AsyncMock:
        reader = AsyncMock(spec=EcsTaskTagsReader)
        reader.__aenter__.return_value = reader
        return reader

    @pytest.fixture
    def mock_infrastructure_manager(self) -> AsyncMock:
        manager = AsyncMock()
        manager.check_sqs_queue_exists.return_value = True
        # Mock context manager behavior
        manager.__aenter__.return_value = manager
        manager.__aexit__.return_value = None
        return manager

    @pytest.fixture
    def observer(
        self,
        settings: EcsObserverSettings,
        mock_sqs_subscriber: AsyncMock,
        mock_tags_reader: AsyncMock,
        mock_infrastructure_manager: AsyncMock,
    ) -> EcsObserver:
        return EcsObserver(
            settings=settings,
            sqs_subscriber=mock_sqs_subscriber,
            ecs_tags_reader=mock_tags_reader,
            infrastructure_manager=mock_infrastructure_manager,
        )

    def test_init_with_defaults(self):
        observer = EcsObserver()
        assert isinstance(observer.settings, EcsObserverSettings)
        assert isinstance(observer.sqs_subscriber, SqsSubscriber)
        assert isinstance(observer.ecs_tags_reader, EcsTaskTagsReader)
        assert observer.event_handlers == {
            "task": [],
            "container-instance": [],
            "deployment": [],
        }

    def test_init_with_custom_components(
        self,
        settings: EcsObserverSettings,
        mock_sqs_subscriber: AsyncMock,
        mock_tags_reader: AsyncMock,
    ):
        observer = EcsObserver(
            settings=settings,
            sqs_subscriber=mock_sqs_subscriber,
            ecs_tags_reader=mock_tags_reader,
        )
        assert observer.settings == settings
        assert observer.sqs_subscriber == mock_sqs_subscriber
        assert observer.ecs_tags_reader == mock_tags_reader

    def test_on_event_decorator(self, observer: EcsObserver):
        handler = Mock()

        decorated = observer.on_event("task", tags={"key": "value"})(handler)

        assert decorated == handler
        assert len(observer.event_handlers["task"]) == 1
        handler_with_filters = observer.event_handlers["task"][0]
        assert handler_with_filters.handler == handler
        assert isinstance(handler_with_filters.filters["tags"], TagsFilter)

    def test_on_event_decorator_multiple_handlers(self, observer: EcsObserver):
        handler1 = Mock()
        handler2 = Mock()

        observer.on_event("task")(handler1)
        observer.on_event("task", tags={"key": FilterCase.PRESENT})(handler2)

        assert len(observer.event_handlers["task"]) == 2

    async def test_run_with_started_event(
        self,
        observer: EcsObserver,
        mock_sqs_subscriber: AsyncMock,
        mock_tags_reader: AsyncMock,
    ):
        started_event = asyncio.Event()
        mock_sqs_subscriber.stream_messages.return_value = async_generator_from_list([])

        task = asyncio.create_task(observer.run(started_event=started_event))

        await asyncio.wait_for(started_event.wait(), timeout=1.0)
        assert started_event.is_set()

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_run_processes_messages(
        self,
        observer: EcsObserver,
        mock_sqs_subscriber: AsyncMock,
        mock_tags_reader: AsyncMock,
    ):
        handler = AsyncMock()
        handler.__name__ = "test_handler"  # Mock needs __name__ attribute
        observer.on_event("task", tags={"prefect": "test"})(handler)

        message = {
            "Body": json.dumps(
                {
                    "detail-type": "ECS Task State Change",
                    "detail": {
                        "taskArn": "arn:aws:ecs:us-east-1:123456789:task/task-id",
                        "clusterArn": "arn:aws:ecs:us-east-1:123456789:cluster/cluster",
                    },
                }
            )
        }

        mock_sqs_subscriber.stream_messages.return_value = async_generator_from_list(
            [message]
        )
        mock_tags_reader.read_tags.return_value = {"prefect": "test"}

        task = asyncio.create_task(observer.run())
        await asyncio.sleep(0.1)

        handler.assert_called_once()
        call_args = handler.call_args[0]
        assert call_args[0]["detail-type"] == "ECS Task State Change"
        assert call_args[1] == {"prefect": "test"}

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_run_skips_message_without_body(
        self,
        observer: EcsObserver,
        mock_sqs_subscriber: AsyncMock,
        mock_tags_reader: AsyncMock,
    ):
        handler = Mock()
        handler.__name__ = "test_handler"  # Mock needs __name__ attribute
        observer.on_event("task")(handler)

        message = {"MessageId": "123"}

        mock_sqs_subscriber.stream_messages.return_value = async_generator_from_list(
            [message]
        )

        task = asyncio.create_task(observer.run())
        await asyncio.sleep(0.1)

        handler.assert_not_called()

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_run_handles_sync_handler(
        self,
        observer: EcsObserver,
        mock_sqs_subscriber: AsyncMock,
        mock_tags_reader: AsyncMock,
    ):
        handler = Mock()
        handler.__name__ = "test_handler"  # Mock needs __name__ attribute
        observer.on_event("task")(handler)

        message = {
            "Body": json.dumps(
                {
                    "detail-type": "ECS Task State Change",
                    "detail": {},
                }
            )
        }

        mock_sqs_subscriber.stream_messages.return_value = async_generator_from_list(
            [message]
        )

        task = asyncio.create_task(observer.run())
        await asyncio.sleep(0.2)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except BaseException:
            # Handle any ExceptionGroup raised by the task group
            pass

    async def test_run_filters_handlers_by_tags(
        self,
        observer: EcsObserver,
        mock_sqs_subscriber: AsyncMock,
        mock_tags_reader: AsyncMock,
    ):
        matching_handler = AsyncMock()
        matching_handler.__name__ = "matching_handler"  # Mock needs __name__ attribute
        non_matching_handler = AsyncMock()
        non_matching_handler.__name__ = (
            "non_matching_handler"  # Mock needs __name__ attribute
        )

        observer.on_event("task", tags={"env": "prod"})(matching_handler)
        observer.on_event("task", tags={"env": "dev"})(non_matching_handler)

        message = {
            "Body": json.dumps(
                {
                    "detail-type": "ECS Task State Change",
                    "detail": {
                        "taskArn": "arn:aws:ecs:us-east-1:123456789:task/task-id",
                        "clusterArn": "arn:aws:ecs:us-east-1:123456789:cluster/cluster",
                    },
                }
            )
        }

        mock_sqs_subscriber.stream_messages.return_value = async_generator_from_list(
            [message]
        )
        mock_tags_reader.read_tags.return_value = {"env": "prod"}

        task = asyncio.create_task(observer.run())
        await asyncio.sleep(0.2)

        matching_handler.assert_called_once()
        non_matching_handler.assert_not_called()

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def test_ensure_queue_setup_queue_exists(self):
        settings = EcsObserverSettings()
        mock_manager_instance = AsyncMock()
        mock_manager_instance.check_sqs_queue_exists.return_value = True

        mock_infrastructure_manager = AsyncMock()
        mock_infrastructure_manager.__aenter__.return_value = mock_manager_instance
        mock_infrastructure_manager.__aexit__.return_value = None

        observer = EcsObserver(
            settings=settings,
            infrastructure_manager=mock_infrastructure_manager,
        )

        await observer._ensure_queue_setup()

        # Should check if queue exists but not set up infrastructure
        mock_manager_instance.check_sqs_queue_exists.assert_called_once_with(
            settings.sqs.queue_name
        )
        mock_manager_instance.setup_complete_infrastructure.assert_not_called()

    async def test_ensure_queue_setup_queue_missing_automatic_setup_enabled(self):
        settings = EcsObserverSettings(automatic_setup=True)
        mock_manager_instance = AsyncMock()
        mock_manager_instance.check_sqs_queue_exists.return_value = False
        mock_manager_instance.setup_complete_infrastructure.return_value = (
            "arn:aws:sqs:us-east-1:123:test"
        )

        mock_infrastructure_manager = AsyncMock()
        mock_infrastructure_manager.__aenter__.return_value = mock_manager_instance
        mock_infrastructure_manager.__aexit__.return_value = None

        observer = EcsObserver(
            settings=settings,
            infrastructure_manager=mock_infrastructure_manager,
        )

        await observer._ensure_queue_setup()

        # Should check if queue exists and set up infrastructure
        mock_manager_instance.check_sqs_queue_exists.assert_called_once_with(
            settings.sqs.queue_name
        )
        mock_manager_instance.setup_complete_infrastructure.assert_called_once_with(
            settings.sqs.queue_name
        )

    async def test_ensure_queue_setup_queue_missing_automatic_setup_disabled(self):
        settings = EcsObserverSettings(automatic_setup=False)
        mock_manager_instance = AsyncMock()
        mock_manager_instance.check_sqs_queue_exists.return_value = False

        mock_infrastructure_manager = AsyncMock()
        mock_infrastructure_manager.__aenter__.return_value = mock_manager_instance
        mock_infrastructure_manager.__aexit__.return_value = None

        observer = EcsObserver(
            settings=settings,
            infrastructure_manager=mock_infrastructure_manager,
        )

        await observer._ensure_queue_setup()

        # Should check if queue exists but not set up infrastructure
        mock_manager_instance.check_sqs_queue_exists.assert_called_once_with(
            settings.sqs.queue_name
        )
        mock_manager_instance.setup_complete_infrastructure.assert_not_called()

    def test_init_with_custom_infrastructure_manager(
        self,
        settings: EcsObserverSettings,
        mock_sqs_subscriber: AsyncMock,
        mock_tags_reader: AsyncMock,
    ):
        custom_manager = AsyncMock()
        observer = EcsObserver(
            settings=settings,
            sqs_subscriber=mock_sqs_subscriber,
            ecs_tags_reader=mock_tags_reader,
            infrastructure_manager=custom_manager,
        )

        assert observer.infrastructure_manager == custom_manager
        assert observer.settings == settings
        assert observer.sqs_subscriber == mock_sqs_subscriber
        assert observer.ecs_tags_reader == mock_tags_reader


class TestRelatedResourcesFromTags:
    def test_empty_tags(self):
        result = _related_resources_from_tags({})
        assert result == []

    def test_flow_run_tags(self):
        tags = {
            "prefect.io/flow-run-id": "flow-run-123",
            "prefect.io/flow-run-name": "my-flow-run",
        }
        result = _related_resources_from_tags(tags)

        assert len(result) == 1
        assert (
            result[0].model_dump()["prefect.resource.id"]
            == "prefect.flow-run.flow-run-123"
        )
        assert result[0].model_dump()["prefect.resource.role"] == "flow-run"
        assert result[0].model_dump()["prefect.resource.name"] == "my-flow-run"

    def test_deployment_tags(self):
        tags = {
            "prefect.io/deployment-id": "deployment-456",
            "prefect.io/deployment-name": "my-deployment",
        }
        result = _related_resources_from_tags(tags)

        assert len(result) == 1
        assert (
            result[0].model_dump()["prefect.resource.id"]
            == "prefect.deployment.deployment-456"
        )
        assert result[0].model_dump()["prefect.resource.role"] == "deployment"
        assert result[0].model_dump()["prefect.resource.name"] == "my-deployment"

    def test_flow_tags(self):
        tags = {
            "prefect.io/flow-id": "flow-789",
            "prefect.io/flow-name": "my-flow",
        }
        result = _related_resources_from_tags(tags)

        assert len(result) == 1
        assert result[0].model_dump()["prefect.resource.id"] == "prefect.flow.flow-789"
        assert result[0].model_dump()["prefect.resource.role"] == "flow"
        assert result[0].model_dump()["prefect.resource.name"] == "my-flow"

    def test_work_pool_tags(self):
        tags = {
            "prefect.io/work-pool-id": "pool-abc",
            "prefect.io/work-pool-name": "my-pool",
        }
        result = _related_resources_from_tags(tags)

        assert len(result) == 1
        assert (
            result[0].model_dump()["prefect.resource.id"]
            == "prefect.work-pool.pool-abc"
        )
        assert result[0].model_dump()["prefect.resource.role"] == "work-pool"
        assert result[0].model_dump()["prefect.resource.name"] == "my-pool"

    def test_worker_tags(self):
        tags = {
            "prefect.io/worker-name": "My Worker",
        }
        result = _related_resources_from_tags(tags)

        assert len(result) == 1
        assert (
            result[0].model_dump()["prefect.resource.id"]
            == "prefect.worker.ecs.my-worker"
        )
        assert result[0].model_dump()["prefect.resource.role"] == "worker"
        assert result[0].model_dump()["prefect.resource.name"] == "My Worker"

    def test_all_tags_combined(self):
        tags = {
            "prefect.io/flow-run-id": "flow-run-123",
            "prefect.io/flow-run-name": "my-flow-run",
            "prefect.io/deployment-id": "deployment-456",
            "prefect.io/deployment-name": "my-deployment",
            "prefect.io/flow-id": "flow-789",
            "prefect.io/flow-name": "my-flow",
            "prefect.io/work-pool-id": "pool-abc",
            "prefect.io/work-pool-name": "my-pool",
            "prefect.io/worker-name": "my-worker",
        }
        result = _related_resources_from_tags(tags)

        assert len(result) == 5
        resource_ids = [r.model_dump()["prefect.resource.id"] for r in result]
        assert "prefect.flow-run.flow-run-123" in resource_ids
        assert "prefect.deployment.deployment-456" in resource_ids
        assert "prefect.flow.flow-789" in resource_ids
        assert "prefect.work-pool.pool-abc" in resource_ids
        assert "prefect.worker.ecs.my-worker" in resource_ids


class TestReplicateEcsEvent:
    @pytest.fixture
    def sample_event(self):
        return {
            "id": str(uuid.uuid4()),
            "time": "2024-01-01T12:00:00Z",
            "detail": {
                "taskArn": "arn:aws:ecs:us-east-1:123456789:task/cluster/task-id",
                "clusterArn": "arn:aws:ecs:us-east-1:123456789:cluster/cluster",
                "taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789:task-definition/task-def:1",
                "lastStatus": "RUNNING",
            },
        }

    @pytest.fixture
    def sample_tags(self):
        return {
            "prefect.io/flow-run-id": "flow-run-123",
            "prefect.io/flow-run-name": "my-flow-run",
        }

    @patch("prefect_aws.observers.ecs.get_events_client")
    async def test_replicate_ecs_event(
        self,
        mock_get_events_client: AsyncMock,
        sample_event: dict[str, Any],
        sample_tags: dict[str, str],
    ):
        mock_events_client = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_events_client
        mock_get_events_client.return_value = mock_context

        await replicate_ecs_event(sample_event, sample_tags)

        mock_events_client.emit.assert_called_once()
        emitted_event = mock_events_client.emit.call_args[1]["event"]

        assert emitted_event.event == "prefect.ecs.task.running"
        assert emitted_event.id == uuid.UUID(sample_event["id"])
        assert "prefect.ecs.task.task-id" in str(
            emitted_event.resource.model_dump()["prefect.resource.id"]
        )
        assert len(emitted_event.related) > 0

    @patch("prefect_aws.observers.ecs.get_events_client")
    async def test_replicate_ecs_event_missing_id(
        self, mock_get_events_client: AsyncMock, sample_tags: dict[str, str]
    ):
        event = {"detail": {"taskArn": "arn", "lastStatus": "RUNNING"}}

        await replicate_ecs_event(event, sample_tags)

        mock_get_events_client.assert_not_called()

    @patch("prefect_aws.observers.ecs.get_events_client")
    async def test_replicate_ecs_event_missing_task_arn(
        self, mock_get_events_client: AsyncMock, sample_tags: dict[str, str]
    ):
        event = {"id": str(uuid.uuid4()), "detail": {"lastStatus": "RUNNING"}}

        await replicate_ecs_event(event, sample_tags)

        mock_get_events_client.assert_not_called()

    @patch("prefect_aws.observers.ecs.get_events_client")
    async def test_replicate_ecs_event_missing_last_status(
        self, mock_get_events_client: AsyncMock, sample_tags: dict[str, str]
    ):
        event = {
            "id": str(uuid.uuid4()),
            "detail": {
                "taskArn": "arn:aws:ecs:us-east-1:123456789:task/cluster/task-id"
            },
        }

        await replicate_ecs_event(event, sample_tags)

        mock_get_events_client.assert_not_called()

    @patch("prefect_aws.observers.ecs.get_events_client")
    @patch("prefect_aws.observers.ecs._last_event_cache")
    async def test_replicate_ecs_event_with_follows(
        self,
        mock_cache: AsyncMock,
        mock_get_events_client: AsyncMock,
        sample_event: dict[str, Any],
        sample_tags: dict[str, str],
    ):
        mock_events_client = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_events_client
        mock_get_events_client.return_value = mock_context

        previous_event = Event(
            event="prefect.ecs.task.pending",
            resource=Resource.model_validate({"prefect.resource.id": "test"}),
            occurred=datetime.fromisoformat("2024-01-01T11:59:00+00:00"),
        )
        mock_cache.get.return_value = previous_event

        await replicate_ecs_event(sample_event, sample_tags)

        emitted_event = mock_events_client.emit.call_args[1]["event"]
        assert emitted_event.follows == previous_event.id

    @patch("prefect_aws.observers.ecs.get_events_client")
    async def test_replicate_ecs_event_handles_exception(
        self,
        mock_get_events_client: AsyncMock,
        sample_event: dict[str, Any],
        sample_tags: dict[str, str],
    ):
        mock_events_client = AsyncMock()
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_events_client
        mock_get_events_client.return_value = mock_context
        mock_events_client.emit.side_effect = Exception("Emit failed")

        await replicate_ecs_event(sample_event, sample_tags)


class TestObserverManagement:
    @patch("prefect_aws.observers.ecs._DEFAULT_ECS_OBSERVER")
    async def test_start_and_stop_observer(self, mock_observer: AsyncMock):
        mock_observer.run = AsyncMock(
            side_effect=lambda started_event: started_event.set()
        )

        await start_observer()

        mock_observer.run.assert_called_once()

        await start_observer()

        # Shouldn't be called again
        mock_observer.run.assert_called_once()

        await stop_observer()

    async def test_stop_observer_not_running(self):
        # Shouldn't raise
        await stop_observer()


async def async_generator_from_list(items: list[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item

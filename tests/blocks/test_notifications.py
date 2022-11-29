from importlib import reload
from typing import Type
from unittest.mock import patch

import cloudpickle
import pytest
from pydantic import ValidationError

import prefect
from prefect.blocks.notifications import (
    AppriseNotificationBlock,
    PagerDutyWebHook,
    PrefectNotifyType,
)
from prefect.testing.utilities import AsyncMock


def reload_modules():
    """
    Reloads the prefect.blocks.notifications module so patches to modules it imports
    will be visible to the blocks under test.
    """
    try:
        reload(prefect.blocks.notifications)
    except UserWarning as ex:
        # ignore the warning Prefect gives when reloading the notifications module
        # because we reload prefect itself immediately afterward.
        pass

    reload(prefect)


# A list of the notification classes Pytest should use as parameters to each method in TestAppriseNotificationBlock
notification_classes = sorted(
    AppriseNotificationBlock.__subclasses__(), key=lambda cls: cls.__name__
)


@pytest.mark.parametrize("block_class", notification_classes)
class TestAppriseNotificationBlock:
    """
    Checks for behavior expected from Apprise-based notification blocks.
    """

    async def test_notify_async(self, block_class: Type[AppriseNotificationBlock]):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = block_class(url="https://example.com/notification")
            await block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                block.url.get_secret_value()
            )

            if block_class.__name__ == "PagerDutyWebHook":
                notify_type = "info"
            else:
                notify_type = PrefectNotifyType.DEFAULT
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=notify_type
            )

    def test_notify_sync(self, block_class: Type[AppriseNotificationBlock]):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = block_class(url="https://example.com/notification")
            block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                block.url.get_secret_value()
            )

            if block_class.__name__ == "PagerDutyWebHook":
                notify_type = "info"
            else:
                notify_type = PrefectNotifyType.DEFAULT
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=notify_type
            )

    def test_is_picklable(self, block_class: Type[AppriseNotificationBlock]):
        reload_modules()
        block = block_class(url="http://example.com/notification")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, block_class)


class TestPagerDutyWebhook:
    @pytest.mark.parametrize("key", [None, "integration_key", "api_key"])
    def test_validate_has_either_url_or_components(self, key):
        webhook_kwargs = dict(
            integration_key="my-integration-key", api_key="my-api-key", url="my-url"
        )
        if key:
            webhook_kwargs.pop(key)
        with pytest.raises(ValidationError, match="Cannot provide url alongside"):
            PagerDutyWebHook(**webhook_kwargs)

    @pytest.mark.parametrize("key", ["integration_key", "api_key"])
    def test_validate_has_both_keys(self, key):
        webhook_kwargs = dict(
            integration_key="my-integration-key", api_key="my-api-key"
        )
        webhook_kwargs.pop(key)
        with pytest.raises(ValidationError, match="Must provide both"):
            PagerDutyWebHook(**webhook_kwargs)

    def test_instantiate_with_url(self):
        assert isinstance(
            PagerDutyWebHook(url="pagerduty://int_key@api_key"), PagerDutyWebHook
        )

    def test_instantiate_with_keys(self):
        assert isinstance(
            PagerDutyWebHook(integration_key="int_key", api_key="api_key"),
            PagerDutyWebHook,
        )

    def test_save_load_roundtrip(self):
        pagerduty_webhook = PagerDutyWebHook(
            integration_key="int_key", api_key="api_key"
        )
        pagerduty_webhook.save("my-block", overwrite=True)
        loaded_pagerduty_webhook = pagerduty_webhook.load("my-block")
        assert loaded_pagerduty_webhook.integration_key.get_secret_value() == "int_key"
        assert loaded_pagerduty_webhook.api_key.get_secret_value() == "api_key"

from importlib import reload
from typing import Type
from unittest.mock import patch

import cloudpickle
import pytest
import respx
from httpx import Response

import prefect
from prefect.blocks.notifications import (
    AppriseNotificationBlock,
    PrefectNotifyType,
    TwilioSMS,
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
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PrefectNotifyType.DEFAULT
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
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PrefectNotifyType.DEFAULT
            )

    def test_is_picklable(self, block_class: Type[AppriseNotificationBlock]):
        reload_modules()
        block = block_class(url="http://example.com/notification")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, block_class)


class TestTwilioSMS:
    @respx.mock(assert_all_called=True)
    @pytest.fixture
    def mock_unsuccessful_sms_message(self, respx_mock):
        url = "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Messages.json"

        respx_mock.post(url).mock(
            return_value=Response(
                400,
                json={
                    "code": 21211,
                    "message": "The 'To' number 8675309 is not a valid phone number.",
                    "more_info": "https://www.twilio.com/docs/errors/21211",
                    "status": 400,
                },
            )
        )

    def test_instantiate_with_url_components(self):
        assert isinstance(
            TwilioSMS(
                account_sid="ACxxx",
                auth_token="XXX",
                from_phone_number="11234567890",
                to_phone_number=["12345678901"],
            ),
            TwilioSMS,
        )

    def test_raises_error_on_bad_phone_number(self, mock_unsuccessful_sms_message):
        twilio = TwilioSMS(
            account_sid="ACxxx",
            auth_token="XXX",
            from_phone_number="42424242424",
            to_phone_number=["8675309"],
        )
        with pytest.raises(ValueError, match="8675309 is not a valid phone number"):
            twilio.notify("test")

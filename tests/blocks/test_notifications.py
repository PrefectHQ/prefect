from importlib import reload
from typing import Optional, Type
from unittest.mock import patch

import cloudpickle
import pytest

import prefect
from prefect.blocks.notifications import (
    AppriseNotificationBlock,
    MattermostWebhook,
    OpsgenieWebhook,
    PagerDutyWebHook,
    PrefectNotifyType,
    TwilioSMS,
    CustomWebhookNotificationBlock,
)
from prefect.testing.utilities import AsyncMock


def reload_modules():
    """
    Reloads the prefect.blocks.notifications module so patches to modules it imports
    will be visible to the blocks under test.
    """
    try:
        reload(prefect.blocks.notifications)
    except UserWarning:
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
            apprise_instance_mock.async_notify.assert_called_once_with(
                body="test", title=None, notify_type=PrefectNotifyType.DEFAULT
            )

    def test_is_picklable(self, block_class: Type[AppriseNotificationBlock]):
        reload_modules()
        block = block_class(url="http://example.com/notification")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, block_class)


class TestMattermostWebhook:
    async def test_notify_async(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            mm_block = MattermostWebhook(
                hostname="example.com",
                token="token",
                include_image=True,
            )
            await mm_block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"mmost://{mm_block.hostname}/{mm_block.token.get_secret_value()}/"
                "?image=yes&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PrefectNotifyType.DEFAULT
            )

    def test_notify_sync(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            mm_block = MattermostWebhook(hostname="example.com", token="token")
            mm_block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"mmost://{mm_block.hostname}/{mm_block.token.get_secret_value()}/"
                "?image=no&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )
            apprise_instance_mock.async_notify.assert_called_once_with(
                body="test", title=None, notify_type=PrefectNotifyType.DEFAULT
            )

    def test_notify_with_multiple_channels(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            mm_block = MattermostWebhook(
                hostname="example.com",
                token="token",
                channels=["general", "death-metal-anonymous"],
            )
            mm_block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"mmost://{mm_block.hostname}/{mm_block.token.get_secret_value()}/"
                "?image=no&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
                "&channel=death-metal-anonymous%2Cgeneral"
            )

            apprise_instance_mock.async_notify.assert_called_once_with(
                body="test", title=None, notify_type=PrefectNotifyType.DEFAULT
            )

    def test_is_picklable(self):
        reload_modules()
        block = MattermostWebhook(token="token", hostname="example.com")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, MattermostWebhook)


class TestOpsgenieWebhook:
    API_KEY = "api_key"

    async def test_notify_async(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = OpsgenieWebhook(apikey=self.API_KEY)
            await block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"opsgenie://{self.API_KEY}//?region=us&priority=normal&batch=no&"
                "format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )

            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PrefectNotifyType.DEFAULT
            )

    def _test_notify_sync(self, targets="", params=None, **kwargs):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            if params is None:
                params = "region=us&priority=normal&batch=no"

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = OpsgenieWebhook(apikey=self.API_KEY, **kwargs)
            block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"opsgenie://{self.API_KEY}/{targets}/?{params}"
                "&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )

            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PrefectNotifyType.DEFAULT
            )

    def test_notify_sync_simple(self):
        self._test_notify_sync()

    def test_notify_sync_params(self):
        params = "region=eu&priority=low&batch=yes"
        self._test_notify_sync(params=params, region_name="eu", priority=1, batch=True)

    def test_notify_sync_targets(self):
        targets = "%23team/%2Aschedule/%40user/%5Eescalation"
        self._test_notify_sync(
            targets=targets,
            target_user=["user"],
            target_team=["team"],
            target_schedule=["schedule"],
            target_escalation=["escalation"],
        )

    def test_notify_sync_users(self):
        targets = "%40user1/%40user2"
        self._test_notify_sync(targets=targets, target_user=["user1", "user2"])

    def test_notify_sync_details(self):
        params = "region=us&priority=normal&batch=no&%2Bkey1=value1&%2Bkey2=value2"
        self._test_notify_sync(
            params=params,
            details={
                "key1": "value1",
                "key2": "value2",
            },
        )


class TestPagerDutyWebhook:
    async def test_notify_async(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = PagerDutyWebHook(integration_key="int_key", api_key="api_key")
            await block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                "pagerduty://int_key@api_key/Prefect/Notification?region=us&"
                "image=yes&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )

            notify_type = "info"
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=notify_type
            )

    def test_notify_sync(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = PagerDutyWebHook(integration_key="int_key", api_key="api_key")
            block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                "pagerduty://int_key@api_key/Prefect/Notification?region=us&"
                "image=yes&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )

            notify_type = "info"
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=notify_type
            )


class TestTwilioSMS:
    @pytest.fixture
    def valid_apprise_url(self) -> str:
        return (
            "twilio://ACabcdefabcdefabcdefabcdef"
            ":XXXXXXXXXXXXXXXXXXXXXXXX"
            "@%2B15555555555/%2B15555555556/%2B15555555557/"
            "?format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
        )

    async def test_twilio_notify_async(self, valid_apprise_url):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            client_instance_mock = AppriseMock.return_value
            client_instance_mock.async_notify = AsyncMock()

            twilio_sms_block = TwilioSMS(
                account_sid="ACabcdefabcdefabcdefabcdef",
                auth_token="XXXXXXXXXXXXXXXXXXXXXXXX",
                from_phone_number="+15555555555",
                to_phone_numbers=["+15555555556", "+15555555557"],
            )

            await twilio_sms_block.notify("hello from prefect")

            AppriseMock.assert_called_once()
            client_instance_mock.add.assert_called_once_with(valid_apprise_url)

            client_instance_mock.async_notify.assert_awaited_once_with(
                body="hello from prefect",
                title=None,
                notify_type=PrefectNotifyType.DEFAULT,
            )

    def test_twilio_notify_sync(self, valid_apprise_url):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            reload_modules()

            client_instance_mock = AppriseMock.return_value
            client_instance_mock.async_notify = AsyncMock()

            twilio_sms_block = TwilioSMS(
                account_sid="ACabcdefabcdefabcdefabcdef",
                auth_token="XXXXXXXXXXXXXXXXXXXXXXXX",
                from_phone_number="+15555555555",
                to_phone_numbers=["+15555555556", "+15555555557"],
            )

            twilio_sms_block.notify("hello from prefect")

            AppriseMock.assert_called_once()
            client_instance_mock.add.assert_called_once_with(valid_apprise_url)

            client_instance_mock.async_notify.assert_awaited_once_with(
                body="hello from prefect",
                title=None,
                notify_type=PrefectNotifyType.DEFAULT,
            )

    def test_invalid_from_phone_number_raises_validation_error(self):
        with pytest.raises(TypeError):
            TwilioSMS(
                account_sid="ACabcdefabcdefabcdefabcdef",
                auth_token="XXXXXXXXXXXXXXXX",
                to_phone_numbers=["+15555555555"],
                from_phone_number="0000000",
            )

    def test_invalid_to_phone_numbers_raises_warning(self, caplog):
        with caplog.at_level("WARNING"):
            TwilioSMS(
                account_sid="ACabcdefabcdefabcdefabcdef",
                auth_token="XXXXXXXXXXXXXXXX",
                to_phone_numbers=["0000000"],
                from_phone_number="+15555555555",
            )

            assert "Dropped invalid phone # (0000000) specified." in caplog.text


class TestCustomWebhook:
    async def _test_notify_async(
        self,
        data: dict,
        expected_call: dict,
        body: str = "test",
        subject: Optional[str] = "subject",
    ):
        with patch("httpx.AsyncClient", autospec=True) as HttpxClientMock:
            reload_modules()

            httpx_instance_mock = HttpxClientMock.return_value
            httpx_instance_mock.request = AsyncMock()

            # use validate here to match alias for 'json'
            custom_block = CustomWebhookNotificationBlock.validate(data)
            await custom_block.notify(body, subject)

            HttpxClientMock.assert_called_once_with(
                headers={"user-agent": "Prefect Notifications"}
            )
            httpx_instance_mock.request.assert_awaited_once_with(**expected_call)

    def _test_notify_sync(
        self,
        data: dict,
        expected_call: dict,
        body: str = "test",
        subject: Optional[str] = "subject",
    ):
        with patch("httpx.AsyncClient", autospec=True) as HttpxClientMock:
            reload_modules()

            httpx_instance_mock = HttpxClientMock.return_value
            httpx_instance_mock.request = AsyncMock()

            custom_block = CustomWebhookNotificationBlock.validate(data)
            custom_block.notify(body, subject)

            HttpxClientMock.assert_called_once_with(
                headers={"user-agent": "Prefect Notifications"}
            )
            httpx_instance_mock.request.assert_awaited_once_with(**expected_call)

    async def test_notify_async(self):
        await self._test_notify_async(
            {
                "name": "test name",
                "url": "https://example.com/",
                "json": {"msg": "${subject}\n${body}", "token": "${token}"},
                "secrets": {"token": "someSecretToken"},
            },
            expected_call={
                "method": "POST",
                "url": "https://example.com/",
                "params": None,
                "data": None,
                "json": {"msg": "subject\ntest", "token": "someSecretToken"},
                "headers": None,
                "cookies": None,
                "timeout": 10,
            },
        )

    def test_notify_sync(self):
        self._test_notify_sync(
            {
                "name": "test name",
                "url": "https://example.com/",
                "json": {"msg": "${subject}\n${body}", "token": "${token}"},
                "secrets": {"token": "someSecretToken"},
            },
            expected_call={
                "method": "POST",
                "url": "https://example.com/",
                "params": None,
                "data": None,
                "json": {"msg": "subject\ntest", "token": "someSecretToken"},
                "headers": None,
                "cookies": None,
                "timeout": 10,
            },
        )

    def test_subst_nested_list(self):
        self._test_notify_sync(
            {
                "name": "test name",
                "url": "https://example.com/",
                "json": {"data": {"sub1": [{"in-list": "${body}"}]}},
                "secrets": {"token": "someSecretToken"},
            },
            expected_call={
                "method": "POST",
                "url": "https://example.com/",
                "params": None,
                "data": None,
                "json": {"data": {"sub1": [{"in-list": "test"}]}},
                "headers": None,
                "cookies": None,
                "timeout": 10,
            },
        )

    def test_subst_none(self):
        self._test_notify_sync(
            {
                "name": "test name",
                "url": "https://example.com/",
                "json": {"msg": "${subject}\n${body}", "token": "${token}"},
                "secrets": {"token": "someSecretToken"},
            },
            expected_call={
                "method": "POST",
                "url": "https://example.com/",
                "params": None,
                "data": None,
                "json": {"msg": "null\ntest", "token": "someSecretToken"},
                "headers": None,
                "cookies": None,
                "timeout": 10,
            },
            subject=None,
        )

    def test_is_picklable(self):
        reload_modules()
        block = CustomWebhookNotificationBlock.validate(
            {
                "name": "test name",
                "url": "https://example.com/",
                "json": {"msg": "${subject}\n${body}", "token": "${token}"},
                "secrets": {"token": "someSecretToken"},
            }
        )
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, CustomWebhookNotificationBlock)

    def test_invalid_key_raises_validation_error(self):
        with pytest.raises(KeyError):
            CustomWebhookNotificationBlock.validate(
                {
                    "name": "test name",
                    "url": "https://example.com/",
                    "json": {"msg": "${subject}\n${body}", "token": "${token}"},
                    "secrets": {"token2": "someSecretToken"},
                }
            )

    def test_provide_both_data_and_json_raises_validation_error(self):
        with pytest.raises(ValueError):
            CustomWebhookNotificationBlock.validate(
                {
                    "name": "test name",
                    "url": "https://example.com/",
                    "data": {"msg": "${subject}\n${body}", "token": "${token}"},
                    "json": {"msg": "${subject}\n${body}", "token": "${token}"},
                    "secrets": {"token": "someSecretToken"},
                }
            )

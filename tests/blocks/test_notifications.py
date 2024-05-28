import urllib
from typing import Type
from unittest.mock import patch

import cloudpickle
import pytest
import respx

from prefect.blocks.notifications import (
    PREFECT_NOTIFY_TYPE_DEFAULT,
    AppriseNotificationBlock,
    CustomWebhookNotificationBlock,
    DiscordWebhook,
    MattermostWebhook,
    OpsgenieWebhook,
    PagerDutyWebHook,
    SendgridEmail,
    TwilioSMS,
)
from prefect.flows import flow
from prefect.testing.utilities import AsyncMock

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
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = block_class(url="https://example.com/notification")
            await block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                block.url.get_secret_value()
            )

            notify_type = PREFECT_NOTIFY_TYPE_DEFAULT
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=notify_type
            )

    def test_notify_sync(self, block_class: Type[AppriseNotificationBlock]):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = block_class(url="https://example.com/notification")

            @flow
            def test_flow():
                block.notify("test")

            test_flow()

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                block.url.get_secret_value()
            )
            apprise_instance_mock.async_notify.assert_called_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_is_picklable(self, block_class: Type[AppriseNotificationBlock]):
        block = block_class(url="http://example.com/notification")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, block_class)


class TestMattermostWebhook:
    async def test_notify_async(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
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
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_notify_sync(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            mm_block = MattermostWebhook(hostname="example.com", token="token")

            @flow
            def test_flow():
                mm_block.notify("test")

            test_flow()

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"mmost://{mm_block.hostname}/{mm_block.token.get_secret_value()}/"
                "?image=no&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )
            apprise_instance_mock.async_notify.assert_called_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_notify_with_multiple_channels(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            mm_block = MattermostWebhook(
                hostname="example.com",
                token="token",
                channels=["general", "death-metal-anonymous"],
            )

            @flow
            def test_flow():
                mm_block.notify("test")

            test_flow()

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"mmost://{mm_block.hostname}/{mm_block.token.get_secret_value()}/"
                "?image=no&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
                "&channel=death-metal-anonymous%2Cgeneral"
            )

            apprise_instance_mock.async_notify.assert_called_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_is_picklable(self):
        block = MattermostWebhook(token="token", hostname="example.com")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, MattermostWebhook)


class TestDiscordWebhook:
    async def test_notify_async(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            discord_block = DiscordWebhook(
                webhook_id="123456",
                webhook_token="abc123EFG",
            )
            await discord_block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"discord://{discord_block.webhook_id.get_secret_value()}/{discord_block.webhook_token.get_secret_value()}/"
                "?tts=no&avatar=no&footer=no&footer_logo=yes&image=no&fields=yes&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_notify_sync(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            discord_block = DiscordWebhook(
                webhook_id="123456", webhook_token="abc123EFG"
            )

            @flow
            def test_flow():
                discord_block.notify("test")

            test_flow()

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"discord://{discord_block.webhook_id.get_secret_value()}/{discord_block.webhook_token.get_secret_value()}/"
                "?tts=no&avatar=no&footer=no&footer_logo=yes&image=no&fields=yes&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )
            apprise_instance_mock.async_notify.assert_called_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_is_picklable(self):
        block = DiscordWebhook(webhook_id="123456", webhook_token="abc123EFG")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, DiscordWebhook)


class TestOpsgenieWebhook:
    API_KEY = "api_key"

    async def test_notify_async(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
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
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def _test_notify_sync(self, targets="", params=None, **kwargs):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            if params is None:
                params = "region=us&priority=normal&batch=no"

            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = OpsgenieWebhook(apikey=self.API_KEY, **kwargs)

            @flow
            def test_flow():
                block.notify("test")

            test_flow()

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                f"opsgenie://{self.API_KEY}/{targets}/?{params}"
                "&format=text&overflow=upstream&rto=4.0&cto=4.0&verify=yes"
            )

            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
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
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = PagerDutyWebHook(integration_key="int_key", api_key="api_key")

            @flow
            def test_flow():
                block.notify("test")

            test_flow()

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
                notify_type=PREFECT_NOTIFY_TYPE_DEFAULT,
            )

    def test_twilio_notify_sync(self, valid_apprise_url):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            client_instance_mock = AppriseMock.return_value
            client_instance_mock.async_notify = AsyncMock()

            twilio_sms_block = TwilioSMS(
                account_sid="ACabcdefabcdefabcdefabcdef",
                auth_token="XXXXXXXXXXXXXXXXXXXXXXXX",
                from_phone_number="+15555555555",
                to_phone_numbers=["+15555555556", "+15555555557"],
            )

            @flow
            def test_flow():
                twilio_sms_block.notify("hello from prefect")

            test_flow()

            AppriseMock.assert_called_once()
            client_instance_mock.add.assert_called_once_with(valid_apprise_url)

            client_instance_mock.async_notify.assert_awaited_once_with(
                body="hello from prefect",
                title=None,
                notify_type=PREFECT_NOTIFY_TYPE_DEFAULT,
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
    async def test_notify_async(self):
        with respx.mock as xmock:
            xmock.post("https://example.com/")

            custom_block = CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                secrets={"token": "someSecretToken"},
            )
            await custom_block.notify("test", "subject")

            last_req = xmock.calls.last.request
            assert last_req.headers["user-agent"] == "Prefect Notifications"
            assert (
                last_req.content
                == b'{"msg": "subject\\ntest", "token": "someSecretToken"}'
            )
            assert last_req.extensions == {
                "timeout": {"connect": 10, "pool": 10, "read": 10, "write": 10}
            }

    def test_notify_sync(self):
        with respx.mock as xmock:
            xmock.post("https://example.com/")

            custom_block = CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                secrets={"token": "someSecretToken"},
            )

            @flow
            def test_flow():
                custom_block.notify("test", "subject")

            test_flow()

            last_req = xmock.calls.last.request
            assert last_req.headers["user-agent"] == "Prefect Notifications"
            assert (
                last_req.content
                == b'{"msg": "subject\\ntest", "token": "someSecretToken"}'
            )
            assert last_req.extensions == {
                "timeout": {"connect": 10, "pool": 10, "read": 10, "write": 10}
            }

    async def test_user_agent_override(self):
        with respx.mock as xmock:
            xmock.post("https://example.com/")

            custom_block = CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                headers={"user-agent": "CustomUA"},
                json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                secrets={"token": "someSecretToken"},
            )
            await custom_block.notify("test", "subject")

            last_req = xmock.calls.last.request
            assert last_req.headers["user-agent"] == "CustomUA"
            assert (
                last_req.content
                == b'{"msg": "subject\\ntest", "token": "someSecretToken"}'
            )
            assert last_req.extensions == {
                "timeout": {"connect": 10, "pool": 10, "read": 10, "write": 10}
            }

    async def test_timeout_override(self):
        with respx.mock as xmock:
            xmock.post("https://example.com/")

            custom_block = CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                secrets={"token": "someSecretToken"},
                timeout=30,
            )
            await custom_block.notify("test", "subject")

            last_req = xmock.calls.last.request
            assert (
                last_req.content
                == b'{"msg": "subject\\ntest", "token": "someSecretToken"}'
            )
            assert last_req.extensions == {
                "timeout": {"connect": 30, "pool": 30, "read": 30, "write": 30}
            }

    async def test_request_cookie(self):
        with respx.mock as xmock:
            xmock.post("https://example.com/")

            custom_block = CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                cookies={"key": "{{cookie}}"},
                secrets={"token": "someSecretToken", "cookie": "secretCookieValue"},
                timeout=30,
            )
            await custom_block.notify("test", "subject")

            last_req = xmock.calls.last.request
            assert last_req.headers["cookie"] == "key=secretCookieValue"
            assert (
                last_req.content
                == b'{"msg": "subject\\ntest", "token": "someSecretToken"}'
            )
            assert last_req.extensions == {
                "timeout": {"connect": 30, "pool": 30, "read": 30, "write": 30}
            }

    async def test_subst_nested_list(self):
        with respx.mock as xmock:
            xmock.post("https://example.com/")

            custom_block = CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                json_data={
                    "data": {"sub1": [{"in-list": "{{body}}", "name": "{{name}}"}]}
                },
                secrets={"token": "someSecretToken"},
            )
            await custom_block.notify("test", "subject")

            last_req = xmock.calls.last.request
            assert last_req.headers["user-agent"] == "Prefect Notifications"
            assert (
                last_req.content
                == b'{"data": {"sub1": [{"in-list": "test", "name": "test name"}]}}'
            )
            assert last_req.extensions == {
                "timeout": {"connect": 10, "pool": 10, "read": 10, "write": 10}
            }

    async def test_subst_none(self):
        with respx.mock as xmock:
            xmock.post("https://example.com/")

            custom_block = CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                secrets={"token": "someSecretToken"},
            )
            # subject=None
            await custom_block.notify("test", None)

            last_req = xmock.calls.last.request
            assert last_req.headers["user-agent"] == "Prefect Notifications"
            assert (
                last_req.content
                == b'{"msg": "null\\ntest", "token": "someSecretToken"}'
            )
            assert last_req.extensions == {
                "timeout": {"connect": 10, "pool": 10, "read": 10, "write": 10}
            }

    def test_is_picklable(self):
        block = CustomWebhookNotificationBlock(
            name="test name",
            url="https://example.com/",
            json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
            secrets={"token": "someSecretToken"},
        )
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, CustomWebhookNotificationBlock)

    def test_invalid_key_raises_validation_error(self):
        with pytest.raises(KeyError):
            CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                secrets={"token2": "someSecretToken"},
            )

    def test_provide_both_data_and_json_raises_validation_error(self):
        with pytest.raises(ValueError):
            CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                form_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                secrets={"token": "someSecretToken"},
            )


class TestSendgridEmail:
    URL_PARAMS = {
        # default notify format
        "format": "html",
        # default overflow mode
        "overflow": "upstream",
        # socket read timeout
        "rto": 4.0,
        # socket connect timeout
        "cto": 4.0,
        # ssl certificate authority verification
        "verify": "yes",
    }

    async def test_notify_async(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            sg_block = SendgridEmail(
                api_key="test-api-key",
                sender_email="test@gmail.com",
                to_emails=["test1@gmail.com", "test2@gmail.com"],
            )
            await sg_block.notify("test")

            # check if the apprise object is created
            AppriseMock.assert_called_once()

            # check if the Apprise().add function is called with correct url
            url = f"sendgrid://{sg_block.api_key.get_secret_value()}:{sg_block.sender_email}/"
            url += "/".join(
                [urllib.parse.quote(email, safe="") for email in sg_block.to_emails]
            )

            url += "?"
            url += urllib.parse.urlencode(TestSendgridEmail.URL_PARAMS)

            apprise_instance_mock.add.assert_called_once_with(url)
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_notify_sync(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            sg_block = SendgridEmail(
                api_key="test-api-key",
                sender_email="test@gmail.com",
                to_emails=["test1@gmail.com", "test2@gmail.com"],
            )

            @flow
            def test_flow():
                sg_block.notify("test")

            test_flow()

            # check if the Apprise().add function is called with correct url
            url = f"sendgrid://{sg_block.api_key.get_secret_value()}:{sg_block.sender_email}/"
            url += "/".join(
                [urllib.parse.quote(email, safe="") for email in sg_block.to_emails]
            )
            url += "?"
            url += urllib.parse.urlencode(TestSendgridEmail.URL_PARAMS)

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(url)
            apprise_instance_mock.async_notify.assert_called_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_is_picklable(self):
        block = SendgridEmail(
            api_key="test-api-key",
            sender_email="test@gmail.com",
            to_emails=["test1@gmail.com", "test2@gmail.com"],
        )
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, SendgridEmail)

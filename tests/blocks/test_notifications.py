import urllib
from typing import Type
from unittest.mock import call, patch

import cloudpickle
import pytest
import respx

from prefect.blocks.abstract import NotificationError
from prefect.blocks.notifications import (
    PREFECT_NOTIFY_TYPE_DEFAULT,
    AppriseNotificationBlock,
    CustomWebhookNotificationBlock,
    DiscordWebhook,
    MattermostWebhook,
    MicrosoftTeamsWebhook,
    OpsgenieWebhook,
    PagerDutyWebHook,
    SendgridEmail,
    TwilioSMS,
)
from prefect.flows import flow
from prefect.testing.utilities import AsyncMock

# A list of the notification classes Pytest should use as parameters to each method in TestAppriseNotificationBlock
notification_classes = sorted(
    [
        cls
        for cls in AppriseNotificationBlock.__subclasses__()
        if cls != MicrosoftTeamsWebhook
    ],
    key=lambda cls: cls.__name__,
)

RESTRICTED_URLS = [
    ("", ""),
    (" ", ""),
    ("[]", ""),
    ("not a url", ""),
    ("http://", ""),
    ("https://", ""),
    ("ftp://example.com", "HTTP and HTTPS"),
    ("gopher://example.com", "HTTP and HTTPS"),
    ("https://localhost", "private address"),
    ("https://127.0.0.1", "private address"),
    ("https://[::1]", "private address"),
    ("https://[fc00:1234:5678:9abc::10]", "private address"),
    ("https://[fd12:3456:789a:1::1]", "private address"),
    ("https://[fe80::1234:5678:9abc]", "private address"),
    ("https://10.0.0.1", "private address"),
    ("https://10.255.255.255", "private address"),
    ("https://172.16.0.1", "private address"),
    ("https://172.31.255.255", "private address"),
    ("https://192.168.1.1", "private address"),
    ("https://192.168.1.255", "private address"),
    ("https://169.254.0.1", "private address"),
    ("https://169.254.169.254", "private address"),
    ("https://169.254.254.255", "private address"),
    # These will resolve to a private address in production, but not in tests,
    # so we'll use "resolve" as the reason to catch both cases
    ("https://metadata.google.internal", "resolve"),
    ("https://anything.privatecloud", "resolve"),
    ("https://anything.privatecloud.svc", "resolve"),
    ("https://anything.privatecloud.svc.cluster.local", "resolve"),
    ("https://cluster-internal", "resolve"),
    ("https://network-internal.cloud.svc", "resolve"),
    ("https://private-internal.cloud.svc.cluster.local", "resolve"),
]


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
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
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
        block = block_class(url="https://example.com/notification")
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, block_class)

    @pytest.mark.parametrize("value, reason", RESTRICTED_URLS)
    async def test_notification_can_prevent_restricted_urls(
        self, block_class, value: str, reason: str
    ):
        notification = block_class(url=value, allow_private_urls=False)

        with pytest.raises(ValueError, match=f"is not a valid URL.*{reason}"):
            await notification.notify(subject="example", body="example")

    async def test_raises_on_url_validation_failure(self, block_class):
        """
        When within a raise_on_failure block, we want URL validation errors to be
        wrapped and captured as NotificationErrors for reporting back to users.
        """
        block = block_class(url="https://127.0.0.1/foo/bar", allow_private_urls=False)

        # outside of a raise_on_failure block, we get a ValueError directly
        with pytest.raises(ValueError, match="not a valid URL") as captured:
            await block.notify(subject="Test", body="Test")

        # inside of a raise_on_failure block, we get a NotificationError
        with block.raise_on_failure():
            with pytest.raises(NotificationError) as captured:
                await block.notify(subject="Test", body="Test")

        assert captured.value.log == (
            "'https://127.0.0.1/foo/bar' is not a valid URL.  It resolves to the "
            "private address 127.0.0.1."
        )


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
                "?image=yes&format=text&overflow=upstream"
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
                "?image=no&format=text&overflow=upstream"
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
                "?image=no&format=text&overflow=upstream"
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
                "?tts=no&avatar=no&footer=no&footer_logo=yes&image=no&fields=yes&format=text&overflow=upstream"
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
                "?tts=no&avatar=no&footer=no&footer_logo=yes&image=no&fields=yes&format=text&overflow=upstream"
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
                f"opsgenie://{self.API_KEY}//?action=map&region=us&priority=normal&"
                "batch=no&%3Ainfo=note&%3Asuccess=close&%3Awarning=new&%3Afailure="
                "new&format=text&overflow=upstream"
            )

            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def _test_notify_sync(self, targets="", params=None, **kwargs):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            if params is None:
                params = "action=map&region=us&priority=normal&batch=no"

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
                "&%3Ainfo=note&%3Asuccess=close&%3Awarning=new&%3Afailure=new&format=text&overflow=upstream"
            )

            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_notify_sync_simple(self):
        self._test_notify_sync()

    def test_notify_sync_params(self):
        params = "action=map&region=eu&priority=low&batch=yes"
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
        params = "action=map&region=us&priority=normal&batch=no&%2Bkey1=value1&%2Bkey2=value2"
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
                "image=yes&format=text&overflow=upstream"
            )

            notify_type = "info"
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=notify_type
            )

    async def test_notify_async_with_subject(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = PagerDutyWebHook(integration_key="int_key", api_key="api_key")
            await block.notify("test", "test")

            apprise_instance_mock.add.assert_has_calls(
                [
                    call(
                        "pagerduty://int_key@api_key/Prefect/Notification?region=us"
                        "&image=yes&format=text&overflow=upstream"
                    ),
                    call(
                        "pagerduty://int_key@api_key/Prefect/Notification?region=us"
                        "&image=yes&%2BPrefect+Notification+Body=test&format=text&overflow=upstream"
                    ),
                ],
                any_order=False,
            )

            notify_type = "info"
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body=" ", title="test", notify_type=notify_type
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
                "image=yes&format=text&overflow=upstream"
            )

            notify_type = "info"
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=notify_type
            )

    def test_notify_sync_with_subject(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = PagerDutyWebHook(integration_key="int_key", api_key="api_key")

            @flow
            def test_flow():
                block.notify("test", "test")

            test_flow()

            apprise_instance_mock.add.assert_has_calls(
                [
                    call(
                        "pagerduty://int_key@api_key/Prefect/Notification?region=us"
                        "&image=yes&format=text&overflow=upstream"
                    ),
                    call(
                        "pagerduty://int_key@api_key/Prefect/Notification?region=us"
                        "&image=yes&%2BPrefect+Notification+Body=test&format=text&overflow=upstream"
                    ),
                ],
                any_order=False,
            )

            notify_type = "info"
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body=" ", title="test", notify_type=notify_type
            )


class TestTwilioSMS:
    @pytest.fixture
    def valid_apprise_url(self) -> str:
        return (
            "twilio://ACabcdefabcdefabcdefabcdef"
            ":XXXXXXXXXXXXXXXXXXXXXXXX"
            "@%2B15555555555/%2B15555555556/%2B15555555557/"
            "?format=text&overflow=upstream"
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
            xmock.route(host="localhost").pass_through()

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
            xmock.route(host="localhost").pass_through()

            custom_block = CustomWebhookNotificationBlock(
                name="test name",
                url="https://example.com/",
                json_data={"msg": "{{subject}}\n{{body}}", "token": "{{token}}"},
                secrets={"token": "someSecretToken"},
            )

            custom_block.notify("test", "subject")

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


class TestMicrosoftTeamsWebhook:
    SAMPLE_URL = "https://prod-NO.LOCATION.logic.azure.com:443/workflows/WFID/triggers/manual/paths/invoke?sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=SIGNATURE"

    async def test_notify_async(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = MicrosoftTeamsWebhook(url=self.SAMPLE_URL)
            await block.notify("test")

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                "workflow://prod-NO.LOCATION.logic.azure.com:443/WFID/SIGNATURE/"
                "?image=yes&wrap=yes"
                "&format=markdown&overflow=upstream"
            )
            apprise_instance_mock.async_notify.assert_awaited_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_notify_sync(self):
        with patch("apprise.Apprise", autospec=True) as AppriseMock:
            apprise_instance_mock = AppriseMock.return_value
            apprise_instance_mock.async_notify = AsyncMock()

            block = MicrosoftTeamsWebhook(url=self.SAMPLE_URL)

            @flow
            def test_flow():
                block.notify("test")

            test_flow()

            AppriseMock.assert_called_once()
            apprise_instance_mock.add.assert_called_once_with(
                "workflow://prod-NO.LOCATION.logic.azure.com:443/WFID/SIGNATURE/"
                "?image=yes&wrap=yes"
                "&format=markdown&overflow=upstream"
            )
            apprise_instance_mock.async_notify.assert_called_once_with(
                body="test", title=None, notify_type=PREFECT_NOTIFY_TYPE_DEFAULT
            )

    def test_is_picklable(self):
        block = MicrosoftTeamsWebhook(url=self.SAMPLE_URL)
        pickled = cloudpickle.dumps(block)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, MicrosoftTeamsWebhook)

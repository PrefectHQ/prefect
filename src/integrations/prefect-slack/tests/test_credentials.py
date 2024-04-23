from prefect_slack import SlackCredentials, SlackWebhook
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.webhook.async_client import AsyncWebhookClient


def test_slack_credentials():
    assert type(SlackCredentials(token="xoxb-xxxx").get_client()) is AsyncWebClient


def test_slack_webhook():
    assert (
        type(SlackWebhook(url="https://hooks.slack.com/xxxx").get_client())
        is AsyncWebhookClient
    )

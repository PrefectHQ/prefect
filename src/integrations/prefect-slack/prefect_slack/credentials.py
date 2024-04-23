"""Credential classes used to perform authenticated interacting with Slack"""
from dataclasses import dataclass

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.webhook.async_client import AsyncWebhookClient


@dataclass
class SlackCredentials:
    """
    Class for holding Slack credentials for use in tasks and flows.

    Args:
        token: Bot user OAuth token for the Slack app used to perform actions.
    """

    token: str

    def get_client(self) -> AsyncWebClient:
        """
        Returns an authenticated `AsyncWebClient` to interact with the Slack API.
        """
        return AsyncWebClient(token=self.token)


@dataclass
class SlackWebhook:
    """
    Class holding a Slack webhook for use in tasks and flows.

    Args:
        url: Slack webhook URL which can be used to send messages
            (e.g. `https://hooks.slack.com/XXX`).
    """

    url: str

    def get_client(self) -> AsyncWebhookClient:
        """
        Returns and authenticated `AsyncWebhookClient` to interact with the configured
        Slack webhook.
        """
        return AsyncWebhookClient(url=self.url)

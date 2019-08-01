from typing import Any, cast

import requests

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class SlackTask(Task):
    """
    Task for sending a message via Slack.  For this task to function properly,
    you must have a Prefect Secret set which stores your Slack webhook URL.  For installing the Prefect App,
    please see these [installation instructions](https://docs.prefect.io/guide/tutorials/slack-notifications.html#installation-instructions).

    Args:
        - message (str, optional): the message to send; can also be provided at runtime
        - webhook_secret (str, optional): the name of the Prefect Secret which stores your slack webhook URL;
            defaults to `"SLACK_WEBHOOK_URL"`
        - **kwargs (Any, optional): additional keyword arguments to pass to the base Task initialization
    """

    def __init__(
        self,
        message: str = None,
        webhook_secret: str = "SLACK_WEBHOOK_URL",
        **kwargs: Any
    ):
        self.message = message
        self.webhook_secret = webhook_secret
        super().__init__(**kwargs)

    @defaults_from_attrs("message")
    def run(self, message: str = None) -> None:
        """
        Run method which sends a Slack message.

        Args:
            - message (str, optional): the message to send; if not provided here, will use the value provided
                at initialization

        Returns:
            - None
        """

        webhook_url = cast(str, Secret(self.webhook_secret).get())
        r = requests.post(webhook_url, json={"text": message})
        r.raise_for_status()

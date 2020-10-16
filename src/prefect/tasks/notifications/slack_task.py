from typing import Any, cast, Union

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class SlackTask(Task):
    """
    Task for sending a message via Slack.  For this task to function properly, you must have a
    Prefect Secret set which stores your Slack webhook URL.  For installing the Prefect App,
    please see these [installation
    instructions](https://docs.prefect.io/core/advanced_tutorials/slack-notifications.html#installation-instructions).

    Args:
        - message (str, optional): the message to send as either a dictionary or a plain
            string; can also be provided at runtime
        - webhook_secret (str, optional): the name of the Prefect Secret which stores your
            slack webhook URL; defaults to `"SLACK_WEBHOOK_URL"`
        - **kwargs (Any, optional): additional keyword arguments to pass to the base Task
            initialization
    """

    def __init__(
        self,
        message: Union[str, dict] = None,
        webhook_secret: str = "SLACK_WEBHOOK_URL",
        **kwargs: Any
    ):
        self.message = message
        self.webhook_secret = webhook_secret
        super().__init__(**kwargs)

    @defaults_from_attrs("message", "webhook_secret")
    def run(
        self,
        message: Union[str, dict] = None,
        webhook_secret: str = None,
        webhook_url: str = None,
    ) -> None:
        """
        Run method which sends a Slack message.

        Args:
            - message (Union[str,dict], optional): the message to send as either a dictionary
                or a plain string; if not provided here, will use the value provided at
                initialization
            - webhook_secret (str, optional): the name of the Prefect Secret which stores your
                slack webhook URL; defaults to `"SLACK_WEBHOOK_URL"`; if not provided here,
                will use the value provided at initialization
            - webhook_url (str, optional): the value of a Slack webhook URL that is returned from an
                upstream `PrefectSecret` task. If specified then the `webhook_secret` will not be used.

        Returns:
            - None
        """
        # 'import requests' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import requests

        webhook_url = webhook_url or cast(str, Secret(webhook_secret).get())
        r = requests.post(
            webhook_url,
            json=message if isinstance(message, dict) else {"text": message},
        )
        r.raise_for_status()

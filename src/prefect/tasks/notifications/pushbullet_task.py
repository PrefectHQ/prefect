from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs
from typing import Any
from pushbullet import Pushbullet


class PushbulletTask(Task):
    """
    Task for sending a notification to a mobile phone (or other device) using pushbullet. For this task to function properly,
    you must have the `"PUSHBULLET_TOKEN"` Prefect Secret set. You can set up a pushbullet account and/or get a token here: https://www.pushbullet.com/#settings/account

    Args:
        - msg(str, optional):  The message you want to send to your phone; can also be provided at runtime.
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task init method
    """

    def __init__(self, msg: str = None, **kwargs: Any):
        self.msg = msg
        super().__init__(**kwargs)

    @defaults_from_attrs("msg")
    def run(self, msg: str = None) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a Flow context,
        or by using `Task.bind`.

        Args:
            - msg (str): The message you want sent to your phone; defaults to the one provided
                at initialization

        Raises:
            - None

        Returns:
            - None
        """

        pbtoken = Secret("PUSHBULLET_TOKEN").get()

        pb = Pushbullet(pbtoken)

        ## send the request
        pb.push_note("Flow Notification", msg)

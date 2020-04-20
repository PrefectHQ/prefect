

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs

class PushBulletTask(Task):
    """
    Task for sending a notification to a mobile phone (or other device) using pushbullet. For this task to function properly,
    you must have the `"PUSHBULLET_TOKEN"` Prefect Secret set. You can set up a pushbullet account token here: https://www.pushbullet.com/#settings/account

    Args:
        - msg(str, optional):  The message you want to send to your phone; can also be provided at runtime.
    """

    def __init__(
        self,
        msg: str = None
    ):
        self.msg = msg
        super().__init__(*args, **kwargs)

    @defaults_from_attrs("msg")
    def run(
        self,
        msg: str = None
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a Flow context,
        or by using `Task.bind`.

        Args:
            - msg (str): The message you want sent to your phone; defaults to the one provided
                at initialization

        Raises:
            - HTTPError: if the POST request returns a non-200 status code

        Returns:
            - None
        """

        # 'import  is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        from pushbullet import Pushbullet

        pbtoken = cast(str, Secret("PUSHBULLET_TOKEN").get())
        pb = Pushbullet(pbtoken)

        
        ## send the request
        resp = pb.push_note('Flow Notification', msg)
        print('resp', resp)
        resp.raise_for_status()

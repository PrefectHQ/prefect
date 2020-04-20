from pushbullet import Pushbullet

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs

pb = Pushbullet(creds['pushbullet']['token'])


def sendPushBulletOnFail(task, old_state, new_state):
    if new_state.is_failed():
        msg = "{0} failed in state {1}".format(task, new_state)
        pb.push_note('Flow Error', msg)
    return new_state
t = Task(state_handlers=[sendPushBulletOnFail])


class SendPushBulletNotification(Task):
    """
    Task for sending a notification to a mobile phone using pushbullet. For this task to function properly,
    you must have the `"PUSHBULLET_TOKEN"` Prefect Secret set. 

    Args:
        - msg(str, optional):  The message you want to send to your phone.
    """

    def __init__(
        self,
        msg: str = None
    ):
        self.repo = repo
        self.title = title
        self.body = body
        self.labels = labels or []
        if token_secret is not None:
            warnings.warn(
                "The `token` argument is deprecated. Use a `Secret` task "
                "to pass the credentials value at runtime instead.",
                UserWarning,
            )
        self.token_secret = token_secret
        super().__init__(**kwargs)

    @defaults_from_attrs("repo", "title", "body", "labels")
    def run(
        self,
        repo: str = None,
        title: str = None,
        body: str = None,
        labels: List[str] = None,
        token: str = None,
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a Flow context,
        or by using `Task.bind`.

        Args:
            - repo (str, optional): the name of the repository to open the issue in; must be provided in the
                form `organization/repo_name`; defaults to the one provided at initialization
            - title (str, optional): the title of the issue to create; defaults to the one provided at initialization
            - body (str, optional): the contents of the issue; defaults to the one provided at initialization
            - labels (List[str], optional): a list of labels to apply to the newly opened issues; defaults to
            the ones provided at initialization
            - token (str): a GitHub API token

        Raises:
            - ValueError: if a `repo` was never provided
            - HTTPError: if the POST request returns a non-200 status code

        Returns:
            - None
        """
        if repo is None:
            raise ValueError("A GitHub repository must be provided.")

        ## prepare the request
        if token is None:
            warnings.warn(
                "The `token` argument is deprecated. Use a `Secret` task "
                "to pass the credentials value at runtime instead.",
                UserWarning,
            )
            token = Secret(self.token_secret).get()

        # 'import requests' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import requests

        url = "https://api.github.com/repos/{}/issues".format(repo)
        headers = {
            "AUTHORIZATION": "token {}".format(token),
            "Accept": "application/vnd.github.v3+json",
        }
        issue = {"title": title, "body": body, "labels": labels}

        ## send the request
        resp = requests.post(url, data=json.dumps(issue), headers=headers)
        resp.raise_for_status()

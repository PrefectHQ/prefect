import json
from typing import Any

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class CreateGitHubPR(Task):
    """
    Task for opening/creating new GitHub Pull Requests using the v3 version of the GitHub REST API.

    Args:
        - repo (str, optional): the name of the repository to open the issue in; must be
            provided in the form `organization/repo_name`; can also be provided to the `run`
            method
        - title (str, optional): the title of the issue to create; can also be provided to the
            `run` method
        - body (str, optional): the contents of the issue; can also be provided to the `run` method
        - head (str, optional): the name of the branch where your changes are implemented; can also
            be provided to the `run` method
        - base (str, optional): the name of the branch you want the changes pulled into; can also
            be provided to the `run` method
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method
    """

    def __init__(
        self,
        repo: str = None,
        title: str = None,
        body: str = None,
        head: str = None,
        base: str = None,
        **kwargs: Any
    ):
        self.repo = repo
        self.title = title
        self.body = body
        self.head = head
        self.base = base
        super().__init__(**kwargs)

    @defaults_from_attrs("repo", "title", "body", "head", "base")
    def run(
        self,
        repo: str = None,
        title: str = None,
        body: str = None,
        head: str = None,
        base: str = None,
        token: str = None,
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a
        Flow context, or by using `Task.bind`.

        Args:
            - repo (str, optional): the name of the repository to open the issue in; must be
                provided in the form `organization/repo_name`; defaults to the one provided at
                initialization
            - title (str, optional): the title of the issue to create; defaults to the one
                provided at initialization
            - body (str, optional): the contents of the issue; defaults to the one provided at
                initialization
            - head (str, optional): the name of the branch where your changes are implemented;
                defaults to the one provided at initialization
            - base (str, optional): the name of the branch you want the changes pulled into;
                defaults to the one provided at initialization
            - token (str): a GitHub API token

        Raises:
            - ValueError: if a `repo` was never provided
            - HTTPError: if the POST request returns a non-200 status code

        Returns:
            - None
        """
        if repo is None:
            raise ValueError("A GitHub repository must be provided.")

        # 'import requests' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import requests

        url = "https://api.github.com/repos/{}/pulls".format(repo)
        headers = {
            "AUTHORIZATION": "token {}".format(token),
            "Accept": "application/vnd.github.v3+json",
        }
        pr = {"title": title, "body": body, "head": head, "base": base}

        # send the request
        resp = requests.post(url, data=json.dumps(pr), headers=headers)
        resp.raise_for_status()

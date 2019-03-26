import json
from typing import Any, List

import requests

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class OpenGitHubIssue(Task):
    """
    Task for opening / creating new GitHub issues using the v3 version of the GitHub REST API.

    Args:
        - repo (str, optional): the name of the repository to open the issue in; must be provided in the
            form `organization/repo_name`; can also be provided to the `run` method
        - title (str, optional): the title of the issue to create; can also be provided to the `run` method
        - body (str, optional): the contents of the issue; can also be provided to the `run` method
        - labels (List[str], optional): a list of labels to apply to the newly opened issues; can also
            be provided to the `run` method
        - token_secret (str, optional): the name of the Prefect Secret containing your GitHub Access Token;
            defaults to "GITHUB_ACCESS_TOKEN"
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task init method
    """

    def __init__(
        self,
        repo: str = None,
        title: str = None,
        body: str = None,
        labels: List[str] = None,
        token_secret: str = "GITHUB_ACCESS_TOKEN",
        **kwargs: Any
    ):
        self.repo = repo
        self.title = title
        self.body = body
        self.labels = labels or []
        self.token_secret = token_secret
        super().__init__(**kwargs)

    @defaults_from_attrs("repo", "title", "body", "labels")
    def run(
        self,
        repo: str = None,
        title: str = None,
        body: str = None,
        labels: List[str] = None,
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a Flow context,
        or by using `Task.bind`.

        Args:
            - repo (str, optional): the name of the repository to open the issue in; must be provided in the
                form `organization/repo_name`; defaults to the one provided at initialization
            - title (str, optional): the title of the issue to create; defaults to the one provided at initialization
            - body (str, optional): the contents of the issue; defaults to the one provided at initialization
            - labels (List[str], optional): a list of labels to apply to the newly opened issues; defaults to the ones provided
                at initialization

        Raises:
            - ValueError: if a `repo` was never provided
            - HTTPError: if the POST request returns a non-200 status code

        Returns:
            - None
        """
        if repo is None:
            raise ValueError("A GitHub repository must be provided.")

        ## prepare the request
        token = Secret(self.token_secret).get()
        url = "https://api.github.com/repos/{}/issues".format(repo)
        headers = {
            "AUTHORIZATION": "token {}".format(token),
            "Accept": "application/vnd.github.v3+json",
        }
        issue = {"title": title, "body": body, "labels": labels}

        ## send the request
        resp = requests.post(url, data=json.dumps(issue), headers=headers)
        resp.raise_for_status()

import json
from typing import Any

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class CreateIssueComment(Task):
    """
    Task for creating a comment on the specified GitHub issue using the v3 version of the
    GitHub REST API.

    Args:
        - repo (str, optional): the name of the repository to create the comment in; must be
            provided in the form `organization/repo_name`; can also be provided to the `run`
            method
        - issue_number (int, optional): the ID of the issue to create the comment on.
        - body (str, optional): the body of the comment; can also be provided to the `run` method
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method

    References:
        - See: [Create an issue
            comment](https://developer.github.com/v3/issues/comments/#create-an-issue-comment)
    """

    def __init__(
        self,
        repo: str = None,
        issue_number: int = None,
        body: str = None,
        **kwargs: Any
    ):
        self.repo = repo
        self.issue_number = issue_number
        self.body = body
        super().__init__(**kwargs)

    @defaults_from_attrs("repo", "issue_number", "body")
    def run(
        self,
        repo: str = None,
        issue_number: int = None,
        body: str = None,
        token: str = None,
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a
        Flow context, or by using `Task.bind`.

        Args:
            - repo (str, optional): the name of the repository to create the comment in; must be
                provided in the form `organization/repo_name`; can also be provided to the `run`
                method
            - issue_number (int, optional): the ID of the issue to create the comment on.
            - body (str, optional): the body of the comment; can also be provided to the `run` method
            - token (str): a GitHub API token

        Raises:
            - ValueError: if a `repo` or an `issue_number` was never provided
            - HTTPError: if the POST request returns a non-200 status code

        Returns:
            - None
        """
        if repo is None:
            raise ValueError("A GitHub repository must be provided.")

        if issue_number is None:
            raise ValueError("An issue number must be provided")

        # 'import requests' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import requests

        url = "https://api.github.com/repos/{}/issues/{}/comments".format(
            repo, issue_number
        )
        headers = {
            "AUTHORIZATION": "token {}".format(token),
            "Accept": "application/vnd.github.v3+json",
        }
        issue = {"body": body}

        # send the request
        resp = requests.post(url, data=json.dumps(issue), headers=headers)
        resp.raise_for_status()

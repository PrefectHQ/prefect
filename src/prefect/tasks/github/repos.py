import json
import requests
from typing import Any, List

from prefect import Task
from prefect.client import Secret
from prefect.utilities.tasks import defaults_from_attrs


class GetRepoInfo(Task):
    """
    Task for retrieving GitHub repository information using the v3 version of the GitHub REST API.

    Args:
        - repo (str, optional): the name of the repository to open the issue in; must be provided in the
            form `organization/repo_name` or `user/repo_name`; can also be provided to the `run` method
        - info_keys (List[str], optional): a list of repo attributes to pull (e.g., `["stargazers_count", "subscribers_count"]`).
            A full list of available keys can be found in the official [GitHub documentation](https://developer.github.com/v3/repos/)
        - token_secret (str, optional): the name of the Prefect Secret containing your GitHub Access Token;
            defaults to "GITHUB_ACCESS_TOKEN"
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task init method
    """

    def __init__(
        self,
        repo: str = None,
        info_keys: List[str] = None,
        token_secret: str = "GITHUB_ACCESS_TOKEN",
        **kwargs: Any
    ):
        self.repo = repo
        self.info_keys = info_keys or []
        self.token_secret = token_secret
        super().__init__(**kwargs)

    @defaults_from_attrs("repo", "info_keys")
    def run(self, repo: str = None, info_keys: List[str] = None) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a Flow context,
        or by using `Task.bind`.

        Args:
            - repo (str, optional): the name of the repository to open the issue in; must be provided in the
                form `organization/repo_name`; defaults to the one provided at initialization
            - info_keys (List[str], optional): a list of repo attributes to pull (e.g., `["stargazers_count", "subscribers_count"]`).
                A full list of available keys can be found in the official [GitHub documentation](https://developer.github.com/v3/repos/)

        Raises:
            - ValueError: if a `repo` was never provided
            - HTTPError: if the GET request returns a non-200 status code

        Returns:
            - dict: dictionary of the requested information
        """
        if repo is None:
            raise ValueError("A GitHub repository must be provided.")

        ## prepare the request
        token = Secret(self.token_secret).get()
        url = "https://api.github.com/repos/{}".format(repo)
        headers = {
            "AUTHORIZATION": "token {}".format(token),
            "Accept": "application/vnd.github.v3+json",
        }

        ## send the request
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        return {key: data[key] for key in info_keys}

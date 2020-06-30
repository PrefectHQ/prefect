from typing import Any, List

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class GetRepoInfo(Task):
    """
    Task for retrieving GitHub repository information using the v3 version of the GitHub REST API.

    Args:
        - repo (str, optional): the name of the repository to open the issue in; must be
            provided in the form `organization/repo_name` or `user/repo_name`; can also be
            provided to the `run` method
        - info_keys (List[str], optional): a list of repo attributes to pull (e.g.,
            `["stargazers_count", "subscribers_count"]`).  A full list of available keys can be
            found in the official [GitHub
            documentation](https://developer.github.com/v3/repos/)
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method
    """

    def __init__(self, repo: str = None, info_keys: List[str] = None, **kwargs: Any):
        self.repo = repo
        self.info_keys = info_keys or []

        super().__init__(**kwargs)

    @defaults_from_attrs("repo", "info_keys")
    def run(
        self, repo: str = None, info_keys: List[str] = None, token: str = None
    ) -> None:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a
        Flow context, or by using `Task.bind`.

        Args:
            - repo (str, optional): the name of the repository to open the issue in; must be
                provided in the form `organization/repo_name`; defaults to the one provided at
                initialization
            - info_keys (List[str], optional): a list of repo attributes to pull (e.g.,
                `["stargazers_count", "subscribers_count"]`).  A full list of available keys
                can be found in the official [GitHub
                documentation](https://developer.github.com/v3/repos/)
            - token (str): a GitHub access token

        Raises:
            - ValueError: if a `repo` was never provided
            - HTTPError: if the GET request returns a non-200 status code

        Returns:
            - dict: dictionary of the requested information
        """
        if repo is None:
            raise ValueError("A GitHub repository must be provided.")

        # 'import requests' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import requests

        url = "https://api.github.com/repos/{}".format(repo)
        headers = {
            "AUTHORIZATION": "token {}".format(token),
            "Accept": "application/vnd.github.v3+json",
        }

        # send the request
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        return {key: data[key] for key in info_keys}


class CreateBranch(Task):
    """
    Task for creating new branches using the v3 version of the GitHub REST API.

    Args:
        - repo (str, optional): the name of the repository to create the branch in; must be
            provided in the form `organization/repo_name` or `user/repo_name`; can also be
            provided to the `run` method
        - base (str, optional): the name of the branch you want to branch off; can also be
            provided to the `run` method.  Defaults to "master".
        - branch_name (str, optional): the name of the new branch; can also be provided to the
            `run` method
        - **kwargs (Any, optional): additional keyword arguments to pass to the standard Task
            init method
    """

    def __init__(
        self,
        repo: str = None,
        base: str = "master",
        branch_name: str = None,
        **kwargs: Any
    ):
        self.repo = repo
        self.base = base
        self.branch_name = branch_name

        super().__init__(**kwargs)

    @defaults_from_attrs("repo", "base", "branch_name")
    def run(
        self,
        repo: str = None,
        base: str = None,
        branch_name: str = None,
        token: str = None,
    ) -> dict:
        """
        Run method for this Task. Invoked by calling this Task after initialization within a
        Flow context, or by using `Task.bind`.

        Args:
            - repo (str, optional): the name of the repository to open the issue in; must be
                provided in the form `organization/repo_name`; defaults to the one provided at
                initialization
            - base (str, optional): the name of the branch you want to branch off; if not
                provided here, defaults to the one set at initialization
            - branch_name (str, optional): the name of the new branch; if not provided here,
                defaults to the one set at initialization
            - token (str): a GitHub access token

        Raises:
            - ValueError: if a `repo` or `branch_name` was never provided, or if the base
                branch wasn't found
            - HTTPError: if the GET request returns a non-200 status code

        Returns:
            - dict: dictionary of the response (includes commit hash, etc.)
        """
        if branch_name is None:
            raise ValueError("A branch name must be provided.")

        if repo is None:
            raise ValueError("A GitHub repository must be provided.")

        # 'import requests' is expensive time-wise, we should do this just-in-time to keep
        # the 'import prefect' time low
        import requests

        url = "https://api.github.com/repos/{}/git/refs".format(repo)
        headers = {
            "AUTHORIZATION": "token {}".format(token),
            "Accept": "application/vnd.github.v3+json",
        }

        # gather branch information
        resp = requests.get(url + "/heads", headers=headers)
        resp.raise_for_status()
        branch_data = resp.json()

        commit_sha = None
        for branch in branch_data:
            if branch.get("ref") == "refs/heads/{}".format(base):
                commit_sha = branch.get("object", {}).get("sha")
                break

        if commit_sha is None:
            raise ValueError("Base branch {} not found.".format(base))

        # create new branch
        new_branch = {"ref": "refs/heads/{}".format(branch_name), "sha": commit_sha}
        resp = requests.post(url, headers=headers, json=new_branch)
        resp.raise_for_status()
        return resp.json()

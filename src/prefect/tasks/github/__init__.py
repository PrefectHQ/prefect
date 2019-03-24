"""
A collection of tasks for interacting with GitHub.

Note that the tasks in this collection require a Prefect Secret called `"GITHUB_ACCESS_TOKEN"`
containing a valid GitHub Access Token.
"""

from .issues import OpenGitHubIssue
from .prs import CreateGitHubPR
from .repos import GetRepoInfo

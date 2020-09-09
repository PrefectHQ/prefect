"""
A collection of tasks for interacting with GitHub.
"""

from .issues import OpenGitHubIssue
from .prs import CreateGitHubPR
from .repos import GetRepoInfo, CreateBranch
from .comments import CreateIssueComment

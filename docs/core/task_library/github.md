# GitHub

A collection of tasks for interacting with GitHub.

Note that the tasks in this collection require a Prefect Secret called `"GITHUB_ACCESS_TOKEN"`
containing a valid GitHub Access Token.

## CreateGitHubPR <Badge text="task"/>

Task for opening / creating new GitHub Pull Requests using the v3 version of the GitHub REST API.

[API Reference](/api/latest/tasks/github.html#prefect-tasks-github-prs-creategithubpr)

## OpenGitHubIssue <Badge text="task"/>

Task for opening / creating new GitHub issues using the v3 version of the GitHub REST API.

[API Reference](/api/latest/tasks/github.html#prefect-tasks-github-prs-opengithubissue)

## CreateIssueComment <Badge text="task"/>

Task for creating a comment on the specified GitHub issue using the v3 version of the GitHub REST API.

[API Reference](/api/latest/tasks/github.html#prefect-tasks-github-prs-createissuecomment)

## GetRepoInfo <Badge text="task"/>

Task for retrieving GitHub repository information using the v3 version of the GitHub REST API.

[API Reference](/api/latest/tasks/github.html#prefect-tasks-github-prs-getrepoinfo)

## CreateBranch <Badge text="task"/>

Task for creating new branches in a given GitHub repository using the v3 version of the GitHub REST API.

[API Reference](/api/latest/tasks/github.html#prefect-tasks-github-prs-createbranch)

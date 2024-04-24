"""
This is a module containing:
GitHub mutation tasks

"""

# This module was auto-generated using prefect-collection-generator so
# manually editing this file is not recommended. If this module
# is outdated, rerun scripts/generate.py.

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable

from sgqlc.operation import Operation

from prefect import task
from prefect_github import GitHubCredentials
from prefect_github.graphql import _execute_graphql_op, _subset_return_fields
from prefect_github.schemas import graphql_schema
from prefect_github.utils import initialize_return_fields_defaults, strip_kwargs

config_dir = Path(__file__).parent.resolve() / "configs" / "mutation"
return_fields_defaults = {}
for config_path in config_dir.glob("*.json"):
    return_fields_defaults.update(initialize_return_fields_defaults(config_path))


@task
async def add_comment_subject(  # noqa
    subject_id: str,
    body: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Adds a comment to an Issue or Pull Request.

    Args:
        subject_id: The Node ID of the subject to modify.
        body: The contents of the comment.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.add_comment(
        **strip_kwargs(
            input=dict(
                subject_id=subject_id,
                body=body,
            )
        )
    ).subject(**strip_kwargs())

    op_stack = (
        "addComment",
        "subject",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["addComment"]["subject"]


@task
async def create_pull_request(  # noqa
    repository_id: str,
    base_ref_name: str,
    head_ref_name: str,
    title: str,
    github_credentials: GitHubCredentials,
    body: str = None,
    maintainer_can_modify: bool = None,
    draft: bool = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Create a new pull request.

    Args:
        repository_id: The Node ID of the repository.
        base_ref_name: The name of the branch you want your changes pulled into.
            This should be an existing branch on the current repository.
            You cannot update the base branch on a pull request to point
            to another repository.
        head_ref_name: The name of the branch where your changes are
            implemented. For cross-repository pull requests in the same
            network, namespace `head_ref_name` with a user like this:
            `username:branch`.
        title: The title of the pull request.
        github_credentials: Credentials to use for authentication with GitHub.
        body: The contents of the pull request.
        maintainer_can_modify: Indicates whether maintainers can modify the pull
            request.
        draft: Indicates whether this pull request should be a draft.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.create_pull_request(
        **strip_kwargs(
            input=dict(
                repository_id=repository_id,
                base_ref_name=base_ref_name,
                head_ref_name=head_ref_name,
                title=title,
                body=body,
                maintainer_can_modify=maintainer_can_modify,
                draft=draft,
            )
        )
    ).pull_request(**strip_kwargs())

    op_stack = (
        "createPullRequest",
        "pullRequest",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["createPullRequest"]["pullRequest"]


@task
async def close_pull_request(  # noqa
    pull_request_id: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Close a pull request.

    Args:
        pull_request_id: ID of the pull request to be closed.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.close_pull_request(
        **strip_kwargs(
            input=dict(
                pull_request_id=pull_request_id,
            )
        )
    ).pull_request(**strip_kwargs())

    op_stack = (
        "closePullRequest",
        "pullRequest",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["closePullRequest"]["pullRequest"]


@task
async def create_issue(  # noqa
    repository_id: str,
    title: str,
    assignee_ids: Iterable[str],
    label_ids: Iterable[str],
    project_ids: Iterable[str],
    github_credentials: GitHubCredentials,
    body: str = None,
    milestone_id: str = None,
    issue_template: str = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Creates a new issue.

    Args:
        repository_id: The Node ID of the repository.
        title: The title for the issue.
        assignee_ids: The Node ID for the user assignee for this issue.
        label_ids: An array of Node IDs of labels for this issue.
        project_ids: An array of Node IDs for projects associated with this
            issue.
        github_credentials: Credentials to use for authentication with GitHub.
        body: The body for the issue description.
        milestone_id: The Node ID of the milestone for this issue.
        issue_template: The name of an issue template in the repository, assigns
            labels and assignees from the template to the issue.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.create_issue(
        **strip_kwargs(
            input=dict(
                repository_id=repository_id,
                title=title,
                assignee_ids=assignee_ids,
                label_ids=label_ids,
                project_ids=project_ids,
                body=body,
                milestone_id=milestone_id,
                issue_template=issue_template,
            )
        )
    ).issue(**strip_kwargs())

    op_stack = (
        "createIssue",
        "issue",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["createIssue"]["issue"]


@task
async def close_issue(  # noqa
    issue_id: str,
    github_credentials: GitHubCredentials,
    state_reason: graphql_schema.IssueClosedStateReason = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Close an issue.

    Args:
        issue_id: ID of the issue to be closed.
        github_credentials: Credentials to use for authentication with GitHub.
        state_reason: The reason the issue is to be closed.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.close_issue(
        **strip_kwargs(
            input=dict(
                issue_id=issue_id,
                state_reason=state_reason,
            )
        )
    ).issue(**strip_kwargs())

    op_stack = (
        "closeIssue",
        "issue",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["closeIssue"]["issue"]


@task
async def add_star_starrable(  # noqa
    starrable_id: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Adds a star to a Starrable.

    Args:
        starrable_id: The Starrable ID to star.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.add_star(
        **strip_kwargs(
            input=dict(
                starrable_id=starrable_id,
            )
        )
    ).starrable(**strip_kwargs())

    op_stack = (
        "addStar",
        "starrable",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["addStar"]["starrable"]


@task
async def remove_star_starrable(  # noqa
    starrable_id: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Removes a star from a Starrable.

    Args:
        starrable_id: The Starrable ID to unstar.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.remove_star(
        **strip_kwargs(
            input=dict(
                starrable_id=starrable_id,
            )
        )
    ).starrable(**strip_kwargs())

    op_stack = (
        "removeStar",
        "starrable",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["removeStar"]["starrable"]


@task
async def add_reaction_subject(  # noqa
    subject_id: str,
    content: graphql_schema.ReactionContent,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Adds a reaction to a subject.

    Args:
        subject_id: The Node ID of the subject to modify.
        content: The name of the emoji to react with.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.add_reaction(
        **strip_kwargs(
            input=dict(
                subject_id=subject_id,
                content=content,
            )
        )
    ).subject(**strip_kwargs())

    op_stack = (
        "addReaction",
        "subject",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["addReaction"]["subject"]


@task
async def add_reaction(  # noqa
    subject_id: str,
    content: graphql_schema.ReactionContent,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Adds a reaction to a subject.

    Args:
        subject_id: The Node ID of the subject to modify.
        content: The name of the emoji to react with.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.add_reaction(
        **strip_kwargs(
            input=dict(
                subject_id=subject_id,
                content=content,
            )
        )
    ).reaction(**strip_kwargs())

    op_stack = (
        "addReaction",
        "reaction",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["addReaction"]["reaction"]


@task
async def remove_reaction_subject(  # noqa
    subject_id: str,
    content: graphql_schema.ReactionContent,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Removes a reaction from a subject.

    Args:
        subject_id: The Node ID of the subject to modify.
        content: The name of the emoji reaction to remove.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.remove_reaction(
        **strip_kwargs(
            input=dict(
                subject_id=subject_id,
                content=content,
            )
        )
    ).subject(**strip_kwargs())

    op_stack = (
        "removeReaction",
        "subject",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["removeReaction"]["subject"]


@task
async def remove_reaction(  # noqa
    subject_id: str,
    content: graphql_schema.ReactionContent,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Removes a reaction from a subject.

    Args:
        subject_id: The Node ID of the subject to modify.
        content: The name of the emoji reaction to remove.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.remove_reaction(
        **strip_kwargs(
            input=dict(
                subject_id=subject_id,
                content=content,
            )
        )
    ).reaction(**strip_kwargs())

    op_stack = (
        "removeReaction",
        "reaction",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["removeReaction"]["reaction"]


@task
async def request_reviews(  # noqa
    pull_request_id: str,
    user_ids: Iterable[str],
    team_ids: Iterable[str],
    github_credentials: GitHubCredentials,
    union: bool = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Set review requests on a pull request.

    Args:
        pull_request_id: The Node ID of the pull request to modify.
        user_ids: The Node IDs of the user to request.
        team_ids: The Node IDs of the team to request.
        github_credentials: Credentials to use for authentication with GitHub.
        union: Add users to the set rather than replace.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.request_reviews(
        **strip_kwargs(
            input=dict(
                pull_request_id=pull_request_id,
                user_ids=user_ids,
                team_ids=team_ids,
                union=union,
            )
        )
    )

    op_stack = ("requestReviews",)
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["requestReviews"]


@task
async def request_reviews_pull_request(  # noqa
    pull_request_id: str,
    user_ids: Iterable[str],
    team_ids: Iterable[str],
    github_credentials: GitHubCredentials,
    union: bool = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Set review requests on a pull request.

    Args:
        pull_request_id: The Node ID of the pull request to modify.
        user_ids: The Node IDs of the user to request.
        team_ids: The Node IDs of the team to request.
        github_credentials: Credentials to use for authentication with GitHub.
        union: Add users to the set rather than replace.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.request_reviews(
        **strip_kwargs(
            input=dict(
                pull_request_id=pull_request_id,
                user_ids=user_ids,
                team_ids=team_ids,
                union=union,
            )
        )
    ).pull_request(**strip_kwargs())

    op_stack = (
        "requestReviews",
        "pullRequest",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["requestReviews"]["pullRequest"]


@task
async def add_pull_request_review(  # noqa
    pull_request_id: str,
    github_credentials: GitHubCredentials,
    commit_oid: datetime = None,
    body: str = None,
    event: graphql_schema.PullRequestReviewEvent = None,
    comments: Iterable[graphql_schema.DraftPullRequestReviewComment] = None,
    threads: Iterable[graphql_schema.DraftPullRequestReviewThread] = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Adds a review to a Pull Request.

    Args:
        pull_request_id: The Node ID of the pull request to modify.
        github_credentials: Credentials to use for authentication with GitHub.
        commit_oid: The commit OID the review pertains to.
        body: The contents of the review body comment.
        event: The event to perform on the pull request review.
        comments: The review line comments.
        threads: The review line comment threads.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/mutation/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Mutation)
    op_selection = op.add_pull_request_review(
        **strip_kwargs(
            input=dict(
                pull_request_id=pull_request_id,
                commit_oid=commit_oid,
                body=body,
                event=event,
                comments=comments,
                threads=threads,
            )
        )
    ).pull_request_review(**strip_kwargs())

    op_stack = (
        "addPullRequestReview",
        "pullRequestReview",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["addPullRequestReview"]["pullRequestReview"]

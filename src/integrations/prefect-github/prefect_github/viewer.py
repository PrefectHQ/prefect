"""
This is a module containing:
GitHub query_viewer* tasks
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

config_path = Path(__file__).parent.resolve() / "configs" / "query" / "viewer.json"
return_fields_defaults = initialize_return_fields_defaults(config_path)


@task
async def query_viewer(  # noqa
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The query root of GitHub's GraphQL interface.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs())

    op_stack = ("viewer",)
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]


@task
async def query_viewer_gist(  # noqa
    name: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find gist by repo name.

    Args:
        name: The gist name to find.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).gist(
        **strip_kwargs(
            name=name,
        )
    )

    op_stack = (
        "viewer",
        "gist",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["gist"]


@task
async def query_viewer_gists(  # noqa
    github_credentials: GitHubCredentials,
    privacy: graphql_schema.GistPrivacy = None,
    order_by: graphql_schema.GistOrder = None,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of the Gists the user has created.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        privacy: Filters Gists according to privacy.
        order_by: Ordering options for gists returned from the connection.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).gists(
        **strip_kwargs(
            privacy=privacy,
            order_by=order_by,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "gists",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["gists"]


@task
async def query_viewer_issues(  # noqa
    labels: Iterable[str],
    states: Iterable[graphql_schema.IssueState],
    github_credentials: GitHubCredentials,
    order_by: graphql_schema.IssueOrder = None,
    filter_by: graphql_schema.IssueFilters = None,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of issues associated with this user.

    Args:
        labels: A list of label names to filter the pull requests by.
        states: A list of states to filter the issues by.
        github_credentials: Credentials to use for authentication with GitHub.
        order_by: Ordering options for issues returned from the
            connection.
        filter_by: Filtering options for issues returned from the
            connection.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).issues(
        **strip_kwargs(
            labels=labels,
            states=states,
            order_by=order_by,
            filter_by=filter_by,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "issues",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["issues"]


@task
async def query_viewer_status(  # noqa
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The user's description of what they're currently doing.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).status(**strip_kwargs())

    op_stack = (
        "viewer",
        "status",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["status"]


@task
async def query_viewer_project(  # noqa
    number: int,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find project by number.

    Args:
        number: The project number to find.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).project(
        **strip_kwargs(
            number=number,
        )
    )

    op_stack = (
        "viewer",
        "project",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["project"]


@task
async def query_viewer_packages(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    names: Iterable[str] = None,
    repository_id: str = None,
    package_type: graphql_schema.PackageType = None,
    order_by: graphql_schema.PackageOrder = {
        "field": "CREATED_AT",
        "direction": "DESC",
    },
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of packages under the owner.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        names: Find packages by their names.
        repository_id: Find packages in a repository by ID.
        package_type: Filter registry package by type.
        order_by: Ordering of the returned packages.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).packages(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            names=names,
            repository_id=repository_id,
            package_type=package_type,
            order_by=order_by,
        )
    )

    op_stack = (
        "viewer",
        "packages",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["packages"]


@task
async def query_viewer_projects(  # noqa
    states: Iterable[graphql_schema.ProjectState],
    github_credentials: GitHubCredentials,
    order_by: graphql_schema.ProjectOrder = None,
    search: str = None,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of projects under the owner.

    Args:
        states: A list of states to filter the projects by.
        github_credentials: Credentials to use for authentication with GitHub.
        order_by: Ordering options for projects returned from the
            connection.
        search: Query to search projects by, currently only searching
            by name.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).projects(
        **strip_kwargs(
            states=states,
            order_by=order_by,
            search=search,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "projects",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["projects"]


@task
async def query_viewer_sponsors(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    tier_id: str = None,
    order_by: graphql_schema.SponsorOrder = {"field": "RELEVANCE", "direction": "DESC"},
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    List of sponsors for this user or organization.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        tier_id: If given, will filter for sponsors at the given tier.
            Will only return sponsors whose tier the viewer is permitted
            to see.
        order_by: Ordering options for sponsors returned from the
            connection.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).sponsors(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            tier_id=tier_id,
            order_by=order_by,
        )
    )

    op_stack = (
        "viewer",
        "sponsors",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["sponsors"]


@task
async def query_viewer_watching(  # noqa
    github_credentials: GitHubCredentials,
    privacy: graphql_schema.RepositoryPrivacy = None,
    order_by: graphql_schema.RepositoryOrder = None,
    affiliations: Iterable[graphql_schema.RepositoryAffiliation] = None,
    owner_affiliations: Iterable[graphql_schema.RepositoryAffiliation] = (
        "OWNER",
        "COLLABORATOR",
    ),
    is_locked: bool = None,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of repositories the given user is watching.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        privacy: If non-null, filters repositories according to privacy.
        order_by: Ordering options for repositories returned from the
            connection.
        affiliations: Affiliation options for repositories returned
            from the connection. If none specified, the results will
            include repositories for which the current viewer is an
            owner or collaborator, or member.
        owner_affiliations: Array of owner's affiliation options for
            repositories returned from the connection. For example,
            OWNER will include only repositories that the organization
            or user being viewed owns.
        is_locked: If non-null, filters repositories according to
            whether they have been locked.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).watching(
        **strip_kwargs(
            privacy=privacy,
            order_by=order_by,
            affiliations=affiliations,
            owner_affiliations=owner_affiliations,
            is_locked=is_locked,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "watching",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["watching"]


@task
async def query_viewer_project_v2(  # noqa
    number: int,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find a project by number.

    Args:
        number: The project number.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).project_v2(
        **strip_kwargs(
            number=number,
        )
    )

    op_stack = (
        "viewer",
        "projectV2",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["projectV2"]


@task
async def query_viewer_followers(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of users the given user is followed by.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).followers(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "followers",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["followers"]


@task
async def query_viewer_following(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of users the given user is following.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).following(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "following",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["following"]


@task
async def query_viewer_projects_v2(  # noqa
    github_credentials: GitHubCredentials,
    query: str = None,
    order_by: graphql_schema.ProjectV2Order = {"field": "NUMBER", "direction": "DESC"},
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of projects under the owner.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        query: A project to search for under the the owner.
        order_by: How to order the returned projects.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).projects_v2(
        **strip_kwargs(
            query=query,
            order_by=order_by,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "projectsV2",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["projectsV2"]


@task
async def query_viewer_repository(  # noqa
    name: str,
    github_credentials: GitHubCredentials,
    follow_renames: bool = True,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find Repository.

    Args:
        name: Name of Repository to find.
        github_credentials: Credentials to use for authentication with GitHub.
        follow_renames: Follow repository renames. If disabled, a
            repository referenced by its old name will return an error.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).repository(
        **strip_kwargs(
            name=name,
            follow_renames=follow_renames,
        )
    )

    op_stack = (
        "viewer",
        "repository",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["repository"]


@task
async def query_viewer_sponsoring(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    order_by: graphql_schema.SponsorOrder = {"field": "RELEVANCE", "direction": "DESC"},
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    List of users and organizations this entity is sponsoring.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        order_by: Ordering options for the users and organizations
            returned from the connection.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).sponsoring(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
        )
    )

    op_stack = (
        "viewer",
        "sponsoring",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["sponsoring"]


@task
async def query_viewer_public_keys(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of public keys associated with this user.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).public_keys(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "publicKeys",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["publicKeys"]


@task
async def query_viewer_project_next(  # noqa
    number: int,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find a project by project (beta) number.

    Args:
        number: The project (beta) number.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).project_next(
        **strip_kwargs(
            number=number,
        )
    )

    op_stack = (
        "viewer",
        "projectNext",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["projectNext"]


@task
async def query_viewer_pinned_items(  # noqa
    types: Iterable[graphql_schema.PinnableItemType],
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of repositories and gists this profile owner has pinned to their profile.

    Args:
        types: Filter the types of pinned items that are returned.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).pinned_items(
        **strip_kwargs(
            types=types,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "pinnedItems",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["pinnedItems"]


@task
async def query_viewer_projects_next(  # noqa
    github_credentials: GitHubCredentials,
    query: str = None,
    sort_by: graphql_schema.ProjectNextOrderField = "TITLE",
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of projects (beta) under the owner.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        query: A project (beta) to search for under the the owner.
        sort_by: How to order the returned projects (beta).
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).projects_next(
        **strip_kwargs(
            query=query,
            sort_by=sort_by,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "projectsNext",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["projectsNext"]


@task
async def query_viewer_repositories(  # noqa
    github_credentials: GitHubCredentials,
    privacy: graphql_schema.RepositoryPrivacy = None,
    order_by: graphql_schema.RepositoryOrder = None,
    affiliations: Iterable[graphql_schema.RepositoryAffiliation] = None,
    owner_affiliations: Iterable[graphql_schema.RepositoryAffiliation] = (
        "OWNER",
        "COLLABORATOR",
    ),
    is_locked: bool = None,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    is_fork: bool = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of repositories that the user owns.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        privacy: If non-null, filters repositories according to
            privacy.
        order_by: Ordering options for repositories returned from
            the connection.
        affiliations: Array of viewer's affiliation options for
            repositories returned from the connection. For example,
            OWNER will include only repositories that the current viewer
            owns.
        owner_affiliations: Array of owner's affiliation options
            for repositories returned from the connection. For example,
            OWNER will include only repositories that the organization
            or user being viewed owns.
        is_locked: If non-null, filters repositories according to
            whether they have been locked.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        is_fork: If non-null, filters repositories according to
            whether they are forks of another repository.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).repositories(
        **strip_kwargs(
            privacy=privacy,
            order_by=order_by,
            affiliations=affiliations,
            owner_affiliations=owner_affiliations,
            is_locked=is_locked,
            after=after,
            before=before,
            first=first,
            last=last,
            is_fork=is_fork,
        )
    )

    op_stack = (
        "viewer",
        "repositories",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["repositories"]


@task
async def query_viewer_item_showcase(  # noqa
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Showcases a selection of repositories and gists that the profile owner has
    either curated or that have been selected automatically based on popularity.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).item_showcase(**strip_kwargs())

    op_stack = (
        "viewer",
        "itemShowcase",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["itemShowcase"]


@task
async def query_viewer_gist_comments(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of gist comments made by this user.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).gist_comments(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "gistComments",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["gistComments"]


@task
async def query_viewer_organization(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find an organization by its login that the user belongs to.

    Args:
        login: The login of the organization to find.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).organization(
        **strip_kwargs(
            login=login,
        )
    )

    op_stack = (
        "viewer",
        "organization",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["organization"]


@task
async def query_viewer_pull_requests(  # noqa
    states: Iterable[graphql_schema.PullRequestState],
    labels: Iterable[str],
    github_credentials: GitHubCredentials,
    head_ref_name: str = None,
    base_ref_name: str = None,
    order_by: graphql_schema.IssueOrder = None,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of pull requests associated with this user.

    Args:
        states: A list of states to filter the pull requests by.
        labels: A list of label names to filter the pull requests
            by.
        github_credentials: Credentials to use for authentication with GitHub.
        head_ref_name: The head ref name to filter the pull
            requests by.
        base_ref_name: The base ref name to filter the pull
            requests by.
        order_by: Ordering options for pull requests returned from
            the connection.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).pull_requests(
        **strip_kwargs(
            states=states,
            labels=labels,
            head_ref_name=head_ref_name,
            base_ref_name=base_ref_name,
            order_by=order_by,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "pullRequests",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["pullRequests"]


@task
async def query_viewer_saved_replies(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    order_by: graphql_schema.SavedReplyOrder = {
        "field": "UPDATED_AT",
        "direction": "DESC",
    },
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Replies this user has saved.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        order_by: The field to order saved replies by.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).saved_replies(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
        )
    )

    op_stack = (
        "viewer",
        "savedReplies",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["savedReplies"]


@task
async def query_viewer_pinnable_items(  # noqa
    types: Iterable[graphql_schema.PinnableItemType],
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of repositories and gists this profile owner can pin to their profile.

    Args:
        types: Filter the types of pinnable items that are
            returned.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).pinnable_items(
        **strip_kwargs(
            types=types,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "pinnableItems",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["pinnableItems"]


@task
async def query_viewer_issue_comments(  # noqa
    github_credentials: GitHubCredentials,
    order_by: graphql_schema.IssueCommentOrder = None,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of issue comments made by this user.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        order_by: Ordering options for issue comments returned
            from the connection.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).issue_comments(
        **strip_kwargs(
            order_by=order_by,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "issueComments",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["issueComments"]


@task
async def query_viewer_organizations(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of organizations the user belongs to.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come before
            the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).organizations(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "organizations",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["organizations"]


@task
async def query_viewer_recent_projects(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Recent projects that this user has modified in the context of the owner.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come
            before the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).recent_projects(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "recentProjects",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["recentProjects"]


@task
async def query_viewer_commit_comments(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of commit comments made by this user.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come
            before the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).commit_comments(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "commitComments",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["commitComments"]


@task
async def query_viewer_sponsors_listing(  # noqa
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The GitHub Sponsors listing for this user or organization.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).sponsors_listing(**strip_kwargs())

    op_stack = (
        "viewer",
        "sponsorsListing",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["sponsorsListing"]


@task
async def query_viewer_top_repositories(  # noqa
    order_by: graphql_schema.RepositoryOrder,
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    since: datetime = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Repositories the user has contributed to, ordered by contribution rank, plus
    repositories the user has created.

    Args:
        order_by: Ordering options for repositories returned
            from the connection.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come
            before the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        since: How far back in time to fetch contributed
            repositories.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).top_repositories(
        **strip_kwargs(
            order_by=order_by,
            after=after,
            before=before,
            first=first,
            last=last,
            since=since,
        )
    )

    op_stack = (
        "viewer",
        "topRepositories",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["topRepositories"]


@task
async def query_viewer_sponsors_activities(  # noqa
    actions: Iterable[graphql_schema.SponsorsActivityAction],
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    period: graphql_schema.SponsorsActivityPeriod = "MONTH",
    order_by: graphql_schema.SponsorsActivityOrder = {
        "field": "TIMESTAMP",
        "direction": "DESC",
    },
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Events involving this sponsorable, such as new sponsorships.

    Args:
        actions: Filter activities to only the specified
            actions.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come
            after the specified cursor.
        before: Returns the elements in the list that come
            before the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        period: Filter activities returned to only those
            that occurred in the most recent specified time period. Set
            to ALL to avoid filtering by when the activity occurred.
        order_by: Ordering options for activity returned
            from the connection.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).sponsors_activities(
        **strip_kwargs(
            actions=actions,
            after=after,
            before=before,
            first=first,
            last=last,
            period=period,
            order_by=order_by,
        )
    )

    op_stack = (
        "viewer",
        "sponsorsActivities",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["sponsorsActivities"]


@task
async def query_viewer_interaction_ability(  # noqa
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The interaction ability settings for this user.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).interaction_ability(**strip_kwargs())

    op_stack = (
        "viewer",
        "interactionAbility",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["interactionAbility"]


@task
async def query_viewer_starred_repositories(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    owned_by_viewer: bool = None,
    order_by: graphql_schema.StarOrder = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Repositories the user has starred.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come
            after the specified cursor.
        before: Returns the elements in the list that come
            before the specified cursor.
        first: Returns the first _n_ elements from the
            list.
        last: Returns the last _n_ elements from the list.
        owned_by_viewer: Filters starred repositories to
            only return repositories owned by the viewer.
        order_by: Order for connection.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).starred_repositories(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            owned_by_viewer=owned_by_viewer,
            order_by=order_by,
        )
    )

    op_stack = (
        "viewer",
        "starredRepositories",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["starredRepositories"]


@task
async def query_viewer_repository_discussions(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    order_by: graphql_schema.DiscussionOrder = {
        "field": "CREATED_AT",
        "direction": "DESC",
    },
    repository_id: str = None,
    answered: bool = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Discussions this user has started.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come
            after the specified cursor.
        before: Returns the elements in the list that
            come before the specified cursor.
        first: Returns the first _n_ elements from the
            list.
        last: Returns the last _n_ elements from the
            list.
        order_by: Ordering options for discussions
            returned from the connection.
        repository_id: Filter discussions to only those
            in a specific repository.
        answered: Filter discussions to only those that
            have been answered or not. Defaults to including both
            answered and unanswered discussions.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).repository_discussions(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
            repository_id=repository_id,
            answered=answered,
        )
    )

    op_stack = (
        "viewer",
        "repositoryDiscussions",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["repositoryDiscussions"]


@task
async def query_viewer_sponsorships_as_sponsor(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    order_by: graphql_schema.SponsorshipOrder = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    This object's sponsorships as the sponsor.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that
            come after the specified cursor.
        before: Returns the elements in the list that
            come before the specified cursor.
        first: Returns the first _n_ elements from the
            list.
        last: Returns the last _n_ elements from the
            list.
        order_by: Ordering options for sponsorships
            returned from this connection. If left blank, the
            sponsorships will be ordered based on relevancy to the
            viewer.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).sponsorships_as_sponsor(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
        )
    )

    op_stack = (
        "viewer",
        "sponsorshipsAsSponsor",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["sponsorshipsAsSponsor"]


@task
async def query_viewer_sponsorship_newsletters(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    order_by: graphql_schema.SponsorshipNewsletterOrder = {
        "field": "CREATED_AT",
        "direction": "DESC",
    },
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    List of sponsorship updates sent from this sponsorable to sponsors.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that
            come after the specified cursor.
        before: Returns the elements in the list that
            come before the specified cursor.
        first: Returns the first _n_ elements from the
            list.
        last: Returns the last _n_ elements from the
            list.
        order_by: Ordering options for sponsorship
            updates returned from the connection.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).sponsorship_newsletters(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
        )
    )

    op_stack = (
        "viewer",
        "sponsorshipNewsletters",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["sponsorshipNewsletters"]


@task
async def query_viewer_contributions_collection(  # noqa
    github_credentials: GitHubCredentials,
    organization_id: str = None,
    from_: datetime = None,
    to: datetime = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The collection of contributions this user has made to different repositories.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        organization_id: The ID of the organization
            used to filter contributions.
        from_: Only contributions made at this time or
            later will be counted. If omitted, defaults to a year ago.
        to: Only contributions made before and up to
            (including) this time will be counted. If omitted, defaults
            to the current time or one year from the provided from
            argument.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).contributions_collection(
        **strip_kwargs(
            organization_id=organization_id,
            from_=from_,
            to=to,
        )
    )

    op_stack = (
        "viewer",
        "contributionsCollection",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["contributionsCollection"]


@task
async def query_viewer_sponsorships_as_maintainer(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    include_private: bool = False,
    order_by: graphql_schema.SponsorshipOrder = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    This object's sponsorships as the maintainer.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that
            come after the specified cursor.
        before: Returns the elements in the list that
            come before the specified cursor.
        first: Returns the first _n_ elements from
            the list.
        last: Returns the last _n_ elements from the
            list.
        include_private: Whether or not to include
            private sponsorships in the result set.
        order_by: Ordering options for sponsorships
            returned from this connection. If left blank, the
            sponsorships will be ordered based on relevancy to the
            viewer.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).sponsorships_as_maintainer(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            include_private=include_private,
            order_by=order_by,
        )
    )

    op_stack = (
        "viewer",
        "sponsorshipsAsMaintainer",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["sponsorshipsAsMaintainer"]


@task
async def query_viewer_repositories_contributed_to(  # noqa
    github_credentials: GitHubCredentials,
    privacy: graphql_schema.RepositoryPrivacy = None,
    order_by: graphql_schema.RepositoryOrder = None,
    is_locked: bool = None,
    include_user_repositories: bool = None,
    contribution_types: Iterable[graphql_schema.RepositoryContributionType] = None,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of repositories that the user recently contributed to.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        privacy: If non-null, filters repositories
            according to privacy.
        order_by: Ordering options for repositories
            returned from the connection.
        is_locked: If non-null, filters repositories
            according to whether they have been locked.
        include_user_repositories: If true, include
            user repositories.
        contribution_types: If non-null, include
            only the specified types of contributions. The GitHub.com UI
            uses [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY].
        after: Returns the elements in the list that
            come after the specified cursor.
        before: Returns the elements in the list
            that come before the specified cursor.
        first: Returns the first _n_ elements from
            the list.
        last: Returns the last _n_ elements from the
            list.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).repositories_contributed_to(
        **strip_kwargs(
            privacy=privacy,
            order_by=order_by,
            is_locked=is_locked,
            include_user_repositories=include_user_repositories,
            contribution_types=contribution_types,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "viewer",
        "repositoriesContributedTo",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["repositoriesContributedTo"]


@task
async def query_viewer_repository_discussion_comments(  # noqa
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    repository_id: str = None,
    only_answers: bool = False,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Discussion comments this user has authored.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list
            that come after the specified cursor.
        before: Returns the elements in the list
            that come before the specified cursor.
        first: Returns the first _n_ elements
            from the list.
        last: Returns the last _n_ elements from
            the list.
        repository_id: Filter discussion comments
            to only those in a specific repository.
        only_answers: Filter discussion comments
            to only those that were marked as the answer.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).repository_discussion_comments(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            repository_id=repository_id,
            only_answers=only_answers,
        )
    )

    op_stack = (
        "viewer",
        "repositoryDiscussionComments",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["repositoryDiscussionComments"]


@task
async def query_viewer_sponsorship_for_viewer_as_sponsor(  # noqa
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The sponsorship from the viewer to this user/organization; that is, the
    sponsorship where you're the sponsor. Only returns a sponsorship if it is
    active.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).sponsorship_for_viewer_as_sponsor(
        **strip_kwargs()
    )

    op_stack = (
        "viewer",
        "sponsorshipForViewerAsSponsor",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["sponsorshipForViewerAsSponsor"]


@task
async def query_viewer_sponsorship_for_viewer_as_sponsorable(  # noqa
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The sponsorship from this user/organization to the viewer; that is, the
    sponsorship you're receiving. Only returns a sponsorship if it is active.

    Args:
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.viewer(**strip_kwargs()).sponsorship_for_viewer_as_sponsorable(
        **strip_kwargs()
    )

    op_stack = (
        "viewer",
        "sponsorshipForViewerAsSponsorable",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["viewer"]["sponsorshipForViewerAsSponsorable"]

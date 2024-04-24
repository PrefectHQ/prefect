"""
This is a module containing:
GitHub query_repository_owner* tasks
"""

# This module was auto-generated using prefect-collection-generator so
# manually editing this file is not recommended. If this module
# is outdated, rerun scripts/generate.py.

from pathlib import Path
from typing import Any, Dict, Iterable

from sgqlc.operation import Operation

from prefect import task
from prefect_github import GitHubCredentials
from prefect_github.graphql import _execute_graphql_op, _subset_return_fields
from prefect_github.schemas import graphql_schema
from prefect_github.utils import initialize_return_fields_defaults, strip_kwargs

config_path = (
    Path(__file__).parent.resolve() / "configs" / "query" / "repository_owner.json"
)
return_fields_defaults = initialize_return_fields_defaults(config_path)


@task
async def query_repository_owner(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The query root of GitHub's GraphQL interface.

    Args:
        login: The username to lookup the owner by.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.repository_owner(
        **strip_kwargs(
            login=login,
        )
    )

    op_stack = ("repositoryOwner",)
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["repositoryOwner"]


@task
async def query_repository_owner_repository(  # noqa
    login: str,
    name: str,
    github_credentials: GitHubCredentials,
    follow_renames: bool = True,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find Repository.

    Args:
        login: The username to lookup the owner by.
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
    op_selection = op.repository_owner(
        **strip_kwargs(
            login=login,
        )
    ).repository(
        **strip_kwargs(
            name=name,
            follow_renames=follow_renames,
        )
    )

    op_stack = (
        "repositoryOwner",
        "repository",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["repositoryOwner"]["repository"]


@task
async def query_repository_owner_repositories(  # noqa
    login: str,
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
        login: The username to lookup the owner by.
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
    op_selection = op.repository_owner(
        **strip_kwargs(
            login=login,
        )
    ).repositories(
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
        "repositoryOwner",
        "repositories",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["repositoryOwner"]["repositories"]

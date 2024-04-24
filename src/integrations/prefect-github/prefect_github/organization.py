"""
This is a module containing:
GitHub query_organization* tasks
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
    Path(__file__).parent.resolve() / "configs" / "query" / "organization.json"
)
return_fields_defaults = initialize_return_fields_defaults(config_path)


@task
async def query_organization(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The query root of GitHub's GraphQL interface.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    )

    op_stack = ("organization",)
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]


@task
async def query_organization_team(  # noqa
    login: str,
    slug: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find an organization's team by its slug.

    Args:
        login: The organization's login.
        slug: The name or slug of the team to find.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).team(
        **strip_kwargs(
            slug=slug,
        )
    )

    op_stack = (
        "organization",
        "team",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["team"]


@task
async def query_organization_teams(  # noqa
    login: str,
    user_logins: Iterable[str],
    github_credentials: GitHubCredentials,
    privacy: graphql_schema.TeamPrivacy = None,
    role: graphql_schema.TeamRole = None,
    query: str = None,
    order_by: graphql_schema.TeamOrder = None,
    ldap_mapped: bool = None,
    root_teams_only: bool = False,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of teams in this organization.

    Args:
        login: The organization's login.
        user_logins: User logins to filter by.
        github_credentials: Credentials to use for authentication with GitHub.
        privacy: If non-null, filters teams according to privacy.
        role: If non-null, filters teams according to whether the viewer
            is an admin or member on team.
        query: If non-null, filters teams with query on team name and team
            slug.
        order_by: Ordering options for teams returned from the connection.
        ldap_mapped: If true, filters teams that are mapped to an LDAP
            Group (Enterprise only).
        root_teams_only: If true, restrict to only root teams.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).teams(
        **strip_kwargs(
            user_logins=user_logins,
            privacy=privacy,
            role=role,
            query=query,
            order_by=order_by,
            ldap_mapped=ldap_mapped,
            root_teams_only=root_teams_only,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "organization",
        "teams",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["teams"]


@task
async def query_organization_project(  # noqa
    login: str,
    number: int,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find project by number.

    Args:
        login: The organization's login.
        number: The project number to find.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).project(
        **strip_kwargs(
            number=number,
        )
    )

    op_stack = (
        "organization",
        "project",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["project"]


@task
async def query_organization_domains(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    is_verified: bool = None,
    is_approved: bool = None,
    order_by: graphql_schema.VerifiableDomainOrder = {
        "field": "DOMAIN",
        "direction": "ASC",
    },
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of domains owned by the organization.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        is_verified: Filter by if the domain is verified.
        is_approved: Filter by if the domain is approved.
        order_by: Ordering options for verifiable domains returned.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).domains(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            is_verified=is_verified,
            is_approved=is_approved,
            order_by=order_by,
        )
    )

    op_stack = (
        "organization",
        "domains",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["domains"]


@task
async def query_organization_packages(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).packages(
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
        "organization",
        "packages",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["packages"]


@task
async def query_organization_projects(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).projects(
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
        "organization",
        "projects",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["projects"]


@task
async def query_organization_sponsors(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).sponsors(
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
        "organization",
        "sponsors",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["sponsors"]


@task
async def query_organization_audit_log(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    query: str = None,
    order_by: graphql_schema.AuditLogOrder = {
        "field": "CREATED_AT",
        "direction": "DESC",
    },
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Audit log entries of the organization.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after the
            specified cursor.
        before: Returns the elements in the list that come before the
            specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        query: The query string to filter audit entries.
        order_by: Ordering options for the returned audit log entries.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).audit_log(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            query=query,
            order_by=order_by,
        )
    )

    op_stack = (
        "organization",
        "auditLog",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["auditLog"]


@task
async def query_organization_project_v2(  # noqa
    login: str,
    number: int,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find a project by number.

    Args:
        login: The organization's login.
        number: The project number.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).project_v2(
        **strip_kwargs(
            number=number,
        )
    )

    op_stack = (
        "organization",
        "projectV2",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["projectV2"]


@task
async def query_organization_projects_v2(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).projects_v2(
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
        "organization",
        "projectsV2",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["projectsV2"]


@task
async def query_organization_repository(  # noqa
    login: str,
    name: str,
    github_credentials: GitHubCredentials,
    follow_renames: bool = True,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find Repository.

    Args:
        login: The organization's login.
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
    op_selection = op.organization(
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
        "organization",
        "repository",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["repository"]


@task
async def query_organization_sponsoring(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).sponsoring(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
        )
    )

    op_stack = (
        "organization",
        "sponsoring",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["sponsoring"]


@task
async def query_organization_project_next(  # noqa
    login: str,
    number: int,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Find a project by project (beta) number.

    Args:
        login: The organization's login.
        number: The project (beta) number.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).project_next(
        **strip_kwargs(
            number=number,
        )
    )

    op_stack = (
        "organization",
        "projectNext",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["projectNext"]


@task
async def query_organization_pinned_items(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).pinned_items(
        **strip_kwargs(
            types=types,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "organization",
        "pinnedItems",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["pinnedItems"]


@task
async def query_organization_projects_next(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).projects_next(
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
        "organization",
        "projectsNext",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["projectsNext"]


@task
async def query_organization_repositories(  # noqa
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
        login: The organization's login.
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
    op_selection = op.organization(
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
        "organization",
        "repositories",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["repositories"]


@task
async def query_organization_item_showcase(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Showcases a selection of repositories and gists that the profile owner has
    either curated or that have been selected automatically based on popularity.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).item_showcase(**strip_kwargs())

    op_stack = (
        "organization",
        "itemShowcase",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["itemShowcase"]


@task
async def query_organization_pinnable_items(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).pinnable_items(
        **strip_kwargs(
            types=types,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "organization",
        "pinnableItems",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["pinnableItems"]


@task
async def query_organization_recent_projects(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).recent_projects(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "organization",
        "recentProjects",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["recentProjects"]


@task
async def query_organization_member_statuses(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    order_by: graphql_schema.UserStatusOrder = {
        "field": "UPDATED_AT",
        "direction": "DESC",
    },
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    Get the status messages members of this entity have set that are either public
    or visible only to the organization.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come after
            the specified cursor.
        before: Returns the elements in the list that come
            before the specified cursor.
        first: Returns the first _n_ elements from the list.
        last: Returns the last _n_ elements from the list.
        order_by: Ordering options for user statuses returned
            from the connection.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).member_statuses(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
        )
    )

    op_stack = (
        "organization",
        "memberStatuses",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["memberStatuses"]


@task
async def query_organization_pending_members(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of users who have been invited to join this organization.

    Args:
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).pending_members(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "organization",
        "pendingMembers",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["pendingMembers"]


@task
async def query_organization_sponsors_listing(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The GitHub Sponsors listing for this user or organization.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).sponsors_listing(**strip_kwargs())

    op_stack = (
        "organization",
        "sponsorsListing",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["sponsorsListing"]


@task
async def query_organization_members_with_role(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of users who are members of this organization.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come
            after the specified cursor.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).members_with_role(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "organization",
        "membersWithRole",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["membersWithRole"]


@task
async def query_organization_enterprise_owners(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    query: str = None,
    organization_role: graphql_schema.RoleInOrganization = None,
    order_by: graphql_schema.OrgEnterpriseOwnerOrder = {
        "field": "LOGIN",
        "direction": "ASC",
    },
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of owners of the organization's enterprise account.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        query: The search string to look for.
        organization_role: The organization role to filter by.
        order_by: Ordering options for enterprise owners
            returned from the connection.
        after: Returns the elements in the list that come
            after the specified cursor.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).enterprise_owners(
        **strip_kwargs(
            query=query,
            organization_role=organization_role,
            order_by=order_by,
            after=after,
            before=before,
            first=first,
            last=last,
        )
    )

    op_stack = (
        "organization",
        "enterpriseOwners",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["enterpriseOwners"]


@task
async def query_organization_sponsors_activities(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).sponsors_activities(
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
        "organization",
        "sponsorsActivities",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["sponsorsActivities"]


@task
async def query_organization_interaction_ability(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The interaction ability settings for this organization.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).interaction_ability(**strip_kwargs())

    op_stack = (
        "organization",
        "interactionAbility",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["interactionAbility"]


@task
async def query_organization_ip_allow_list_entries(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    order_by: graphql_schema.IpAllowListEntryOrder = {
        "field": "ALLOW_LIST_VALUE",
        "direction": "ASC",
    },
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The IP addresses that are allowed to access resources owned by the organization.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come
            after the specified cursor.
        before: Returns the elements in the list that come
            before the specified cursor.
        first: Returns the first _n_ elements from the
            list.
        last: Returns the last _n_ elements from the list.
        order_by: Ordering options for IP allow list
            entries returned.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).ip_allow_list_entries(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
        )
    )

    op_stack = (
        "organization",
        "ipAllowListEntries",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["ipAllowListEntries"]


@task
async def query_organization_repository_migrations(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    after: str = None,
    before: str = None,
    first: int = None,
    last: int = None,
    state: graphql_schema.MigrationState = None,
    repository_name: str = None,
    order_by: graphql_schema.RepositoryMigrationOrder = {
        "field": "CREATED_AT",
        "direction": "ASC",
    },
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    A list of all repository migrations for this organization.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        after: Returns the elements in the list that come
            after the specified cursor.
        before: Returns the elements in the list that come
            before the specified cursor.
        first: Returns the first _n_ elements from the
            list.
        last: Returns the last _n_ elements from the list.
        state: Filter repository migrations by state.
        repository_name: Filter repository migrations by
            repository name.
        order_by: Ordering options for repository
            migrations returned.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).repository_migrations(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            state=state,
            repository_name=repository_name,
            order_by=order_by,
        )
    )

    op_stack = (
        "organization",
        "repositoryMigrations",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["repositoryMigrations"]


@task
async def query_organization_saml_identity_provider(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The Organization's SAML identity providers.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).saml_identity_provider(**strip_kwargs())

    op_stack = (
        "organization",
        "samlIdentityProvider",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["samlIdentityProvider"]


@task
async def query_organization_repository_discussions(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).repository_discussions(
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
        "organization",
        "repositoryDiscussions",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["repositoryDiscussions"]


@task
async def query_organization_sponsorships_as_sponsor(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).sponsorships_as_sponsor(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
        )
    )

    op_stack = (
        "organization",
        "sponsorshipsAsSponsor",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["sponsorshipsAsSponsor"]


@task
async def query_organization_sponsorship_newsletters(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).sponsorship_newsletters(
        **strip_kwargs(
            after=after,
            before=before,
            first=first,
            last=last,
            order_by=order_by,
        )
    )

    op_stack = (
        "organization",
        "sponsorshipNewsletters",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["sponsorshipNewsletters"]


@task
async def query_organization_sponsorships_as_maintainer(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).sponsorships_as_maintainer(
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
        "organization",
        "sponsorshipsAsMaintainer",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["sponsorshipsAsMaintainer"]


@task
async def query_organization_repository_discussion_comments(  # noqa
    login: str,
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
        login: The organization's login.
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
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).repository_discussion_comments(
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
        "organization",
        "repositoryDiscussionComments",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["repositoryDiscussionComments"]


@task
async def query_organization_sponsorship_for_viewer_as_sponsor(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The sponsorship from the viewer to this user/organization; that is, the
    sponsorship where you're the sponsor. Only returns a sponsorship if it is
    active.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).sponsorship_for_viewer_as_sponsor(**strip_kwargs())

    op_stack = (
        "organization",
        "sponsorshipForViewerAsSponsor",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["sponsorshipForViewerAsSponsor"]


@task
async def query_organization_sponsorship_for_viewer_as_sponsorable(  # noqa
    login: str,
    github_credentials: GitHubCredentials,
    return_fields: Iterable[str] = None,
) -> Dict[str, Any]:  # pragma: no cover
    """
    The sponsorship from this user/organization to the viewer; that is, the
    sponsorship you're receiving. Only returns a sponsorship if it is active.

    Args:
        login: The organization's login.
        github_credentials: Credentials to use for authentication with GitHub.
        return_fields: Subset the return fields (as snake_case); defaults to
            fields listed in configs/query/*.json.

    Returns:
        A dict of the returned fields.
    """
    op = Operation(graphql_schema.Query)
    op_selection = op.organization(
        **strip_kwargs(
            login=login,
        )
    ).sponsorship_for_viewer_as_sponsorable(**strip_kwargs())

    op_stack = (
        "organization",
        "sponsorshipForViewerAsSponsorable",
    )
    op_selection = _subset_return_fields(
        op_selection, op_stack, return_fields, return_fields_defaults
    )

    result = await _execute_graphql_op(op, github_credentials)
    return result["organization"]["sponsorshipForViewerAsSponsorable"]

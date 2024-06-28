import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Union

import httpx

GITHUB_REPO = "PrefectHQ/prefect"
TOKEN_REGEX = re.compile(r"\s* Token:\s(.*)")
ENGAGEMENT_THRESHOLD = 5  # Number of comments to consider an issue high engagement
LABEL_REMOVAL_INTERVAL_MONTHS = (
    1  # Buffer number of months to wait before re-adding the "Needs Priority" label
)

PROJECT_ID = "PVT_kwDOAlc6B84AGBLE"
FIELD_ID = "PVTSSF_lADOAlc6B84AGBLEzgDd_O0"
ORGANIZATION = "PrefectHQ"
PROJECT_NUMBER = 35

project_items_cache = None
single_select_options_cache = None


def get_github_token() -> str:
    """
    Retrieve the current GitHub token from the `gh` CLI or environment variables.
    """
    if "GITHUB_TOKEN" in os.environ:
        return os.environ["GITHUB_TOKEN"]

    if not shutil.which("gh"):
        print(
            "You must provide a GitHub access token via GITHUB_TOKEN or have the gh CLI"
            " installed."
        )
        exit(1)

    gh_auth_status = subprocess.run(
        ["gh", "auth", "status", "--show-token"], capture_output=True
    )
    output = gh_auth_status.stdout.decode()
    if not gh_auth_status.returncode == 0:
        print(
            "Failed to retrieve authentication status from GitHub CLI:", file=sys.stderr
        )
        print(output, file=sys.stderr)
        exit(1)

    match = TOKEN_REGEX.search(output)
    if not match:
        print(
            (
                "Failed to find token in GitHub CLI output with regex"
                f" {TOKEN_REGEX.pattern!r}:"
            ),
            file=sys.stderr,
        )
        print(output, file=sys.stderr)
        exit(1)

    return match.groups()[0]


def get_high_engagement_issues(headers: dict) -> list:
    """
    Fetch all high engagement issues from the repository.

    Args:
        headers (dict): HTTP headers for GitHub API requests.

    Returns:
        list: List of high engagement issues.
    """
    all_issues = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
        params = {
            "state": "open",
            "sort": "comments",
            "direction": "desc",
            "per_page": per_page,
            "page": page,
        }
        response = httpx.get(url, headers=headers, params=params)
        response.raise_for_status()
        issues = response.json()

        if not issues:
            break

        all_issues.extend(issues)
        page += 1
        print(f"Fetched page {page} with {len(issues)} issues")

    high_engagement_issues = [
        issue for issue in all_issues if issue["comments"] >= ENGAGEMENT_THRESHOLD
    ]
    print(f"Total high engagement issues: {len(high_engagement_issues)}")
    return high_engagement_issues


def issue_has_new_comment(issue, new_comment_interval_days, headers: dict) -> bool:
    """
    Check if an issue has a new comment within the specified interval.

    Args:
        issue (dict): The issue to check.
        new_comment_interval_days (int): Interval in days to check for new comments.
        headers (dict): HTTP headers for GitHub API requests.

    Returns:
        bool: True if there is a new comment within the interval, False otherwise.
    """
    comments_url = issue["comments_url"]
    response = httpx.get(comments_url, headers=headers)
    response.raise_for_status()
    comments = response.json()

    if comments:
        latest_comment = max(comments, key=lambda comment: comment["created_at"])
        latest_comment_date = datetime.strptime(
            latest_comment["created_at"], "%Y-%m-%dT%H:%M:%SZ"
        )
        if latest_comment_date > datetime.utcnow() - timedelta(
            days=new_comment_interval_days
        ):
            return True
    return False


def prioritized_recently(issue_number: int, headers: dict) -> bool:
    """
    An issue is considered to have been prioritized recently if it was removed within the last LABEL_REMOVAL_INTERVAL_MONTHS months.
    We don't want to re-add the "Needs Priority" label if it was removed recently as there is likely to be further discussion
    on this issue right after the issue is prioritized and the label is removed.

    It's possible we may want to increase the LABEL_REMOVAL_INTERVAL_MONTHS to a larger value if we find that the label is being
    re-added too frequently.

    Args:
        issue_number (int): The number of the issue.
        headers (dict): HTTP headers for GitHub API requests.

    Returns:
        bool: True if the issue was prioritized recently, False otherwise.
    """
    timeline_url = (
        f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}/timeline"
    )
    params = {"per_page": 100}
    response = httpx.get(timeline_url, headers=headers, params=params)
    response.raise_for_status()
    events = response.json()

    for event in events:
        if event["event"] == "unlabeled" and event["label"]["name"] == "needs:priority":
            unlabeled_date = datetime.strptime(
                event["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            )
            if unlabeled_date > datetime.utcnow() - timedelta(
                days=LABEL_REMOVAL_INTERVAL_MONTHS * 30
            ):
                return True
    return False


def get_issue_id(issue_number: int, headers: dict) -> str:
    """
    Retrieve the ID of an issue given its number.

    Args:
        issue_number (int): The number of the issue.
        headers (dict): HTTP headers for GitHub API requests.

    Returns:
        str: The ID of the issue.
    """
    query = """
    query($owner: String!, $repo: String!, $issueNumber: Int!) {
      repository(owner: $owner, name: $repo) {
        issue(number: $issueNumber) {
          id
        }
      }
    }
    """
    variables = {"owner": "PrefectHQ", "repo": "prefect", "issueNumber": issue_number}
    url = "https://api.github.com/graphql"
    response = httpx.post(
        url, headers=headers, json={"query": query, "variables": variables}
    )
    response.raise_for_status()
    data = response.json()
    try:
        assert data is not None
        assert "errors" not in data
        issue_id = data["data"]["repository"]["issue"]["id"]
        print(f"Retrieved issue ID: {issue_id}")
    except Exception:
        print(f"Failed to retrieve issue ID for issue #{issue_number}: {data}")

    return issue_id


def get_all_project_items(headers) -> list:
    """
    Retrieve all project items from the project.

    Args:
        headers (dict): HTTP headers for GitHub API requests.

    Returns:
        list: List of project items.
    """
    global project_items_cache
    if project_items_cache is not None:
        return project_items_cache

    all_items = []
    cursor = None
    has_next_page = True

    while has_next_page:
        query = """
        query($organization: String!, $projectNumber: Int!, $after: String) {
          organization(login: $organization) {
            projectV2(number: $projectNumber) {
              items(first: 100, after: $after) {
                nodes {
                  id
                  content {
                    ... on Issue {
                      id
                    }
                  }
                }
                pageInfo {
                  hasNextPage
                  endCursor
                }
              }
            }
          }
        }
        """
        variables = {"organization": "PrefectHQ", "projectNumber": 35, "after": cursor}
        url = "https://api.github.com/graphql"
        response = httpx.post(
            url, headers=headers, json={"query": query, "variables": variables}
        )
        response.raise_for_status()
        data = response.json()

        items = data["data"]["organization"]["projectV2"]["items"]["nodes"]
        all_items.extend(items)

        page_info = data["data"]["organization"]["projectV2"]["items"]["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        cursor = page_info["endCursor"]

        # Print debug information
        print(
            f"Retrieved {len(items)} items, has_next_page: {has_next_page}, cursor: {cursor}"
        )

    project_items_cache = all_items
    return all_items


def get_project_item_id(issue_id: str, headers: dict) -> Union[str, None]:
    """
    Retrieve the project item ID for a given issue ID.

    Args:
        issue_id (str): The ID of the issue.
        headers (dict): HTTP headers for GitHub API requests.

    Returns:
        str: The project item ID, or None if not found.
    """
    items = get_all_project_items(headers)
    print(f"Total project items retrieved: {len(items)}")  # Debug statement

    # Print all project item IDs and their content IDs
    for item in items:
        content_id = item["content"]["id"] if item["content"] else "None"
        print(f"Project item ID: {item['id']}, Content ID: {content_id}")

    for item in items:
        if item["content"] and item["content"]["id"] == issue_id:
            project_item_id = item["id"]
            print(f"Matched project item ID: {project_item_id}")
            return project_item_id

    print(f"No match found for issue ID {issue_id}")


def add_issue_to_project(issue_id: str, project_id: str, headers: dict):
    """
    Add an issue to the project.

    Args:
        issue_id (str): The ID of the issue.
        project_id (str): The ID of the project.
        headers (dict): HTTP headers for GitHub API requests.

    Returns:
        str: The ID of the added project item.
    """
    query = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item {
          id
        }
      }
    }
    """
    variables = {"projectId": project_id, "contentId": issue_id}
    url = "https://api.github.com/graphql"
    response = httpx.post(
        url, headers=headers, json={"query": query, "variables": variables}
    )
    response.raise_for_status()
    data = response.json()
    try:
        item_id = data["data"]["addProjectV2ItemById"]["item"]["id"]
        print(f"Added issue to project with item ID: {item_id}")
    except Exception:
        print(f"Failed to add issue to project: {data}")
    return item_id


def add_needs_attention_label(issue_number: int, headers: dict):
    """
    Add a "needs:attention" label to the issue.

    Args:
        issue_number (int): The number of the issue.
        headers (dict): HTTP headers for GitHub API requests.
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}/labels"
    response = httpx.post(url, headers=headers, json=["needs:attention"])
    response.raise_for_status()
    print(f"Added 'needs:attention' label to issue #{issue_number}")


def set_needs_priority_status_on_high_engagement_issues(new_comment_interval_days: int):
    """
    Sets the "Needs Priority" status on high engagement issues with new comments.
    This status is a field on the Prefect Backlog project board.

    Args:
        new_comment_interval_days (int): Interval in days to check for new comments.

    Example:
        python surface_high_engagement_issues.py --new_comment_interval_days 1

        This will check for high engagement issues with new comments within the last day and add the "Needs Priority" status to them.
        You may want to ad-hoc run this for a longer interval. For instance, if you wanted to loop through high-engagement issues that
        have had new comments in the last year, you could run:

        python surface_high_engagement_issues.py --new_comment_interval_days 365
    """
    token = get_github_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    high_engagement_issues = get_high_engagement_issues(headers)
    for issue in high_engagement_issues:
        issue_number = issue["number"]
        if issue_has_new_comment(
            issue, new_comment_interval_days, headers
        ) or not prioritized_recently(issue_number, headers):
            # Issue id is a globally unique identifier
            issue_id = get_issue_id(issue_number, headers)
            project_item_id = get_project_item_id(issue_id, headers)
            if project_item_id is None:
                print(f"Issue #{issue_number} is not in the project. Adding it now.")
                project_item_id = add_issue_to_project(issue_id, PROJECT_ID, headers)
            else:
                print(f"Issue #{issue_number} is already in the project.")
                add_needs_attention_label(issue_number, headers)
                print(
                    f'Added "needs:attention" label to issue #{issue_number} in the project.'
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--new_comment_interval_days",
        type=int,
        default=1,
        help="Interval in days to check for new comments",
    )
    args = parser.parse_args()
    set_needs_priority_status_on_high_engagement_issues(args.new_comment_interval_days)

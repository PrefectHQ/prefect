#!/usr/bin/env python3
"""
This script generates release notes using the GitHub Release API then prints it to
standard output. You must be logged into GitHub using the `gh` CLI tool or provide a
GitHub token via `GITHUB_TOKEN` environment variable.

Usage:

    generate-release-notes.py [<release-tag>] [<target>] [<previous-tag>]

The release tag defaults to `preview` but often should be set to the new version:

    generate-release-notes.py "2.3.0"

The target defaults to `main` but can be set to a different commit or branch:

    generate-release-notes.py "2.3.0" "my-test-branch"

The previous tag defaults to the last tag, but can be set to a different tag to view
release notes for a different release. In this case, the target must be provided too.

    generate-release-notes.py "2.3.3" "main" "2.3.2"
"""
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from typing import List

import httpx

REPO_ORG = "PrefectHQ"
REPO_NAMES = [
    "prefect",
    "prefect-ui-library",
    "prefect-azure",
    "prefect-aws",
    "prefect-gcp",
]
DEFAULT_TAG = "preview"

TOKEN_REGEX = re.compile(r"\s* Token:\s(.*)")
ENTRY_REGEX = re.compile(r"^\* (.*) by @(.*) in (.*)$", re.MULTILINE)


PREFECTIONISTS = {
    "aaazzam",
    "abrookins",
    "aimeemcmanus",
    "arhead7",
    "biancaines",
    "billpalombi",
    "bunchesofdonald",
    "chrisguidry",
    "collincchoy",
    "desertaxle",
    "discdiver",
    "dylanbhughes",
    "EmilRex",
    "gabcoyne",
    "jakekaplan",
    "jeanluciano",
    "jimid27",
    "jlowin",
    "justin-prefect",
    "kevingrismore",
    "marvin-robot",
    "masonmenges",
    "neha-julka",
    "parkedwards",
    "pleek91",
    "prefectcboyd",
    "robfreedy",
    "Sahiler",
    "sarahbanana09",
    "sarahmk125",
    "seanpwlms",
    "serinamarie",
    "SMPrefect",
    "taylor-curran",
    "tess-dicker",
    "thomas-te",
    "WillRaphaelson",
    "zangell44",
    "zhen0",
    "znicholasbrown",
    "zzstoatzz",
}


def get_latest_repo_release_date(repo_org: str, repo_name: str) -> datetime:
    """
    Retrieve the latest release date for a repository.
    """
    response = httpx.get(
        f"https://api.github.com/repos/{repo_org}/{repo_name}/releases/latest"
    )
    if response.status_code == 200:
        release_date_str = response.json()["published_at"]
        return datetime.fromisoformat(release_date_str.replace("Z", "+00:00"))
    raise Exception(
        f"Failed to retrieve latest {repo_name} release date: {response.json()}"
    )


def get_latest_and_previous_releases(
    repo_org: str, repo_name: str, github_token: str
) -> tuple:
    """
    Retrieves the latest and the previous release tags for the specified repository.
    """

    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    response = httpx.get(
        f"https://api.github.com/repos/{repo_org}/{repo_name}/releases", headers=headers
    )
    response.raise_for_status()
    releases = response.json()

    if not releases:
        raise Exception(f"No releases found for {repo_name}")

    # sort releases by published date
    releases = sorted(releases, key=lambda x: x["published_at"], reverse=True)

    latest_tag = releases[0]["tag_name"]
    previous_tag = releases[1]["tag_name"] if len(releases) > 1 else None

    return latest_tag, previous_tag


def generate_release_notes(
    repo_org: str,
    repo_names: List[str],
    tag_name: str,
    github_token: str,
    target_commit: str,
    previous_tag: str = None,
):
    """
    Generate release notes using the GitHub API.
    """
    integrations_section = []

    latest_prefect_release_date = get_latest_repo_release_date(repo_org, "prefect")

    for repo_name in repo_names:
        if latest_prefect_release_date:
            latest_repo_release_date = get_latest_repo_release_date(repo_org, repo_name)

            repo_has_release_since_latest_prefect_release = (
                latest_repo_release_date >= latest_prefect_release_date
            )
            if not repo_has_release_since_latest_prefect_release:
                continue

        if repo_name != "prefect":
            tag_name, previous_tag = get_latest_and_previous_releases(
                repo_org, repo_name, github_token
            )

        request = {"tag_name": tag_name, "target_commitish": target_commit}
        if previous_tag:
            request["previous_tag_name"] = previous_tag

        response = httpx.post(
            f"https://api.github.com/repos/{repo_org}/{repo_name}/releases/generate-notes",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_token}",
            },
            json=request,
        )
        if not response.status_code == 200:
            print(
                f"Received status code {response.status_code} from GitHub API:",
                file=sys.stderr,
            )
            print(response.json(), file=sys.stderr)
            exit(1)

        release_notes = response.json()["body"]

        if repo_name == "prefect":
            # Drop the first line of the release notes ("## What's Changed")
            release_notes = "\n".join(release_notes.splitlines()[1:])
            # Add newlines before all categories
            release_notes = release_notes.replace("\n###", "\n\n###")
            # Update 'what's new' to 'release tag'
            release_notes = release_notes.replace(
                "## What's Changed", f"## Release {tag_name}"
            )
            # Parse all entries
            entries = ENTRY_REGEX.findall(release_notes)
            # Generate a contributors section
            contributors = ""
            for contributor in sorted(set(user for _, user, _ in entries)):
                if contributor not in PREFECTIONISTS:
                    contributors += f"\n- @{contributor}"

            # Replace the heading of the existing contributors section; append contributors
            release_notes = release_notes.replace(
                "\n**Full Changelog**:",
                "### Contributors" + contributors + "\n\n**All changes**:",
            )
            # Strip contributors from individual entries
            release_notes = ENTRY_REGEX.sub(
                lambda match: f"- {match.group(1)} — {match.group(3)}",
                release_notes,
            )
            prefect_release_notes = release_notes

        else:
            # Drop the first line of the release notes ("## What's Changed")
            # and drop the change preview and the contributors sections
            release_notes = "\n".join(release_notes.splitlines()[1:])
            # Add newlines before all categories
            release_notes = release_notes.replace("\n###", "\n\n###")
            # Parse all entries
            entries = ENTRY_REGEX.findall(release_notes)

            # Strip contributors from individual entries
            release_notes = ENTRY_REGEX.sub(
                lambda match: f"- {match.group(1)} — {match.group(3)}",
                release_notes,
            )

            # we won't include the full changelog and integrations contributors
            search_strings = [
                "## New Contributors",
                "## Contributors",
                "**Full Changelog**",
            ]
            indices = [release_notes.find(s) for s in search_strings]
            indices = [i for i in indices if i != -1]

            if indices:
                split_index = min(indices)
                changelog = release_notes[:split_index].strip()
            else:
                changelog = release_notes.strip()

            integrations_section.append(changelog)

    if integrations_section != [""]:
        parts = prefect_release_notes.split("### Contributors")
        # ensure that Integrations section is before Contributors
        # Print all accumulated non-Prefect changes under "Integrations"
        integrations_heading = "### Integrations" + "\n".join(integrations_section)

        prefect_release_notes = (
            parts[0] + integrations_heading + "\n\n### Contributors" + parts[1]
        )

    print(prefect_release_notes)


def get_github_token() -> str:
    """
    Retrieve the current GitHub token from the `gh` CLI.
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


if __name__ == "__main__":
    generate_release_notes(
        REPO_ORG,
        REPO_NAMES,
        tag_name=sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TAG,
        target_commit=sys.argv[2] if len(sys.argv) > 2 else "main",
        previous_tag=sys.argv[3] if len(sys.argv) > 3 else None,
        github_token=get_github_token(),
    )

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from gh_util.functions import create_repo_tag
from packaging.version import Version

INTEGRATIONS_BASEPATH = "src/integrations"
OWNER = "prefecthq"
REPO = "prefect"


def get_changed_files(previous_tag: str, current_commit: str) -> List[str]:
    cmd = f"git diff --name-only {previous_tag}..{current_commit}"
    output = subprocess.check_output(cmd, shell=True, text=True)
    return output.strip().split("\n")


def increment_patch_version(version: str) -> str:
    v = Version(version)
    return f"{v.major}.{v.minor}.{v.micro + 1}"


def get_latest_tag_version(integration_name: str) -> str:
    cmd = (
        f"git tag --list '*-{integration_name}' "
        "--sort=-v:refname --format='%(refname:short)' | head -n1"
    )
    output = subprocess.check_output(cmd, shell=True, text=True)
    tag_name = output.strip()
    if tag_name:
        return tag_name.split("-")[-1]

    raise ValueError(f"Tag not found for {integration_name}")


def get_changed_integrations(
    changed_files: List[str], glob_pattern: str
) -> Dict[str, str]:
    integrations_base_path = Path(INTEGRATIONS_BASEPATH)
    changed_integrations = {}
    modified_integrations_files = [
        file_path
        for file_path in changed_files
        if Path(file_path).match(glob_pattern)
        and integrations_base_path in Path(file_path).parents
    ]
    for file_path in modified_integrations_files:
        path = Path(file_path)
        integration_name = path.parent.name
        current_version = get_latest_tag_version(integration_name)
        changed_integrations[integration_name] = increment_patch_version(
            current_version
        )
    return changed_integrations


async def create_tags(changed_integrations: Dict[str, str]) -> None:
    for integration_name, version in changed_integrations.items():
        await create_repo_tag(
            owner=OWNER,
            repo=REPO,
            tag_name=f"{integration_name}-{version}",
            commit_sha=os.environ.get("CURRENT_COMMIT", ""),
            message=f"Release {integration_name} {version}",
        )


async def main(glob_pattern: str = "**/*.py"):
    previous_tag = os.environ.get("PREVIOUS_TAG", "")
    current_commit = os.environ.get("CURRENT_COMMIT", "")

    if not previous_tag or not current_commit:
        print(
            "Error: `PREVIOUS_TAG` or `CURRENT_COMMIT` environment variable is missing."
        )
        return

    changed_files = get_changed_files(previous_tag, current_commit)
    changed_integrations = get_changed_integrations(changed_files, glob_pattern)
    print(json.dumps(changed_integrations))

    if changed_integrations:
        await create_tags(changed_integrations)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(main(sys.argv[1]))
    else:
        asyncio.run(main())

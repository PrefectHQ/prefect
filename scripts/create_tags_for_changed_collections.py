import asyncio
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


async def get_changed_integrations(
    changed_files: List[str], glob_pattern: str
) -> Dict[str, str]:
    integrations_base_path = Path(INTEGRATIONS_BASEPATH)
    changed_integrations = {}
    modified_integrations_files = [
        file_path
        for file_path in changed_files
        if Path(file_path).match(glob_pattern)
        and integrations_base_path in Path(file_path).parents
        and Path(file_path).parent.name.startswith("prefect_")
    ]
    for file_path in modified_integrations_files:
        path = Path(file_path)
        integration_name = path.parent.name.replace("_", "-")
        command = f"git tag --list 'prefect-*' --sort=-version:refname | grep -E '^{integration_name}-' | head -n 1"
        try:
            latest_tag = subprocess.check_output(command, shell=True, text=True).strip()
            latest_ref = latest_tag.split("-")[-1]
            print(f"Latest ref for {integration_name}: {latest_ref}")
        except subprocess.CalledProcessError:
            print(f"No tags found for {integration_name}")
            continue

        changed_integrations[integration_name] = increment_patch_version(latest_ref)

    print(changed_integrations)

    return changed_integrations


async def create_tags(changed_integrations: Dict[str, str], dry_run: bool = False):
    for integration_name, version in changed_integrations.items():
        tag_name = f"{integration_name}-{version}".replace("_", "-")
        if dry_run:
            print(f"Would create tag {tag_name} for integration {integration_name}")
            continue
        await create_repo_tag(
            owner=OWNER,
            repo=REPO,
            tag_name=tag_name,
            commit_sha=os.environ.get("CURRENT_COMMIT", ""),
            message=f"Release {integration_name} {version}",
        )


async def main(glob_pattern: str = "**/*.py", dry_run: bool = False):
    previous_tag = os.environ.get("PREVIOUS_TAG", "")
    current_commit = os.environ.get("CURRENT_COMMIT", "")

    if not previous_tag or not current_commit:
        raise ValueError(
            "Error: `PREVIOUS_TAG` or `CURRENT_COMMIT` environment variable is missing."
        )

    changed_files = get_changed_files(previous_tag, current_commit)

    if changed_integrations := await get_changed_integrations(
        changed_files, glob_pattern
    ):
        await create_tags(changed_integrations, dry_run=dry_run)


if __name__ == "__main__":
    glob_pattern = sys.argv[1] if len(sys.argv) > 1 else "**/*.py"
    dry_run = sys.argv[2] == "--dry-run" if len(sys.argv) > 2 else False

    asyncio.run(main(glob_pattern=glob_pattern, dry_run=dry_run))

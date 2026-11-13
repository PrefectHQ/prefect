"""Refresh Docker integration constraints after publication or on a weekly sweep."""

import datetime
import json
import os
import re
import subprocess
import time
import tomllib
from pathlib import Path

from packaging.version import Version


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def pins() -> dict[str, str]:
    with Path("uv.lock").open("rb") as f:
        return {
            p["name"]: p["version"]
            for p in tomllib.load(f)["package"]
            if p["name"].startswith("prefect-") and "version" in p
        }


def release(tag: str) -> tuple[str, str]:
    match = re.fullmatch(r"(prefect-[a-z0-9-]+)-(\d[^/]*)", tag)
    if not match:
        raise ValueError(f"Invalid integration tag: {tag}")
    package, version = match.groups()
    return package, str(Version(version))


def upgrade(package: str, version: str, attempts: int = 6) -> None:
    # Do not downgrade a newer pin when an older release is retried.
    if Version(pins()[package]) >= Version(version):
        return
    for attempt in range(attempts):
        try:
            run(
                "uv",
                "lock",
                "--refresh-package",
                package,
                "--upgrade-package",
                f"{package}=={version}",
            )
            if Version(pins()[package]) != Version(version):
                raise RuntimeError(f"Lock does not contain {package}=={version}")
            return
        except (subprocess.CalledProcessError, RuntimeError):
            if attempt == attempts - 1:
                raise
            # PyPI's index may lag successful upload. Never publish a stale update.
            time.sleep(30)


def prepare_branch(branch: str) -> tuple[str, bool]:
    prs = json.loads(
        run(
            "gh",
            "pr",
            "list",
            "--head",
            branch,
            "--base",
            "main",
            "--state",
            "all",
            "--json",
            "state,url",
        )
    )
    open_pr = any(pr["state"] == "OPEN" for pr in prs)
    if prs and not open_pr:
        # Retained branches from closed/merged PRs must not suppress a new update.
        branch += f"-{os.environ['GITHUB_RUN_ID']}-{os.environ['GITHUB_RUN_ATTEMPT']}"
    remote = run("git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}")
    if remote:
        run("git", "fetch", "origin", f"refs/heads/{branch}")
        run("git", "checkout", "-B", branch, "FETCH_HEAD")
        # Preserve existing commits and refuse to overwrite unrelated changes.
        changed = run("git", "diff", "--name-only", "origin/main...HEAD").splitlines()
        if any(path != "uv.lock" for path in changed):
            raise RuntimeError(
                f"Unexpected changes on {branch}; manual review required"
            )
        run("git", "merge", "--no-edit", "origin/main")
    else:
        run("git", "checkout", "-b", branch, "origin/main")
    return branch, open_pr


def main() -> None:
    tag = os.environ.get("RELEASE_TAG", "")
    package, version = release(tag) if tag else ("", "")
    if package and package not in pins():
        print(f"{package} is not in uv.lock; nothing to update")
        return
    branch = (
        f"automation/uv-lock-{package}-{version}"
        if tag
        else f"automation/uv-lock-sweep-{datetime.date.today():%Y%m%d}"
    )
    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "github-actions[bot]@users.noreply.github.com")
    branch, open_pr = prepare_branch(branch)
    before = pins()
    if package:
        upgrade(package, version)
    else:
        args = [arg for name in sorted(before) for arg in ("--upgrade-package", name)]
        if args:
            run("uv", "lock", *args)
    after = pins()
    if run("git", "diff", "--name-only", "--", "uv.lock"):
        run("git", "add", "uv.lock")
        run("git", "commit", "-m", "Update released integration pins in uv.lock")
    # Recover an earlier successful push even if there are no new lock changes.
    if not run("git", "diff", "origin/main...HEAD", "--", "uv.lock"):
        print("Integration pins already current")
        return
    run("git", "push", "--set-upstream", "origin", branch)
    if not open_pr:
        title = (
            f"Update {package} integration pin"
            if package
            else "Sweep stale integration pins in uv.lock"
        )
        body = "Update Docker integration constraints in uv.lock. " + (
            f"After publication of {tag}, verified {package}=={after[package]}."
            if tag
            else "Weekly integration maintenance."
        )
        run(
            "gh",
            "pr",
            "create",
            "--base",
            "main",
            "--head",
            branch,
            "--title",
            title,
            "--body",
            body,
        )


if __name__ == "__main__":
    main()

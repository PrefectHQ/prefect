#!/usr/bin/env python3
"""
Prepare release notes for Prefect integration packages.
This script generates release notes from commits since the last release.

USAGE:
======
Run this script to generate release notes for any integration package:
  `just prepare-integration-release PACKAGE`
  or
  `python scripts/prepare_integration_release_notes.py PACKAGE`

Examples:
  `python scripts/prepare_integration_release_notes.py prefect-aws`
  `python scripts/prepare_integration_release_notes.py prefect-docker`
  `python scripts/prepare_integration_release_notes.py --list`

The script will:
- Find the latest release tag for the specified integration package
- Generate release notes from commits that affect the package since that tag
- Apply formatting transformations (GitHub users to links, PR URLs, etc.)
- Save the formatted release notes to a markdown file
- Display the release notes for review

WORKFLOW:
=========
1. Run this script with the integration package name
2. Review the generated release notes
3. Use the output for GitHub releases or documentation

FORMATTING:
===========
- ### and #### headers are converted to bold text to reduce nav clutter
- GitHub usernames are converted to links (@username -> [@username](https://github.com/username))
- PR URLs are converted to short format with links
- Version constraints like <0.14.0,>=0.12.0 are wrapped in backticks
- Dates are formatted as "Month Day, Year" on a separate line
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any


def run_command(cmd: list[str]) -> str:
    """Run a command and return its output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(cmd)}: {e}", file=sys.stderr)
        print(f"stderr: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def get_available_packages() -> list[str]:
    """Get list of available integration packages."""
    integrations_dir = "src/integrations"
    if not os.path.exists(integrations_dir):
        print(f"Integration directory {integrations_dir} not found", file=sys.stderr)
        sys.exit(1)

    packages = []
    for item in os.listdir(integrations_dir):
        path = os.path.join(integrations_dir, item)
        if os.path.isdir(path) and item.startswith("prefect-"):
            packages.append(item)

    return sorted(packages)


def get_latest_package_tag(package_name: str) -> str:
    """Get the latest release tag for the given package."""
    cmd = ["gh", "api", "repos/PrefectHQ/prefect/tags", "--paginate"]
    output = run_command(cmd)

    tags = json.loads(output)
    package_tags = [
        tag["name"] for tag in tags if tag["name"].startswith(f"{package_name}-")
    ]

    if not package_tags:
        print(f"No {package_name} tags found", file=sys.stderr)
        sys.exit(1)

    # Tags are already sorted by creation date (newest first)
    return package_tags[0]


def extract_pr_info(commit_subject: str) -> dict[str, str] | None:
    """Extract PR number and title from commit subject."""
    # Match patterns like: "Fix something (#1234)" or "Add feature (#5678)"
    pr_pattern = r"^(.+?)\s*\(#(\d+)\)$"
    match = re.match(pr_pattern, commit_subject.strip())

    if match:
        title = match.group(1).strip()
        pr_number = match.group(2)
        return {"title": title, "pr_number": pr_number}

    return None


def get_pr_data(pr_number: str) -> dict[str, Any]:
    """Get PR data including author and labels using GitHub CLI."""
    try:
        cmd = ["gh", "pr", "view", pr_number, "--json", "author,labels"]
        output = run_command(cmd)
        pr_data = json.loads(output)

        author = pr_data.get("author", {}).get("login", "unknown")
        labels = [label.get("name", "") for label in pr_data.get("labels", [])]

        return {"author": author, "labels": labels}
    except Exception:
        return {"author": "unknown", "labels": []}


def get_commits_since_tag(tag: str, package_name: str) -> list[dict[str, Any]]:
    """Get all commits that affect the given package since the given tag."""
    # Get commits since the tag that touch the package directory
    cmd = [
        "git",
        "log",
        f"{tag}..HEAD",
        "--oneline",
        "--pretty=format:%s",
        "--",
        f"src/integrations/{package_name}/",
    ]

    output = run_command(cmd)

    if not output:
        return []

    prs = []
    seen_prs = set()

    for line in output.split("\n"):
        if line.strip():
            pr_info = extract_pr_info(line.strip())
            if pr_info and pr_info["pr_number"] not in seen_prs:
                # Get PR data (author and labels) from GitHub
                pr_data = get_pr_data(pr_info["pr_number"])

                prs.append(
                    {
                        "title": pr_info["title"],
                        "pr_number": pr_info["pr_number"],
                        "author": pr_data["author"],
                        "labels": pr_data["labels"],
                    }
                )
                seen_prs.add(pr_info["pr_number"])

    return prs


def categorize_prs(
    prs: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Categorize PRs by type based on their GitHub labels."""
    categories = {
        "Features": [],
        "Bug Fixes": [],
        "Documentation": [],
        "Maintenance": [],
        "Other": [],
    }

    # Define label to category mappings
    label_mappings = {
        "Features": ["enhancement", "feature", "new feature"],
        "Bug Fixes": ["bug", "bugfix", "fix"],
        "Documentation": ["documentation", "docs"],
        "Maintenance": ["maintenance", "chore", "dependencies", "refactor", "cleanup"],
    }

    for pr in prs:
        labels = [label.lower() for label in pr.get("labels", [])]
        categorized = False

        # Try to categorize based on labels
        for category, category_labels in label_mappings.items():
            if any(label in labels for label in category_labels):
                categories[category].append(pr)
                categorized = True
                break

        # Fallback to title-based categorization if no matching labels
        if not categorized:
            title = pr["title"].lower()

            if any(
                word in title for word in ["feat", "add", "implement", "support", "new"]
            ):
                categories["Features"].append(pr)
            elif any(word in title for word in ["fix", "bug", "resolve", "correct"]):
                categories["Bug Fixes"].append(pr)
            elif any(word in title for word in ["doc", "readme", "comment"]):
                categories["Documentation"].append(pr)
            elif any(
                word in title
                for word in ["refactor", "clean", "update", "bump", "chore", "test"]
            ):
                categories["Maintenance"].append(pr)
            else:
                categories["Other"].append(pr)

    return categories


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse version string into major, minor, patch."""
    parts = version_str.split(".")
    return int(parts[0]), int(parts[1]), int(parts[2] if len(parts) > 2 else 0)


def bump_version(version_str: str) -> str:
    """Bump the micro (patch) version by 1."""
    major, minor, patch = parse_version(version_str)
    return f"{major}.{minor}.{patch + 1}"


def format_release_notes(
    tag: str, package_name: str, categorized_prs: dict[str, list[dict[str, Any]]]
) -> str:
    """Format the PRs into release notes."""
    total_prs = sum(len(prs) for prs in categorized_prs.values())

    # Extract version from tag (e.g., "prefect-aws-0.5.13" -> "0.5.13")
    current_version = tag.split("-")[-1] if "-" in tag else tag

    # Bump to next version for release notes
    next_version = bump_version(current_version)

    if total_prs == 0:
        return f"## {next_version}\n\n_Released on {datetime.now().strftime('%B %d, %Y')}_\n\nNo changes to {package_name} found since the last release.\n"

    # Format the header with next version
    notes = [f"## {next_version}"]
    notes.append(f"\n_Released on {datetime.now().strftime('%B %d, %Y')}_\n")

    for category, prs in categorized_prs.items():
        if prs:
            # Convert category headers to bold text (matching main release notes style)
            notes.append(f"**{category}**")
            notes.append("")  # Blank line after header

            for pr in prs:
                title = pr["title"]
                pr_number = pr["pr_number"]
                author = pr["author"]

                # Apply formatting transformations to title
                title = format_pr_title(title)

                # Create PR link and author link
                pr_link = f"[#{pr_number}](https://github.com/PrefectHQ/prefect/pull/{pr_number})"
                author_link = f"[@{author}](https://github.com/{author})"

                notes.append(f"- {title} {pr_link} by {author_link}")
            notes.append("")  # Blank line after section

    body = "\n".join(notes).strip() + "\n"

    return body


def format_pr_title(title: str) -> str:
    """Apply formatting transformations to PR titles."""
    # Fix version constraints by wrapping them in backticks
    version_pattern = r"(?<!`)([<>]=?[\d\.]+(?:,\s*[<>]=?[\d\.]+)*)"

    def wrap_version(match):
        version = match.group(1)
        return f"`{version}`"

    title = re.sub(version_pattern, wrap_version, title)

    # Convert GitHub usernames to links in title (avoiding infrastructure decorators)
    infra_decorators = [
        "docker",
        "kubernetes",
        "ecs",
        "process",
        "cloudrun",
        "modal",
        "azure_container",
    ]

    def replace_github_user(match):
        username = match.group(1)
        if username.lower() in infra_decorators:
            return match.group(0)  # Return original text
        return f"[@{username}](https://github.com/{username})"

    github_user_pattern = (
        r"(?<!\w)@([a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})(?![a-zA-Z0-9/-])"
    )
    title = re.sub(github_user_pattern, replace_github_user, title)

    return title


def parse_args():
    """Parse command line arguments."""
    available_packages = get_available_packages()

    parser = argparse.ArgumentParser(
        description="Generate release notes for Prefect integration packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available packages:
{chr(10).join(f"  - {pkg}" for pkg in available_packages)}

Examples:
  python {sys.argv[0]} prefect-aws
  python {sys.argv[0]} prefect-gcp
  python {sys.argv[0]} --list
        """,
    )

    parser.add_argument(
        "package",
        nargs="?",
        help="Name of the integration package (e.g., prefect-aws, prefect-gcp)",
    )

    parser.add_argument(
        "--list", action="store_true", help="List all available integration packages"
    )

    args = parser.parse_args()

    if args.list:
        print("Available integration packages:")
        for pkg in available_packages:
            print(f"  - {pkg}")
        sys.exit(0)

    if not args.package:
        parser.error("Package name is required. Use --list to see available packages.")

    if args.package not in available_packages:
        print(f"Error: Package '{args.package}' not found.", file=sys.stderr)
        print(f"Available packages: {', '.join(available_packages)}", file=sys.stderr)
        sys.exit(1)

    return args


def main():
    """Main function to generate release notes."""
    args = parse_args()
    package_name = args.package

    print(f"🔍 Finding latest {package_name} release...")
    latest_tag = get_latest_package_tag(package_name)
    print(f"📍 Latest release: {latest_tag}")

    print("📝 Getting PRs since last release...")
    prs = get_commits_since_tag(latest_tag, package_name)
    print(f"📊 Found {len(prs)} PR(s) affecting {package_name}")

    if not prs:
        print("✅ No changes found since last release")
        return

    print("🏷️  Categorizing PRs...")
    categorized = categorize_prs(prs)

    print("📋 Generating release notes...")
    release_notes = format_release_notes(latest_tag, package_name, categorized)

    print("\n" + "=" * 60)
    print("RELEASE NOTES")
    print("=" * 60)
    print(release_notes)
    print("=" * 60)

    # Save to the integration documentation directory
    docs_dir = "docs/v3/release-notes/integrations"
    os.makedirs(docs_dir, exist_ok=True)

    output_file = f"{docs_dir}/{package_name}.mdx"

    # Check if file exists to determine if we need frontmatter
    if os.path.exists(output_file):
        # Read existing content and prepend new release
        with open(output_file, "r") as f:
            existing_content = f.read()

        # Find where to insert (after frontmatter)
        lines = existing_content.split("\n")
        insert_index = 0

        # Skip frontmatter
        in_frontmatter = False
        for i, line in enumerate(lines):
            if line.strip() == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    insert_index = i + 2  # After frontmatter and blank line
                    break

        # Insert new release at the top (most recent first)
        lines.insert(insert_index, release_notes.rstrip())
        lines.insert(insert_index + 1, "\n---\n")

        content = "\n".join(lines)
    else:
        # Create new file with frontmatter
        content = f"""---
title: {package_name}
---

{release_notes}
"""

    with open(output_file, "w") as f:
        f.write(content)

    print(f"\n💾 Release notes saved to: {output_file}")


if __name__ == "__main__":
    main()

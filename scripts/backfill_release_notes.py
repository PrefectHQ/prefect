#!/usr/bin/env python3
"""
Backfill release notes documentation from GitHub releases.
This script generates release notes pages for all 3.x releases.

PURPOSE:
========
This script is used to regenerate ALL historical release notes from GitHub.
It should only be needed in these cases:
1. Initial setup of release notes documentation
2. Fixing formatting issues across all releases
3. Recovering from data loss
4. Major restructuring of release notes format

USAGE:
======
Run from the repository root:
    python scripts/backfill_release_notes.py

This will:
1. Fetch all stable 3.x release tags from git
2. Query GitHub API for each release's information
3. Group releases by minor version (3.0, 3.1, 3.2, etc.)
4. Generate one MDX page per minor version with all patches
5. Create the index page and directory structure

DIRECTORY STRUCTURE:
====================
docs/v3/release-notes/
├── index.mdx                    # Main release notes landing page
├── oss/
│   ├── version-3-0.mdx         # All 3.0.x releases
│   ├── version-3-1.mdx         # All 3.1.x releases
│   └── ...
└── cloud/
    └── index.mdx                # Placeholder for cloud releases

FORMATTING:
===========
The script applies several transformations to improve readability:
- Removes "New Contributors" sections (reduce clutter)
- Converts ### headers to **bold text** (simplify right-nav)
- Converts #### headers to **bold text** (for integration subsections)
- Wraps version constraints in backticks (e.g., `<2.0,>=1.5`)
- Removes duplicate headers and "What's Changed" sections
- Formats dates consistently as "Month Day, Year"

REQUIREMENTS:
=============
- Must be run from the Prefect repository root
- Requires 'gh' CLI tool to be installed and authenticated
- Needs git repository with all tags fetched

NOTE: For preparing release notes for a NEW release, use prepare_release_notes.py instead.
"""

import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


def run_command(cmd: list[str]) -> str:
    """Run a command and return its output."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def get_release_tags() -> list[str]:
    """Get all stable release tags for 3.x versions."""
    output = run_command(["git", "tag", "-l", "3.*"])
    tags = output.split("\n") if output else []

    # Filter out rc, dev, and other pre-release versions
    stable_tags = []
    for tag in tags:
        if not any(x in tag for x in ["rc", "dev", "alpha", "beta"]):
            stable_tags.append(tag)

    return sorted(stable_tags, key=lambda x: list(map(int, x.split("."))))


def get_release_info(tag: str) -> dict | None:
    """Get release information from GitHub."""
    try:
        output = run_command(
            ["gh", "release", "view", tag, "--json", "body,name,tagName,publishedAt"]
        )
        return json.loads(output)
    except subprocess.CalledProcessError:
        print(f"Warning: Could not fetch release info for {tag}")
        return None


def parse_version(tag: str) -> tuple[int, int, int]:
    """Parse version string into major, minor, patch."""
    parts = tag.split(".")
    return int(parts[0]), int(parts[1]), int(parts[2] if len(parts) > 2 else 0)


def format_release_notes(release_info: dict) -> str:
    """Format release notes for markdown."""
    body = release_info.get("body", "")
    name = release_info.get("name", "")
    tag = release_info.get("tagName", "")
    date = release_info.get("publishedAt", "")[:10]  # Just the date part

    # Clean up the body
    body = body.replace(
        "<!-- Release notes generated using configuration in .github/release.yml at main -->",
        "",
    ).strip()
    body = body.replace("\r\n", "\n")

    # Remove duplicate headers that might be in the body
    lines = body.split("\n")
    filtered_lines = []

    # Extract just the subtitle part from the name if it exists
    subtitle = ""
    if name and name != tag:
        # Handle various formats of the name
        subtitle = name.replace(tag, "").strip()
        if subtitle.startswith("-"):
            subtitle = subtitle[1:].strip()
        if subtitle.startswith(":"):
            subtitle = subtitle[1:].strip()

    # If no subtitle from name, try to extract from first line of body
    # This handles cases like "## 3.1.5: Like Leftovers, But Async (No More Pi)"
    if not subtitle and lines:
        first_line = lines[0].strip()
        if first_line.startswith(f"## {tag}:") or first_line.startswith(f"# {tag}:"):
            subtitle = first_line.split(":", 1)[1].strip() if ":" in first_line else ""

    skip_next_empty = False
    skip_section = False
    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Skip New Contributors sections entirely
        if line_stripped == "## New Contributors":
            skip_section = True
            continue
        elif skip_section and line_stripped.startswith("##"):
            # We've hit the next section, stop skipping
            skip_section = False
        elif skip_section and line_stripped.startswith("**Full Changelog**"):
            # Keep the Full Changelog line and stop skipping
            skip_section = False
            filtered_lines.append(line)
            continue
        elif skip_section:
            # Skip lines in the New Contributors section
            continue

        # Skip various duplicate header formats
        should_skip = False

        # Check for exact version match headers
        if line_stripped in [f"## {tag}", f"# {tag}", f"## {tag}:", f"# {tag}:"]:
            should_skip = True

        # Check for headers that have version: subtitle format (even when name == tag)
        # This handles cases like "## 3.1.5: Like Leftovers, But Async (No More Pi)"
        if line_stripped.startswith(f"## {tag}:") or line_stripped.startswith(
            f"# {tag}:"
        ):
            should_skip = True

        # Check for subtitle-only headers
        if subtitle:
            # Various subtitle formats
            subtitle_patterns = [
                f"## {subtitle}",
                f"# {subtitle}",
                f"## : {subtitle}",
                f"# : {subtitle}",
                f"##{subtitle}",  # No space
                f"#{subtitle}",  # No space
            ]
            if line_stripped in subtitle_patterns:
                should_skip = True

            # Check for the full duplicate with version and subtitle
            full_patterns = [
                f"## {tag}: {subtitle}",
                f"# {tag}: {subtitle}",
                f"## {tag} - {subtitle}",
                f"# {tag} - {subtitle}",
            ]
            if line_stripped in full_patterns:
                should_skip = True

        # Also check if the line matches our own header format exactly
        # to avoid duplicating what we're already adding
        if (
            line_stripped == f"## {tag} - {subtitle}"
            or line_stripped == f"## {tag} - : {subtitle}"
        ):
            should_skip = True

        # Skip "What's Changed" headers at the beginning (we'll use the content after it)
        if line_stripped in ["## What's Changed", "# What's Changed"]:
            should_skip = True

        if should_skip:
            skip_next_empty = True
            continue

        # Skip empty lines immediately after removed headers
        if skip_next_empty and line_stripped == "":
            skip_next_empty = False
            continue

        skip_next_empty = False

        # Transform ### and #### headers to bold text to reduce nav clutter
        if line.startswith("### "):
            header_text = line[4:].strip()
            # Ensure there's a blank line before the header
            # Check if we need to add spacing
            if filtered_lines:
                # If the last line is not empty, add a blank line
                if filtered_lines[-1].strip():
                    filtered_lines.append("")
            filtered_lines.append(f"**{header_text}**")
            # Always add a blank line after headers for consistent formatting
            filtered_lines.append("")
        elif line.startswith("#### "):
            # Integration subsections - also convert to bold
            header_text = line[5:].strip()
            # Ensure there's a blank line before the header
            # Check if we need to add spacing
            if filtered_lines:
                # If the last line is not empty, add a blank line
                if filtered_lines[-1].strip():
                    filtered_lines.append("")
            filtered_lines.append(f"**{header_text}**")
            # Always add a blank line after headers for consistent formatting
            filtered_lines.append("")
        else:
            # Skip duplicate empty lines that might be in the source after headers
            # This prevents having too many blank lines if source already had spacing
            if line.strip() == "" and filtered_lines and filtered_lines[-1] == "":
                continue
            filtered_lines.append(line)

    body = "\n".join(filtered_lines).strip()

    # Fix problematic patterns for MDX
    # Find version ranges like <0.14.0,>=0.12.0 that aren't already in backticks

    # Pattern to find version constraints not already in backticks
    # Matches patterns like <24.3,>=21.3 or >=0.7.3,<0.9.0
    version_pattern = r"(?<!`)([<>]=?[\d\.]+(?:,\s*[<>]=?[\d\.]+)*)"

    def wrap_version(match):
        version = match.group(1)
        return f"`{version}`"

    # Wrap version constraints in backticks
    body = re.sub(version_pattern, wrap_version, body)

    # Convert GitHub usernames to hyperlinks (e.g., @username -> [@username](https://github.com/username))
    # But avoid matching npm packages like @prefecthq/prefect-ui-library
    # And avoid matching infrastructure decorators like @docker, @kubernetes, @ecs, @process
    # List of known infrastructure decorators to exclude
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
        # Don't convert if it's an infrastructure decorator
        if username.lower() in infra_decorators:
            return match.group(0)  # Return the original text
        return f"[@{username}](https://github.com/{username})"

    github_user_pattern = (
        r"(?<!\w)@([a-zA-Z0-9](?:[a-zA-Z0-9]|-(?=[a-zA-Z0-9])){0,38})(?![a-zA-Z0-9/-])"
    )
    body = re.sub(github_user_pattern, replace_github_user, body)

    # Convert full PR URLs to short format with links
    # e.g., https://github.com/PrefectHQ/prefect/pull/1234 -> [#1234](https://github.com/PrefectHQ/prefect/pull/1234)
    pr_url_pattern = r"https://github\.com/PrefectHQ/prefect/pull/(\d+)"
    body = re.sub(
        pr_url_pattern, r"[#\1](https://github.com/PrefectHQ/prefect/pull/\1)", body
    )

    # Format the patch release section
    patch_title = f"## {tag}"

    # If we have a subtitle, add it to the title
    if subtitle:
        patch_title = f"## {tag} - {subtitle}"
    elif name and name != tag:
        # Fallback to extracting from name if we didn't get subtitle earlier
        name_parts = name.replace(tag, "").strip()
        if name_parts.startswith("-"):
            name_parts = name_parts[1:].strip()
        if name_parts.startswith(":"):
            name_parts = name_parts[1:].strip()
        if name_parts:
            patch_title = f"## {tag} - {name_parts}"

    # Format the date nicely on a separate line
    from datetime import datetime

    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%B %d, %Y")  # e.g., "July 31, 2025"
    except Exception:
        formatted_date = date  # Fallback to original if parsing fails

    return f"{patch_title}\n\n*Released on {formatted_date}*\n\n{body}\n"


def create_release_notes_structure():
    """Create the release notes directory structure and files."""
    base_dir = Path("docs/v3/release-notes")
    base_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    oss_dir = base_dir / "oss"
    cloud_dir = base_dir / "cloud"
    oss_dir.mkdir(exist_ok=True)
    cloud_dir.mkdir(exist_ok=True)

    # Get all release tags
    tags = get_release_tags()

    # Group releases by minor version
    releases_by_minor = defaultdict(list)
    for tag in tags:
        try:
            major, minor, patch = parse_version(tag)
            if major == 3:  # Only process 3.x releases
                releases_by_minor[f"3.{minor}"].append(tag)
        except (ValueError, IndexError):
            print(f"Skipping invalid tag: {tag}")
            continue

    # Create index page
    index_content = """---
title: Release Notes
---

Browse release notes for Prefect OSS and Prefect Cloud.

## Prefect OSS

Release notes for the open-source Prefect orchestration engine.

### Available Versions

"""

    for minor_version in sorted(
        releases_by_minor.keys(),
        key=lambda x: list(map(int, x.split("."))),
        reverse=True,
    ):
        index_content += f"- [Version {minor_version}](/v3/release-notes/oss/version-{minor_version.replace('.', '-')})\n"

    index_content += """

## Prefect Cloud

Release notes for Prefect Cloud features and updates.

*Coming soon*
"""

    with open(base_dir / "index.mdx", "w") as f:
        f.write(index_content)

    # Create release notes for each minor version
    for minor_version, tags in releases_by_minor.items():
        print(f"Processing {minor_version} with {len(tags)} releases...")

        # Sort tags by patch version (descending)
        tags = sorted(tags, key=lambda x: list(map(int, x.split("."))), reverse=True)

        # Create the minor version page
        page_content = f"""---
title: {minor_version}
---

"""

        for tag in tags:
            release_info = get_release_info(tag)
            if release_info:
                page_content += format_release_notes(release_info)
                page_content += "\n---\n\n"

        # Write the page
        filename = f"version-{minor_version.replace('.', '-')}.mdx"
        with open(oss_dir / filename, "w") as f:
            f.write(page_content)

        print(f"  Created {filename}")

    # Create placeholder for Cloud release notes
    cloud_index = """---
title: Prefect Cloud Release Notes
---

# Prefect Cloud Release Notes

Prefect Cloud release notes will be available here soon.
"""

    with open(cloud_dir / "index.mdx", "w") as f:
        f.write(cloud_index)

    print(f"\nRelease notes structure created in {base_dir}")


if __name__ == "__main__":
    create_release_notes_structure()

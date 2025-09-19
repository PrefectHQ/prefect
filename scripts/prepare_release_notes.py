#!/usr/bin/env python3
"""
Prepare release notes documentation for an upcoming release.
This script generates release notes from merged PRs and adds them to the docs.

USAGE:
======
Run this script before creating a new release to prepare the documentation:
  `just prepare-release VERSION [SUBTITLE]`
  or
  `python scripts/prepare_release_notes.py 3.5.0 "Optional Subtitle"`

The script will:
- Generate release notes from merged PRs since the last release
- Apply formatting transformations (remove New Contributors, convert headers to bold)
- Add the release notes to the appropriate minor version page (e.g., version-3-5.mdx)
- Update docs.json to include the new page if needed
- Open the file in your $EDITOR for review

WORKFLOW:
=========
1. Run this script with the upcoming version number
2. Review and edit the generated markdown
3. Commit the changes and create a PR
4. Merge to main before creating the actual GitHub release

FORMATTING:
===========
- New Contributors sections are automatically removed
- ### and #### headers are converted to bold text to reduce nav clutter
- Version constraints like <0.14.0,>=0.12.0 are wrapped in backticks
- Dates are formatted as "Month Day, Year" on a separate line
"""

import json
import re
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str]) -> str:
    """Run a command and return its output."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def generate_release_notes(version: str, subtitle: str = "") -> dict:
    """Generate release notes from merged PRs since the last release."""
    try:
        # Get the previous version tag to use as starting point
        output = run_command(["git", "tag", "-l", "3.*", "--sort=-version:refname"])
        tags = output.split("\n") if output else []

        # Filter out rc, dev, and other pre-release versions
        stable_tags = []
        for tag in tags:
            if not any(x in tag for x in ["rc", "dev", "alpha", "beta"]):
                stable_tags.append(tag)

        previous_tag = stable_tags[0] if stable_tags else None

        # Generate release notes using gh CLI
        cmd = [
            "gh",
            "api",
            "/repos/PrefectHQ/prefect/releases/generate-notes",
            "-X",
            "POST",
            "-f",
            f"tag_name={version}",
        ]

        if previous_tag:
            cmd.extend(["-f", f"previous_tag_name={previous_tag}"])

        output = run_command(cmd)
        result = json.loads(output)

        # Build the release info dict
        release_info = {
            "body": result.get("body", ""),
            "name": f"{version} - {subtitle}" if subtitle else version,
            "tagName": version,
        }

        return release_info
    except subprocess.CalledProcessError as e:
        print(f"Error generating release notes: {e}")
        # Return a basic structure if generation fails
        return {
            "body": "Release notes will be added manually.",
            "name": f"{version} - {subtitle}" if subtitle else version,
            "tagName": version,
        }


def parse_version(tag: str) -> tuple[int, int, int]:
    """Parse version string into major, minor, patch."""
    parts = tag.split(".")
    return int(parts[0]), int(parts[1]), int(parts[2] if len(parts) > 2 else 0)


def format_release_notes(release_info: dict, version: str) -> str:
    """Format release notes for markdown."""
    body = release_info.get("body", "")
    name = release_info.get("name", version)
    tag = version

    # For draft releases, we need to generate a date
    from datetime import datetime

    date = datetime.now().strftime("%Y-%m-%d")

    # Clean up the body
    body = body.replace(
        "<!-- Release notes generated using configuration in .github/release.yml at main -->",
        "",
    ).strip()
    body = body.replace("\r\n", "\n")

    # Remove duplicate headers that might be in the body
    import re

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
            # Omit dependabot-style chores by default (e.g., "chore(deps): ...")
            # This targets conventional commit prefixes for dependency bumps.
            if re.search(r"(?i)chore\(deps", line_stripped):
                continue
            # Omit auto-update documentation PRs (typically from github-actions bot)
            if (
                "auto-update documentation" in line_stripped.lower()
                and "github-actions" in line_stripped.lower()
            ):
                continue
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


def update_minor_version_page(minor_version: str, new_release: str, release_info: dict):
    """Update or create the minor version release notes page."""
    base_dir = Path("docs/v3/release-notes/oss")
    base_dir.mkdir(parents=True, exist_ok=True)

    filename = f"version-{minor_version.replace('.', '-')}.mdx"
    filepath = base_dir / filename

    new_content = format_release_notes(release_info, new_release)

    if filepath.exists():
        # Read existing content
        with open(filepath, "r") as f:
            existing_content = f.read()

        # Find where to insert the new release (after the frontmatter)
        lines = existing_content.split("\n")
        insert_index = 0

        # Skip front matter
        in_frontmatter = False
        for i, line in enumerate(lines):
            if line.strip() == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    insert_index = i + 2  # After frontmatter and blank line
                    break

        # Insert the new release at the top (most recent first)
        lines.insert(insert_index, new_content)
        lines.insert(insert_index + 1, "\n---\n")

        updated_content = "\n".join(lines)
    else:
        # Create new page
        updated_content = f"""---
title: {minor_version}
---

{new_content}

---

"""

    # Write the updated content
    with open(filepath, "w") as f:
        f.write(updated_content)

    print(f"Updated {filepath}")
    return True


def update_docs_json(minor_version: str):
    """Update docs.json to ensure the new version page is included."""
    docs_json_path = Path("docs/docs.json")

    with open(docs_json_path, "r") as f:
        docs_config = json.load(f)

    # Find the Release Notes tab
    tabs = docs_config.get("navigation", {}).get("tabs", [])
    for tab in tabs:
        if tab.get("tab") == "Release Notes":
            # Find OSS group
            for group in tab.get("pages", []):
                if isinstance(group, dict) and group.get("group") == "OSS":
                    # Get all existing release note files
                    oss_dir = Path("docs/v3/release-notes/oss")
                    oss_pages = []

                    if oss_dir.exists():
                        for file in sorted(oss_dir.glob("version-*.mdx")):
                            page_path = f"v3/release-notes/oss/{file.stem}"
                            oss_pages.append(page_path)

                    # Update the pages list (sorted by version, descending)
                    group["pages"] = sorted(oss_pages, reverse=True)

                    # Save the updated config
                    with open(docs_json_path, "w") as f:
                        json.dump(docs_config, f, indent=2)
                        f.write("\n")  # Add trailing newline

                    print(f"Updated {docs_json_path}")
                    return


def main():
    """Main function."""
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python scripts/prepare_release_notes.py <version> [subtitle]")
        print("Example: python scripts/prepare_release_notes.py 3.5.0")
        print(
            "Example: python scripts/prepare_release_notes.py 3.5.0 'Performance Improvements'"
        )
        print(
            "\nThis will generate release notes from merged PRs since the last release."
        )
        sys.exit(1)

    version = sys.argv[1]
    subtitle = sys.argv[2] if len(sys.argv) == 3 else ""

    # Validate version format
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        print(f"Error: Invalid version format '{version}'. Expected format: X.Y.Z")
        sys.exit(1)

    # Parse version
    try:
        major, minor, patch = parse_version(version)
    except (ValueError, IndexError):
        print(f"Error: Could not parse version '{version}'")
        sys.exit(1)

    if major != 3:
        print(f"Warning: This script is designed for 3.x releases. Got {version}")

    minor_version = f"{major}.{minor}"

    print(f"Preparing release notes for {version}...")
    print("Generating release notes from merged PRs...")

    # Generate the release notes
    release_info = generate_release_notes(version, subtitle)

    print(f"Generated release notes for: {release_info.get('name', version)}")

    # Update the minor version page
    if update_minor_version_page(minor_version, version, release_info):
        # Update docs.json
        update_docs_json(minor_version)
        print(f"\n✅ Successfully prepared release notes for {version}")
        print("\nNext steps:")
        print("  1. Review the generated release notes")
        print("  2. Make any necessary edits")
        print("  3. Commit the changes")
        print("  4. Create PR and merge to main")
    else:
        print(f"\n❌ Failed to prepare release notes for {version}")
        sys.exit(1)


if __name__ == "__main__":
    main()

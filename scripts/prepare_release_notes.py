#!/usr/bin/env python3
"""
Prepare release notes for a new release from a GitHub draft release.
This script fetches release notes from a draft release and updates the documentation.
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


def get_draft_release(version: str) -> dict | None:
    """Get draft release information from GitHub."""
    try:
        # List all releases including drafts
        output = run_command(
            ["gh", "release", "list", "--json", "tagName,name,body,publishedAt,isDraft"]
        )
        releases = json.loads(output)

        # Find the draft release for this version
        for release in releases:
            if release.get("isDraft") and release.get("tagName") == version:
                return release

        print(f"No draft release found for version {version}")
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error fetching releases: {e}")
        return None


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

        # Transform ### headers to bold text to reduce nav clutter
        if line.startswith("### "):
            header_text = line[4:].strip()
            filtered_lines.append(f"**{header_text}**")
        else:
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
    if len(sys.argv) != 2:
        print("Usage: python scripts/prepare_release_notes.py <version>")
        print("Example: python scripts/prepare_release_notes.py 3.5.0")
        print(
            "\nNote: This requires a draft release to exist on GitHub for the specified version."
        )
        sys.exit(1)

    version = sys.argv[1]

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
    print("Fetching draft release from GitHub...")

    # Get the draft release
    release_info = get_draft_release(version)
    if not release_info:
        print(f"\nError: No draft release found for version {version}")
        print("\nTo create a draft release:")
        print("  1. Go to https://github.com/PrefectHQ/prefect/releases/new")
        print(f"  2. Set tag to '{version}'")
        print("  3. Generate release notes")
        print("  4. Save as draft")
        print("  5. Run this script again")
        sys.exit(1)

    print(f"Found draft release: {release_info.get('name', version)}")

    # Update the minor version page
    if update_minor_version_page(minor_version, version, release_info):
        # Update docs.json
        update_docs_json(minor_version)
        print(f"\n✅ Successfully prepared release notes for {version}")
        print("\nNext steps:")
        print("  1. Review the generated release notes")
        print("  2. Make any necessary edits")
        print("  3. Commit the changes")
        print("  4. Create PR and merge")
        print("  5. Publish the draft release on GitHub")
    else:
        print(f"\n❌ Failed to prepare release notes for {version}")
        sys.exit(1)


if __name__ == "__main__":
    main()

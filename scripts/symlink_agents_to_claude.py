#!/usr/bin/env -S uv run --quiet --script

"""
This script creates symlinks from AGENTS.md files to CLAUDE.md files.

Usage:
python scripts/symlink_agents_to_claude.py
"""

import os
from pathlib import Path
from typing import Iterator


def find_agents_files(root_dir: Path) -> Iterator[Path]:
    """Find all AGENTS.md files in the directory tree."""
    return root_dir.rglob("AGENTS.md")


def create_claude_symlinks(root_dir: Path | str) -> None:
    """Create CLAUDE.md symlinks for all AGENTS.md files."""
    root = Path(root_dir)

    for agents_file in find_agents_files(root):
        claude_link = agents_file.parent / "CLAUDE.md"

        if claude_link.is_symlink():
            claude_link.unlink()

        os.symlink("AGENTS.md", claude_link)
        print(f"Created symlink: {claude_link} -> AGENTS.md")


if __name__ == "__main__":
    create_claude_symlinks(".")

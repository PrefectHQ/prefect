#!/usr/bin/env bash
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

find . \( -name .venv -o -name node_modules -o -name .git -o -name __pycache__ \) -prune \
    -o -name AGENTS.md -print | while read -r agents_file; do
    dir=$(dirname "$agents_file")
    claude_link="$dir/CLAUDE.md"

    if [ -L "$claude_link" ]; then
        target=$(readlink "$claude_link")
        if [ "$target" = "AGENTS.md" ]; then
            echo "Already linked: $claude_link -> AGENTS.md"
            continue
        fi
        rm "$claude_link"
    elif [ -e "$claude_link" ]; then
        echo "Skipped (regular file exists): $claude_link"
        continue
    fi

    ln -s AGENTS.md "$claude_link"
    echo "Created symlink: $claude_link -> AGENTS.md"
done

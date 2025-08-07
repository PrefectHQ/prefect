mod docs

# Check for uv installation
check-uv:
    #!/usr/bin/env sh
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv is not installed or not found in expected locations."
        case "$(uname)" in
            "Darwin")
                echo "To install uv on macOS, run one of:"
                echo "• brew install uv"
                echo "• curl -LsSf https://astral.sh/uv/install.sh | sh"
                ;;
            "Linux")
                echo "To install uv, run:"
                echo "• curl -LsSf https://astral.sh/uv/install.sh | sh"
                ;;
            *)
                echo "To install uv, visit: https://github.com/astral-sh/uv"
                ;;
        esac
        exit 1
    fi

# Install development dependencies
install: check-uv
    uv sync --group perf

# Clean up environment
clean: check-uv
    deactivate || true
    rm -rf .venv

# Generate API reference documentation for all modules
api-ref-all:
    uvx --with-editable . --refresh-package mdxify mdxify@latest --all --root-module prefect --output-dir docs/v3/api-ref/python --anchor-name "Python SDK Reference" --exclude prefect.agent --include-inheritance

# Generate API reference for specific modules (e.g., just api-ref prefect.flows prefect.tasks)
api-ref *MODULES:
    uvx --with-editable . --refresh-package mdxify mdxify@latest {{MODULES}} --root-module prefect --output-dir docs/v3/api-ref/python --anchor-name "Python SDK Reference" --include-inheritance

# Clean up API reference documentation
api-ref-clean:
    rm -rf docs/python-sdk

# Generate example pages
generate-examples:
    uv run --isolated -p 3.13 --with anyio scripts/generate_example_pages.py

# Prepare release notes from a GitHub draft release
# Usage: just prepare-release 3.5.0
prepare-release VERSION:
    #!/usr/bin/env bash
    set -e
    echo "Preparing release notes for version {{VERSION}}..."
    
    # Run the script to fetch from draft and generate docs
    python scripts/prepare_release_notes.py {{VERSION}}
    
    # Open the generated file in the user's editor
    if [ -n "$EDITOR" ]; then
        # Determine the minor version for the file path
        MINOR=$(echo {{VERSION}} | cut -d. -f1-2)
        FILE="docs/v3/release-notes/oss/version-${MINOR//./-}.mdx"
        
        if [ -f "$FILE" ]; then
            echo "Opening $FILE in $EDITOR..."
            $EDITOR "$FILE"
        else
            echo "Generated file not found: $FILE"
        fi
    else
        echo "No EDITOR environment variable set. Please review the generated files manually."
    fi
    
    echo ""
    echo "After review, commit the changes and create a PR."

# TODO: consider these for GHA (https://just.systems/man/en/github-actions.html)

# - uses: extractions/setup-just@v2
#   with:
#     just-version: 1.5.0  # optional semver specification, otherwise latest

# for example, use just to define/use common lint commands:
#     lint: check-uv
#         uvx ruff check . --fix

#     using it in a GHA workflow:
#         - uses: extractions/setup-just@v2
#         with:
#             just-version: 1.5.0  # optional semver specification, otherwise latest

#         - run: just lint

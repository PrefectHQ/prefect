# Ensure uv is available, installing it if needed
check-uv:
    #!/usr/bin/env sh
    if ! command -v uv >/dev/null 2>&1; then
        echo "Installing uv..."
        if [ "$(uname)" = "Darwin" ] || [ "$(uname)" = "Linux" ]; then
            curl -LsSf https://astral.sh/uv/install.sh | sh
        else
            pip install uv
        fi
        # Verify installation succeeded
        if ! command -v uv >/dev/null 2>&1; then
            echo "Failed to install uv. Please try installing it manually:"
            echo "• curl -LsSf https://astral.sh/uv/install.sh | sh  # For macOS/Linux"
            echo "• pip install uv  # Using pip"
            echo "For more information, visit: https://github.com/astral-sh/uv"
            exit 1
        fi
    fi

# Build and serve documentation
docs: check-uv
    cd docs && uv run mintlify dev

# Install development dependencies
install: check-uv
    echo "this solves prefect + integrations deps into a uv.lock, so the first install is slow, subsequent syncs are fast"
    # TODO: commit the uv.lock file
    uv sync --dev

# Clean up environment
clean: check-uv
    deactivate || true
    rm -rf .venv

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
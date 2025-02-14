# Check for uv installation
check-uv:
    #!/usr/bin/env sh
    if ! command -v uv >/dev/null 2>&1; then
        echo "uv is not installed. Please install it using one of these methods:"
        echo "• curl -LsSf https://astral.sh/uv/install.sh | sh  # For macOS/Linux"
        echo "• pip install uv  # Using pip"
        echo "For more information, visit: https://github.com/astral-sh/uv"
        exit 1
    fi

# List available commands
default:
    @just --list

# Clean up
clean: check-uv
    deactivate || true
    rm -rf .venv

# Install development dependencies
install: check-uv
    echo "this solves prefect + integrations deps into a uv.lock, so the first install is slow, subsequent syncs are fast"
    # TODO: commit the uv.lock file
    uv sync --dev

# Start the Prefect server
server: check-uv
    uv run prefect server start

# Build and serve documentation
docs: check-uv
    cd docs && uv run mintlify dev
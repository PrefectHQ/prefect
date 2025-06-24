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

# Build and serve documentation
docs: check-uv
    cd docs && npx mintlify dev

# Install development dependencies
install: check-uv
    uv sync --group perf

# Clean up environment
clean: check-uv
    deactivate || true
    rm -rf .venv

# Generate API reference documentation for all modules
api-ref-all:
    uvx --with-editable . --refresh-package mdxify mdxify@latest --all --root-module prefect --output-dir docs/v3/api-ref/python --anchor-name "Python SDK Reference" --exclude prefect.agent

# Generate API reference for specific modules (e.g., just api-ref prefect.flows prefect.tasks)
api-ref *MODULES:
    uvx --with-editable . --refresh-package mdxify mdxify@latest {{MODULES}} --root-module prefect --output-dir docs/v3/api-ref/python --anchor-name "Python SDK Reference"

# Clean up API reference documentation
api-ref-clean:
    rm -rf docs/python-sdk

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
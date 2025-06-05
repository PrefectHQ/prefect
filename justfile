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
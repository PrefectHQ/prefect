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

# Symlink all AGENTS.md files to CLAUDE.md
symlink-agents-to-claude:
    ./scripts/symlink_agents_to_claude.py

# Generate API reference documentation for all modules
api-ref-all:
    uvx --with-editable . \
        --python 3.12 \
        --isolated \
        mdxify \
        --all \
        --root-module prefect \
        --output-dir docs/v3/api-ref/python \
        --anchor-name "Python SDK Reference" \
        --repo-url https://github.com/PrefectHQ/prefect \
        --exclude prefect.agent \
        --include-inheritance

# Generate API reference for specific modules (e.g., just api-ref prefect.flows prefect.tasks)
api-ref *MODULES:
    uvx --with-editable . \
        --refresh-package mdxify \
        mdxify@latest \
        {{MODULES}} \
        --root-module prefect \
        --output-dir docs/v3/api-ref/python \
        --anchor-name "Python SDK Reference" \
        --repo-url https://github.com/PrefectHQ/prefect \
        --include-inheritance

# Clean up API reference documentation
api-ref-clean:
    rm -rf docs/python-sdk

# Generate example pages
generate-examples:
    uv run --isolated -p 3.13 --with anyio scripts/generate_example_pages.py

# Generate OpenAPI documentation
generate-openapi:
    uv run --isolated -p 3.10 --with 'pydantic>=2.9.0' ./scripts/generate_mintlify_openapi_docs.py

# Generate settings schema and reference
generate-settings:
    uv run --isolated -p 3.10 --with 'pydantic>=2.9.0' ./scripts/generate_settings_schema.py
    uv run --isolated -p 3.10 --with 'pydantic>=2.9.0' ./scripts/generate_settings_ref.py

# Generate prefect.yaml JSON schema for IDE support
generate-prefect-yaml-schema:
    uv run --isolated -p 3.10 --with 'pydantic>=2.9.0' ./scripts/generate_prefect_yaml_schema.py

generate-cli-docs:
    uv run --isolated ./scripts/generate_cli_docs.py

# Generate all documentation (OpenAPI, settings, API ref, examples)
generate-docs:
    @echo "Generating all documentation..."
    @echo "1. Generating OpenAPI docs..."
    @just generate-openapi
    @echo "2. Generating settings schema and reference..."
    @just generate-settings
    @echo "3. Generating prefect.yaml schema..."
    @just generate-prefect-yaml-schema
    @echo "4. Generating API reference..."
    @just api-ref-all
    @echo "5. Generating CLI docs..."
    @just generate-cli-docs
    @echo "6. Generating example pages..."
    @just generate-examples
    @echo "Documentation generation complete!"

# Prepare release notes from a GitHub draft release
# Usage: just prepare-release 3.5.0
prepare-release VERSION:
    #!/usr/bin/env bash
    set -e
    echo "Preparing release notes for version {{VERSION}}..."

    # Run the script to fetch from draft and generate docs
    uv run scripts/prepare_release_notes.py {{VERSION}}

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

# Prepare release notes for integration packages
# Usage: just prepare-integration-release PACKAGE
prepare-integration-release PACKAGE:
    #!/usr/bin/env bash
    set -e
    echo "Preparing release notes for {{PACKAGE}}..."

    # Run the script to generate integration release notes
    uv run scripts/prepare_integration_release_notes.py {{PACKAGE}}

    # Open the generated file in the user's editor
    if [ -n "$EDITOR" ]; then
        FILE="docs/v3/release-notes/integrations/{{PACKAGE}}.mdx"

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
    echo "Release notes generated successfully!"
    echo "Next steps:"
    echo "  1. Review the generated release notes"
    echo "  2. Open a PR to add the release notes to the docs"

# Check for nvm installation
check-nvm:
    #!/usr/bin/env bash
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

    if ! command -v nvm >/dev/null 2>&1; then
        echo "nvm is not installed."
        echo "To install nvm, run:"
        echo "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
        exit 1
    fi

# Install ui-v2 dependencies
ui-v2-install: check-nvm
    #!/usr/bin/env bash
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

    cd ui-v2
    nvm install
    npm install

# Start the v2 React UI dev server
ui-v2: ui-v2-install
    #!/usr/bin/env bash
    export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
    [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"

    cd ui-v2
    nvm use
    npm run dev

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

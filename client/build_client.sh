#!/bin/bash

set -e

CWD=$(pwd)

# if running in GH Actions, this will already be set
if [ -z ${TMPDIR+x} ]; then
    TMPDIR=$(mktemp -d)
    echo "Using workspace at $TMPDIR"
else 
    echo "Using workspace at $TMPDIR"
fi

# Create necessary directories
mkdir -p $TMPDIR/src/prefect

# Copy necessary files and directories
cp -R src/prefect $TMPDIR/src/
cp pyproject.toml $TMPDIR/
cp README.md $TMPDIR/
cp LICENSE $TMPDIR/
cp MANIFEST.in $TMPDIR/
cp -R client $TMPDIR/

cd $TMPDIR/src/prefect

# delete the files we don't need
rm -rf cli/
rm -rf deployments/recipes/
rm -rf deployments/templates
rm -rf server/__init__.py
find ./server \
    -not -path "./server" \
    -not -path "./server/api" \
    -not -path "./server/api/*" \
    -delete
rm -rf server/database
rm -rf server/models
rm -rf server/orchestration
rm -rf server/schemas
rm -rf server/services
rm -rf testing
rm -rf server/utilities

# replace old build files with client build files
cd $TMPDIR
cp client/setup.py .
cp client/README.md .

# update pyproject.toml for client-only build
python - <<END
import toml
import subprocess

def get_git_version():
    try:
        version = subprocess.check_output(["git", "describe", "--tags"]).strip().decode('ascii')
        return version
    except Exception:
        return "0.0.0"

with open("pyproject.toml", "r") as f:
    data = toml.load(f)

# Update project name and version
data["project"]["name"] = "prefect-client"
data["project"]["version"] = get_git_version()

# Remove main package dependencies
data["project"]["dependencies"] = ["prefect[client]"]

# Move client dependencies to main dependencies
client_deps = data["project"]["optional-dependencies"].pop("client")
data["project"]["dependencies"].extend(client_deps)

# Ensure toml is in build-system requires
if "toml" not in data["build-system"]["requires"]:
    data["build-system"]["requires"].append("toml")

with open("pyproject.toml", "w") as f:
    toml.dump(data, f)
END

# if running in GH Actions, this happens in external workflow steps
# this is a convenience to simulate the full build locally
if [ -z ${CI} ]; then
    if [[ -z "${PREFECT_API_KEY}" ]] || [[ -z "${PREFECT_API_URL}" ]]; then
        echo "In order to run smoke tests locally, PREFECT_API_KEY and"\
        "PREFECT_API_URL must be set and valid for a Prefect Cloud account."
        exit 1
    fi
    python -m venv venv
    source venv/bin/activate
    pip install build toml
    python -m build
    pip install dist/*.whl
    python client/client_flow.py
    echo "Build and smoke test completed successfully. Final results:"
    echo "$(du -sh $VIRTUAL_ENV)"
    deactivate
else 
    echo "Skipping local build"
fi

cd $CWD
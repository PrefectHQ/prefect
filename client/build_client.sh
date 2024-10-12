#!/bin/bash

CWD=$(pwd)

# if running in GH Actions, this will already be set
if [ -z ${TMPDIR+x} ];
    then
        TMPDIR=$(mktemp -d);
        echo "Using workspace at $TMPDIR";
    else echo "Using workspace at $TMPDIR";
fi

# init the workspace
mkdir -p $TMPDIR/src
cp -rf ./src/prefect $TMPDIR/src/
cd $TMPDIR/src/prefect

# delete the files we don't need
rm -rf cli/
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
cp $CWD/client/setup.py .
cp $CWD/client/README.md .
cp $CWD/requirements-client.txt .
cp $CWD/setup.cfg .

# if running in GH Actions, this happens in external workflow steps
# this is a convenience to simulate the full build locally
if [ -z ${CI} ];
    then
        if [[ -z "${PREFECT_API_KEY}" ]] || [[ -z "${PREFECT_API_URL}" ]]; then
            echo "In order to run smoke tests locally, PREFECT_API_KEY and"\
            "PREFECT_API_URL must be set and valid for a Prefect Cloud account.";
            exit 1;
        fi

        # Install uv
        curl -LsSf https://astral.sh/uv/install.sh | sh

        # Create a new virtual environment and activate it
        uv venv --python 3.12

        # Use uv to install dependencies and build the package
        uv build

        # Install the built package
        uv pip install dist/*.whl

        # Run the smoke test
        python $CWD/client/client_flow.py

        echo "Build and smoke test completed successfully. Final results:"
        echo "$(du -sh .venv)"
    else
        echo "Skipping local build"
    fi

cd $CWD

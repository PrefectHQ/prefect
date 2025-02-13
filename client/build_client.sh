#!/bin/bash

CWD=$(pwd)

# if running in GH Actions, this will already be set
if [ -z ${TMPDIR+x} ];
    then
        TMPDIR=$(mktemp -d);
        echo "Using workspace at $TMPDIR";
    else echo "Using workspace at $TMPDIR";
fi

# init the workspace with only client files first
mkdir -p $TMPDIR/client_build
cp -rf client/* $TMPDIR/client_build/

# create local src directory and copy parent src
mkdir -p $TMPDIR/client_build/src
cp -rf src/prefect $TMPDIR/client_build/src/

cd $TMPDIR/client_build/src/prefect

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

cd $TMPDIR/client_build

# if running in GH Actions, this happens in external workflow steps
# this is a convenience to simulate the full build locally
if [ -z ${CI} ];
    then
        if [[ -z "${PREFECT_API_KEY}" ]] || [[ -z "${PREFECT_API_URL}" ]]; then
            echo "In order to run smoke tests locally, PREFECT_API_KEY and"\
            "PREFECT_API_URL must be set and valid for a Prefect Cloud account.";
            exit 1;
        fi
        uv build --sdist --wheel;
        uv pip install dist/*.tar.gz;
        uv run client/client_flow.py;
        echo "Build and smoke test completed successfully. Final results:";
        echo "$(du -sh $VIRTUAL_ENV)";
        deactivate;
    else echo "Skipping local build";
fi

# Copy dist files back to original location if they exist
if [ -d "$TMPDIR/client_build/dist" ]; then
    mkdir -p $CWD/dist
    cp -rf $TMPDIR/client_build/dist/* $CWD/dist/
fi

cd $CWD

#!/bin/bash

# this is a script to build and smoke test the prefect_client package
#
# it requires uv to be installed and the PREFECT_API_KEY and PREFECT_API_URL
# environment variables to be set


set -e  # Exit immediately if a command exits with a non-zero status

CWD=$(pwd)
TMPDIR=$(mktemp -d)
echo "🚀 Initializing workspace at $TMPDIR"

# Export the clean version
export CLEAN_PREFECT_VERSION=$(uv run $CWD/client/clean_version.py)
echo "🔧 Using version $CLEAN_PREFECT_VERSION of prefect_client"

# Init the workspace
mkdir -p $TMPDIR/src/prefect

# Copy only necessary files and directories
cp -r $CWD/src/prefect $TMPDIR/src/
cp -r $CWD/client $TMPDIR/
cp $CWD/requirements-client.txt $TMPDIR/
cp $CWD/setup.cfg $TMPDIR/
cp $CWD/MANIFEST.in $TMPDIR/

# Remove unnecessary files and directories
cd $TMPDIR/src/prefect
rm -rf cli/ server/__init__.py server/database server/models server/orchestration server/schemas server/services testing server/utilities
find ./server -not -path "./server" -not -path "./server/api" -not -path "./server/api/*" -delete

# Replace old build files with client build files
cd $TMPDIR
cp $CWD/client/setup.py .
cp $CWD/client/README.md .
cp $CWD/client/client_flow.py .

# if running in GH Actions, this happens in external workflow steps
# this is a convenience to simulate the full build locally
if [ -z ${CI} ]; then
    if [[ -z "${PREFECT_API_KEY}" ]] || [[ -z "${PREFECT_API_URL}" ]]; then
        echo "❌ PREFECT_API_KEY and PREFECT_API_URL must be set for local smoke tests."
        exit 1
    fi

    # Create a log file
    LOG_FILE=$(mktemp)

    # Clean the dist directory before building
    rm -rf dist/*

    echo "⚙️ Building prefect_client..."
    uv build >> $LOG_FILE 2>&1

    echo "📦 Installing prefect_client..."
    uv pip install dist/*.whl >> $LOG_FILE 2>&1

    echo "🔥 Running smoke test..."
    echo "----------------------------------------"
    echo "Smoke Test Output:"
    echo "----------------------------------------"
    if ! uv run $CWD/client/client_flow.py | tee -a $LOG_FILE; then
        echo "----------------------------------------"
        echo "❌ Smoke test failed. Full build log:"
        echo "----------------------------------------"
        cat $LOG_FILE
        echo "----------------------------------------"
        exit 1
    fi
    echo "----------------------------------------"

    echo "✅ Build and smoke test completed successfully."
    rm $LOG_FILE
else
    echo "🚫 Skipping local build (CI environment detected)"
fi

cd $CWD
echo "🏁 All done!"

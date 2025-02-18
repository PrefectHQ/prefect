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
cp -rf ./ $TMPDIR
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
cp client/pyproject.toml .
cp client/README.md .

cd $CWD

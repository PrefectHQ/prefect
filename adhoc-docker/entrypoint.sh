#!/usr/bin/env bash

# Exit immediately if any command returns a non-zero status
set -e

# Install specified Python version
uv python install --no-progress ${PYTHON_VERSION}

# Create virtual environment with specified Python version
uv venv .venv --python="${PYTHON_VERSION}"

# Activate the virtual environment
. .venv/bin/activate

# Install prefect with specified version
if [ "${PREFECT_VERSION}" = "latest" ]; then
    echo "Installing latest version of prefect" 
    uv pip install --quiet prefect
else
    echo "Installing prefect==${PREFECT_VERSION}"
    uv pip install --quiet "prefect==${PREFECT_VERSION}"
fi

# Install extra pip packages if specified
if [ ! -z "$EXTRA_PIP_PACKAGES" ]; then
  echo "+uv pip install $EXTRA_PIP_PACKAGES"
  uv pip install $EXTRA_PIP_PACKAGES
fi

if [ -z "$*" ]; then
  echo "\
  ___ ___ ___ ___ ___ ___ _____ 
 | _ \ _ \ __| __| __/ __|_   _|
 |  _/   / _|| _|| _| (__  | |  
 |_| |_|_\___|_| |___\___| |_|  

"
  exec bash --login
else
  exec "$@"
fi
#!/usr/bin/env bash
# This is the default entrypoint for the official Prefect Docker image

set -e

if [ -f ~/.bashrc ]; then
  . ~/.bashrc
fi

if [ ! -z "$EXTRA_PIP_PACKAGES" ]; then
  echo "+uv pip install $EXTRA_PIP_PACKAGES"
  uv pip install --system $EXTRA_PIP_PACKAGES 2>&1 | tee /tmp/uv-install.log
  uv_exit_code=${PIPESTATUS[0]}
  if [ $uv_exit_code -ne 0 ]; then
    prefect logs send --silent --level error --name prefect.entrypoint /tmp/uv-install.log
    exit $uv_exit_code
  fi
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

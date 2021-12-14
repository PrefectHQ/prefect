#!/usr/bin/env bash

set -e

if [ ! -z "$EXTRA_PIP_PACKAGES" ]; then
  echo "+pip install $EXTRA_PIP_PACKAGES"
  pip install $EXTRA_PIP_PACKAGES
fi

if [ -z "$*" ]; then
  echo "\
            _____  _____  ______ ______ ______ _____ _______
           |  __ \|  __ \|  ____|  ____|  ____/ ____|__   __|
           | |__) | |__) | |__  | |__  | |__ | |       | |
           |  ___/|  _  /|  __| |  __| |  __|| |       | |
           | |    | | \ \| |____| |    | |___| |____   | |
           |_|    |_|  \_\______|_|    |______\_____|  |_|

Thanks for using Prefect!!!

This is the official docker image for Prefect Orion, intended for executing flows.
"
  exec bash --login
else
  exec "$@"
fi

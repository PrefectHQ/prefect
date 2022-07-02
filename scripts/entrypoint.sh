#!/usr/bin/env bash

set -e

if [ -f ~/.bashrc ]; then
  . ~/.bashrc
fi

if [ ! -z "$EXTRA_PIP_PACKAGES" ]; then
  echo "+pip install $EXTRA_PIP_PACKAGES"
  pip install $EXTRA_PIP_PACKAGES
fi

if [ -z "$*" ]; then
  echo "\
          ____  _____  _____ ____  _   _
         / __ \|  __ \|_   _/ __ \| \ | |
        | |  | | |__) | | || |  | |  \| |
        | |  | |  _  /  | || |  | |     |
        | |__| | | \ \ _| || |__| | |\  |
         \____/|_|  \_\_____\____/|_| \_|


Thanks for using Prefect!!!

This is a development docker image for Prefect Orion.
"
  exec bash --login
else
  exec "$@"
fi

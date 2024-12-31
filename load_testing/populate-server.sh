#!/usr/bin/env bash

prefect --no-prompt work-pool create local --type process --overwrite

prefect --no-prompt deploy --all --prefect-file load_testing/prefect.yaml

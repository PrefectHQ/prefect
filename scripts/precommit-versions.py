#!/usr/bin/env python3
"""
Parses the pre-commit configuration file to get the pinned revisions.

Usage:

    precommit-versions.py [<hook>, ...]

The hooks default to 'black' and 'ruff' but you can specify different
hooks. For example, here we just get the 'black' version:

    ./precommit-versions.py black

The output can be used with pip

    pip install $(./scripts/precommit-versions.py)

"""
import os
import sys

import yaml

path = ".pre-commit-config.yaml"
if not os.path.exists(path):
    print(
        f"{path} not found in current directory!",
        file=sys.stderr,
    )
    exit(1)

hooks = sys.argv[1:] if len(sys.argv) > 1 else ["black", "ruff"]

# Parse the versions from the pre-commit config which pins them
precommit_config = yaml.safe_load(open(path))
rev_by_id = {item["hooks"][0]["id"]: item["rev"] for item in precommit_config["repos"]}

for hook in hooks:
    print(f"{hook}=={rev_by_id[hook].lstrip('v')}", end=" ")

print()

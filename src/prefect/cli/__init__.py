#!/usr/bin/env python

import click
import logging
import os
import requests
import sys
import prefect

from .flows import flows


@click.group()
@click.option("--registry-path")
@click.option("--registry-encryption-key")
def cli(registry_path=None, registry_encryption_key=None):
    """
    The Prefect CLI
    """
    if registry_path:
        prefect.core.registry.load_serialized_registry_from_path(
            registry_path, encryption_key=registry_encryption_key
        )


cli.add_command(flows)

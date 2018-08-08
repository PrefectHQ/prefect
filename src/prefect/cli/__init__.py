#!/usr/bin/env python

import click
import logging
import os
import requests
import sys

from .flows import flows




@click.group()
def cli():
    """
    The Prefect CLI
    """
    pass


cli.add_command(flows)

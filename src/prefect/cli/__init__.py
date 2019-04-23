#!/usr/bin/env python


import click
import json
import logging
import os
import requests
import sys

import prefect
from prefect.client import Client
from prefect.utilities.graphql import with_args


@click.group()
def cli():
    """
    The Prefect CLI
    """
    pass


@cli.command()
@click.argument("storage_metadata")
@click.argument("environment_metadata")
@click.argument("flow_location")
def execute_flow(storage_metadata, environment_metadata, flow_location):
    """"""
    storage_schema = prefect.serialization.storage.StorageSchema()
    storage = storage_schema.load(json.loads(storage_metadata))

    environment_schema = prefect.serialization.environment.EnvironmentSchema()
    environment = environment_schema.load(json.loads(environment_metadata))

    environment.setup(storage)
    environment.execute(storage, flow_location)


@cli.command()
def execute_cloud_flow():
    flow_run_id = prefect.context.get("flow_run_id")
    if not flow_run_id:
        click.echo("Not currently executing a flow within a cloud context.")
        return

    query = {
        "query": {
            with_args("flow_run", {"where": {"id": {"_eq": flow_run_id}}}): {
                "flow": {"name": True, "storage": True, "environment": True}
            }
        }
    }

    result = Client().graphql(query)

    flow_data = result.data.flow_run[0].flow

    storage_schema = prefect.serialization.storage.StorageSchema()
    storage = storage_schema.load(flow_data.storage)

    environment_schema = prefect.serialization.environment.EnvironmentSchema()
    environment = environment_schema.load(flow_data.environment)

    environment.execute(storage=storage, flow_location=storage.flows[flow_data.name])
